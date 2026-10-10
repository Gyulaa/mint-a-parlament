"""Egységtábla: a szomszédsági gráf csúcsai a hatályos körzetbeosztással.

Egység = egész település, kivéve a hatályos térképen megosztott településeket és a
budapesti kerületeket, ahol egység = szavazókör. Külön réteg a megosztható települések
(fővárosi kerületek és az országos átlagnál nagyobb települések, Vjt. 4. § (3))
összes szavazóköre, hogy később ott is lehessen finomabban osztani.

Kimenet: data/interim/egysegek.gpkg (rétegek: telepulesek, szavazokorok, egysegek)
         data/interim/egysegek.csv  (geometria nélkül, áttekintéshez)

Futtatás: python -m oevk.egysegek
"""

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from .adat import (EOV, INTERIM, WGS84, config, ksh_helysegnevtar, ksh_nemzetiseg,
                   lechner_telepulesek, nev_kulcs, nvi_megyek, nvi_szavazokorok,
                   nvi_szavkor_topo, nvi_telepulesek)

SZEKHELY_JOGALLAS = {"város", "megyei jogú város", "fővárosi kerület"}


def ellenoriz(feltetel, uzenet):
    if not feltetel:
        raise AssertionError(uzenet)
    print("  ok:", uzenet)


def telepulesek():
    cfg = config()
    t = nvi_telepulesek(cfg["letszam_valasztas"])
    t["megye"] = t.maz.map(nvi_megyek(cfg["letszam_valasztas"]))
    t["k"] = t.megye + "|" + t.nvi_nev.map(nev_kulcs)

    h, _ = ksh_helysegnevtar()
    h["k"] = h.megye + "|" + h.nev.map(nev_kulcs)
    t = t.merge(h[["k", "nev", "ksh_kod", "jogallas", "jaras", "jaras_szekhely"]], on="k", how="left")
    ellenoriz(t.ksh_kod.notna().all(), f"minden NVI-település KSH-kódot kapott ({len(t)})")

    n = ksh_nemzetiseg()
    n["k"] = n.megye + "|" + n.nev.map(nev_kulcs)
    t = t.merge(n.drop(columns=["megye", "nev"]), on="k", how="left")
    print(f"  népszámlálási adat hiányzik: {t.nep_2022.isna().sum()} településnél")

    t22 = nvi_telepulesek(cfg["trend_valasztas"])[["maz", "taz", "indulo"]]
    t = t.merge(t22.rename(columns={"indulo": "jogosult_2022"}), on=["maz", "taz"], how="left")
    ellenoriz(t.jogosult_2022.notna().all(), "minden településnek van 2022-es létszáma")

    g = lechner_telepulesek()
    t = gpd.GeoDataFrame(t.merge(g, on="ksh_kod", how="left"), geometry="geometry", crs=EOV)
    ellenoriz(t.geometry.notna().all(), "minden település Lechner-poligont kapott")

    t["szekhely_jelolt"] = t.jogallas.isin(SZEKHELY_JOGALLAS) | (t.nev == t.jaras_szekhely)
    t["megosztott"] = t.evk_lst.str.len() > 1
    atlag = t.indulo.sum() / cfg["oevk_szam"]
    t["megoszthato"] = (t.maz == "01") | (t.indulo > atlag)
    t["evk_lst"] = t.evk_lst.str.join(";")
    return t.drop(columns=["k"])


RACS = 0.1  # m; a geometriai műveletek rácsa (a lebegőpontos topológiai hibák ellen)


def csak_felulet(g):
    """A geometria felületi (poligon) része; vonal- és pontdarabok nélkül."""
    reszek = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    return shapely.union_all(reszek) if reszek else shapely.Polygon()


def egyesit(reszek):
    """Poligonok egyesítése; a GEOS topológiai hibáinál egyre durvább, de biztos módszerrel."""
    for f in (shapely.coverage_union_all, shapely.union_all,
              lambda r: shapely.union_all(r, grid_size=RACS),
              lambda r: shapely.union_all([shapely.buffer(c, RACS / 2) for c in r], grid_size=RACS)):
        try:
            return csak_felulet(f(reszek))
        except shapely.errors.GEOSException as e:
            hiba = e
    raise hiba


def kitolt(poligonok, telepules, lepes=25.0):
    """Hézag- és átfedésmentes felosztás: a település minden pontja a legközelebbi szavazókörhöz.

    Az eredeti poligonok (a sorrendben előbbi nyer átfedésnél) megmaradnak; a lefedetlen részt a
    poligonhatárokon sűrűn felvett pontok Voronoi-cellái szerint osztjuk szét.
    """
    def metszet(a, b):
        return csak_felulet(shapely.intersection(a, b, grid_size=RACS))

    def unio(a, b):
        return csak_felulet(shapely.union(a, b, grid_size=RACS))

    telepules = csak_felulet(shapely.set_precision(telepules, RACS))
    vagott, eddig = [], shapely.Polygon()
    for p in poligonok:
        p = metszet(csak_felulet(shapely.make_valid(p)), telepules)
        p = csak_felulet(shapely.difference(p, eddig, grid_size=RACS))
        vagott.append(p)
        eddig = unio(eddig, p)
    arany = eddig.area / telepules.area
    hezag = csak_felulet(shapely.difference(telepules, eddig, grid_size=RACS))
    if hezag.area < 1:
        return vagott, arany

    pontok, cimke = [], []
    for i, (p, eredeti) in enumerate(zip(vagott, poligonok)):
        if p.is_empty:  # teljesen átfedett szavazókör: az eredeti belső pontjából indul
            pontok.append(eredeti.representative_point())
            cimke.append(i)
            continue
        hat = p.boundary
        n = max(int(hat.length / lepes), 4)
        pontok += [hat.interpolate(k / n, normalized=True) for k in range(n)]
        cimke += [i] * n
    # a szomszédos szavazókörök közös határán ismétlődő pontokból csak az első marad
    xy = shapely.get_coordinates(pontok).round(1)
    _, elso = np.unique(xy, axis=0, return_index=True)
    elso.sort()
    pontok, cimke = [pontok[k] for k in elso], [cimke[k] for k in elso]
    cellak = shapely.voronoi_polygons(shapely.MultiPoint(pontok), extend_to=telepules, ordered=True)
    resz = [[] for _ in vagott]
    for i, c in zip(cimke, shapely.get_parts(cellak)):
        resz[i].append(c)
    return [unio(p, metszet(egyesit(r), hezag))
            for p, r in zip(vagott, resz)], arany


def szavazokorok(tel):
    """A megosztható települések szavazókörei, NVI-poligonnal (a településhatárra vágva)."""
    cfg = config()
    sz = nvi_szavazokorok(cfg["letszam_valasztas"])
    ellenoriz(sz.indulo.sum() == tel.indulo.sum(), "a szavazóköri létszámok összege egyezik")
    celok = tel[tel.megoszthato]
    sz = sz.merge(celok[["maz", "taz", "nev", "megye", "ksh_kod", "jaras"]], on=["maz", "taz"])

    geom = []
    for (maz, taz), _ in sz.groupby(["maz", "taz"]):
        geom += [{"maz": maz, "taz": taz, "szk": szk, "geometry": p, "centrum": c}
                 for szk, p, c in nvi_szavkor_topo(maz, taz, cfg["letszam_valasztas"])]
    geom = pd.DataFrame(geom)
    geom["geometry"] = gpd.GeoSeries(geom.geometry, crs=WGS84).to_crs(EOV).make_valid().values
    geom["centrum"] = gpd.GeoSeries(geom.centrum, crs=WGS84).to_crs(EOV).values
    sz = gpd.GeoDataFrame(sz.merge(geom, on=["maz", "taz", "szk"], how="left"), geometry="geometry", crs=EOV)

    # Csak átjelentkezőknek kijelölt szavazókör: nincs lakcím szerinti választója, nincs területe.
    ures = sz.geometry.isna() | sz.geometry.is_empty | (sz.geometry.area < 100)
    csak_atj = sz.atj_kijelolt & (sz.indulo == 0)
    print(f"  poligon nélküli szavazókör: {ures.sum()} db; csak átjelentkezési, lakcím szerinti "
          f"választó nélküli: {csak_atj.sum()} db (elhagyva)")
    sz = sz[~csak_atj & (~ures | (sz.indulo > 0))].copy()
    # Ahol van választó, de a poligon hibás: a középpont körüli 150 m-es kör, megjelölve.
    becsult = sz.geometry.isna() | sz.geometry.is_empty | (sz.geometry.area < 100)
    sz["geom_becsult"] = becsult
    sz.loc[becsult, "geometry"] = sz.loc[becsult, "centrum"].buffer(150)
    for _, r in sz[becsult].iterrows():
        print(f"  BECSÜLT TERÜLET: {r.nev} {r.szk}. szavazókör ({r.indulo} fő)")
    sz = sz.drop(columns="centrum")

    # A VTR-poligonok egyszerűsítettek (kb. 10 m) és a külterületet gyakran nem fedik le:
    # a településhatárra vágjuk, és a lefedetlen részt a legközelebbi szavazókörhöz soroljuk.
    # Átfedésnél a kisebb poligon nyer: a nagy, hibás VTR-poligonok csak a maradékot kapják.
    hatar = celok.set_index(["maz", "taz"]).geometry
    sz["eredeti"] = sz.geometry
    sz["poligon_ervenytelen"] = False
    lefedes = []
    for (maz, taz), idx in sz.groupby(["maz", "taz"]).groups.items():
        idx = sz.loc[idx].geometry.area.sort_values().index
        uj, arany = kitolt(list(sz.loc[idx, "geometry"]), hatar[(maz, taz)])
        sz.loc[idx, "geometry"] = gpd.GeoSeries(uj, index=idx, crs=EOV)
        lefedes.append(arany)
    print(f"  az eredeti VTR-poligonok lefedettsége településenként: min {min(lefedes):.1%}, "
          f"medián {sorted(lefedes)[len(lefedes) // 2]:.1%}; a többit kitöltöttük")
    sz["unit_id"] = sz.maz + "-" + sz.taz + "-" + sz.szk
    sz["oevk_jelenlegi"] = sz.maz + "-" + sz.evk
    return osszevon_uresek(sz).drop(columns="eredeti")


def osszevon_uresek(sz):
    """A területet nem kapott szavazókört összevonja azzal, amelyik a VTR-poligonja belső pontját lefedi.

    Tipikus eset: a VTR több szavazókörre is (közel) ugyanazt a poligont adja. Az összevont egység
    azonosítója a tagok sorszáma '+' jellel. Csak azonos OEVK-n belül vonunk össze.
    """
    ures = sz[sz.geometry.is_empty | (sz.geometry.area < 1)]
    for i, r in ures.iterrows():
        jelolt = sz[(sz.maz == r.maz) & (sz.taz == r.taz) & ~sz.index.isin(ures.index)
                    & sz.geometry.contains(r.eredeti.representative_point())]
        if jelolt.empty or jelolt.iloc[0].evk != r.evk:
            raise AssertionError(f"{r.nev} {r.szk}. szavazókör nem vonható össze azonos OEVK-n belül")
        j = jelolt.index[0]
        sz.loc[j, ["indulo", "osszesen"]] += r[["indulo", "osszesen"]].values
        sz.loc[j, "szk"] += "+" + r.szk
        sz.loc[j, "unit_id"] += "+" + r.szk
        sz.loc[j, "poligon_ervenytelen"] = True
        print(f"  ÖSSZEVONVA: {r.nev} {r.szk}. -> {sz.loc[j, 'szk']} ({r.indulo} fő)")
    return sz.drop(index=ures.index)


def egysegek(tel, szk):
    # Szavazókör-szintű egység: a hatályos térképen megosztott települések, valamint Budapest minden
    # kerülete (fővárosi kerület bármikor megosztható, és a 17. körzethez erre szükség lehet).
    finom = tel.megosztott | (tel.maz == "01")
    egesz = tel[~finom].copy()
    egesz["unit_id"] = egesz.maz + "-" + egesz.taz
    egesz["szint"] = "telepules"
    egesz["oevk_jelenlegi"] = egesz.maz + "-" + egesz.evk_lst
    egesz = egesz.rename(columns={"indulo": "jogosult_2026", "osszesen": "osszesen_2026"})

    resz = szk[szk.set_index(["maz", "taz"]).index.isin(tel[finom].set_index(["maz", "taz"]).index)].copy()
    resz = resz.merge(tel[["maz", "taz", "jogallas", "szekhely_jelolt"]], on=["maz", "taz"])
    resz["szint"] = "szavazokor"
    resz = resz.rename(columns={"indulo": "jogosult_2026", "osszesen": "osszesen_2026"})

    oszlopok = ["unit_id", "szint", "maz", "taz", "nev", "megye", "ksh_kod", "jaras", "jogallas",
                "szekhely_jelolt", "oevk_jelenlegi", "jogosult_2026", "osszesen_2026", "jogosult_2022",
                "nep_2022"] + [c for c in tel.columns if c.startswith("nemz_")] + ["geometry"]
    e = pd.concat([egesz, resz], ignore_index=True).reindex(columns=oszlopok)
    return gpd.GeoDataFrame(e, geometry="geometry", crs=EOV)


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    print("Települések")
    tel = telepulesek()
    print("Szavazókörök (megosztható települések)")
    szk = szavazokorok(tel)
    print("Egységek")
    e = egysegek(tel, szk)
    cfg = config()
    ellenoriz(e.jogosult_2026.sum() == tel.indulo.sum(), f"az egységek létszáma {e.jogosult_2026.sum():,}")
    ellenoriz(e.oevk_jelenlegi.nunique() == cfg["oevk_szam"], "mind a 106 körzetnek van egysége")
    print(f"  {len(e)} egység: {(e.szint == 'telepules').sum()} település, "
          f"{(e.szint == 'szavazokor').sum()} szavazókör")

    kimenet = INTERIM / "egysegek.gpkg"
    kimenet.unlink(missing_ok=True)
    tel.to_file(kimenet, layer="telepulesek")
    szk.to_file(kimenet, layer="szavazokorok")
    e.to_file(kimenet, layer="egysegek")
    e.drop(columns="geometry").to_csv(INTERIM / "egysegek.csv", index=False, encoding="utf-8-sig")
    print(f"Kész: {kimenet}")


if __name__ == "__main__":
    main()

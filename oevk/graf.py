"""Szomszédsági gráf az egységtáblából, folyami átkelők kezelésével.

Két egység szomszédos, ha a közös határuk legalább `graf.min_kozos_hatar_m` hosszú.
Ha a két egység szárazföldi része (a folyómeder nélkül) nem határos, a kapcsolat a Dunán
vagy a Tiszán át vezet (config: graf.folyok), és csak akkor él, ha a határt közúti híd
vagy komp keresztezi (OSM). Minden ilyen döntés a
data/interim/atkelok.csv-be kerül, a földrajzos ezt hagyja jóvá; a felülbírálás a
data/manual/kivetelek.csv-ben történik ('el_torol' / 'el_hozzaad' sorokkal).

Kimenet: data/interim/szomszedsag.csv, data/interim/atkelok.csv
Futtatás: python -m oevk.graf
"""

import geopandas as gpd
import networkx as nx
import pandas as pd
import pyogrio
import shapely

from .adat import EOV, GYOKER, INTERIM, RAW, config

TUR = 5.0  # m; a közös határ mérésének tűrése
NEM_KOZUTI = {"footway", "path", "cycleway", "steps", "pedestrian", "bridleway", "corridor", "proposed",
              "construction", "platform", "abandoned", "razed"}


def egysegek():
    return gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")


def kozos_hatarok(e, min_hossz):
    """(i, j, közös határ geometria, hossz) minden szomszédos egységpárra."""
    bal, jobb = e.sindex.query(e.geometry.buffer(TUR), predicate="intersects")
    parok = [(i, j) for i, j in zip(bal, jobb) if i < j]
    hatar = e.geometry.boundary.values
    puffer = e.geometry.buffer(TUR).values
    sorok = []
    for i, j in parok:
        vonal = shapely.intersection(hatar[i], puffer[j])
        hossz = shapely.length(vonal)
        if hossz >= min_hossz:
            sorok.append((i, j, vonal, hossz))
    return sorok


def folyok(nevek):
    w = gpd.read_file("zip://" + (RAW / "lechner" / "waterways_poly.zip").as_posix() + "!waterways_poly.shp")
    w = w[w.vizf_nev.isin(nevek) & (w.kategoria != "híd")]
    return w.dissolve("vizf_nev").geometry.buffer(10)


def atkelok():
    """Közúti hidak, gyalogos/vasúti hidak és kompok az OSM-ből, EOV-ben."""
    f = (RAW / "osm" / "hungary-latest.osm.pbf").as_posix()
    d = pyogrio.read_dataframe(
        f, layer="lines", columns=["name", "highway", "railway", "other_tags"],
        where="other_tags LIKE '%\"bridge\"=>%' OR other_tags LIKE '%\"route\"=>\"ferry\"%'")
    t = d.other_tags.fillna("")
    d["tipus"] = None
    d.loc[t.str.contains('"route"=>"ferry"'), "tipus"] = "komp"
    d.loc[(d.tipus == "komp") & d.name.str.contains("gyalog", case=False, na=False), "tipus"] = "gyalogos komp"
    hid = t.str.contains('"bridge"=>') & ~t.str.contains('"bridge"=>"no"')
    d.loc[hid & d.railway.notna(), "tipus"] = "vasúti híd"
    d.loc[hid & d.highway.isin(NEM_KOZUTI), "tipus"] = "gyalogos híd"
    d.loc[hid & d.highway.notna() & ~d.highway.isin(NEM_KOZUTI), "tipus"] = "közúti híd"
    return d[d.tipus.notna()].to_crs(EOV)[["name", "tipus", "geometry"]]


def kivetelek():
    k = pd.read_csv(GYOKER / "data" / "manual" / "kivetelek.csv", dtype=str).fillna("")
    return k[k.tipus.isin(["el_torol", "el_hozzaad"])]


def main():
    cfg = config()["graf"]
    e = egysegek()
    print(f"{len(e)} egység; közös határok számítása...")
    parok = kozos_hatarok(e, cfg["min_kozos_hatar_m"])
    print(f"  {len(parok)} szomszédos pár (>= {cfg['min_kozos_hatar_m']} m)")

    fo = folyok(cfg["folyok"])
    meder = shapely.union_all(fo.values)
    szaraz = shapely.difference(e.geometry.values, meder)
    szaraz_hatar = shapely.boundary(szaraz)
    at = atkelok()
    at_idx = at.sindex
    sorok = []
    for i, j, vonal, hossz in parok:
        sor = {"a": e.unit_id[i], "b": e.unit_id[j], "hossz_m": round(hossz),
               "azonos_megye": e.megye[i] == e.megye[j], "folyo": "", "atkelo_tipus": "", "atkelo_nev": "",
               "el": True}
        foldon = shapely.length(shapely.intersection(szaraz_hatar[i], shapely.buffer(szaraz[j], TUR)))
        if foldon < cfg["min_kozos_hatar_m"]:
            sor["folyo"] = max(fo.index, key=lambda n: shapely.length(shapely.intersection(vonal, fo[n])))
        if sor["folyo"]:
            jelolt = at.iloc[at_idx.query(vonal.buffer(20), predicate="intersects")]
            jelolt = jelolt[jelolt.geometry.intersects(vonal.buffer(20))]
            if not jelolt.empty:
                rang = {"közúti híd": 0, "komp": 1, "gyalogos híd": 2, "gyalogos komp": 3, "vasúti híd": 4}
                jelolt = jelolt.assign(r=jelolt.tipus.map(rang)).sort_values("r")
                sor["atkelo_tipus"] = jelolt.tipus.iloc[0]
                sor["atkelo_nev"] = "; ".join(sorted(set(jelolt.name.dropna())))[:200]
            sor["el"] = sor["atkelo_tipus"] in ("közúti híd", "komp")
        sorok.append(sor)
    sz = pd.DataFrame(sorok)

    k = kivetelek()
    for _, r in k.iterrows():
        m = ((sz.a == r.egyseg_a) & (sz.b == r.egyseg_b)) | ((sz.a == r.egyseg_b) & (sz.b == r.egyseg_a))
        if r.tipus == "el_torol":
            sz.loc[m, "el"] = False
        elif not m.any():
            sz.loc[len(sz)] = {"a": r.egyseg_a, "b": r.egyseg_b, "hossz_m": 0, "azonos_megye": True,
                               "folyo": "", "atkelo_tipus": "kivétel", "atkelo_nev": r.indoklas, "el": True}
        else:
            sz.loc[m, "el"] = True
    print(f"  kivétellista: {len(k)} sor alkalmazva")

    sz.to_csv(INTERIM / "szomszedsag.csv", index=False, encoding="utf-8-sig")
    nevek = e.set_index("unit_id")
    fs = sz[sz.folyo != ""].copy()
    for o in ("a", "b"):
        fs[f"{o}_nev"] = fs[o].map(nevek.nev)
        fs[f"{o}_oevk"] = fs[o].map(nevek.oevk_jelenlegi)
    fs.to_csv(INTERIM / "atkelok.csv", index=False, encoding="utf-8-sig")
    print(f"  folyón átnyúló szomszédság: {len(fs)}, ebből híddal/komppal élő: {fs.el.sum()}")

    ellenoriz_hatalyos(e, sz)


def graf(e, sz, csak_el=True):
    g = nx.Graph()
    g.add_nodes_from(e.unit_id)
    el = sz[sz.el] if csak_el else sz
    g.add_edges_from(zip(el.a, el.b))
    return g


def ellenoriz_hatalyos(e, sz):
    """A hatályos körzetek összefüggősége: folyami élek nélkül, és csak híddal/komppal."""
    teljes = graf(e, sz, csak_el=False)
    atkelos = graf(e, sz)
    szaraz = graf(e, sz[sz.folyo == ""])
    print("\nA hatályos térkép összefüggősége")
    for nev, g in (("minden közös határ", teljes), ("csak híd/komp a folyókon", atkelos),
                   ("folyón át semmi", szaraz)):
        hibas = []
        for oevk, cs in e.groupby("oevk_jelenlegi").unit_id:
            n = nx.number_connected_components(g.subgraph(cs))
            if n > 1:
                hibas.append(f"{oevk} ({n} rész)")
        print(f"  {nev}: {len(hibas)} nem összefüggő körzet {', '.join(hibas[:20])}")
    for megye, cs in e.groupby("megye").unit_id:
        n = nx.number_connected_components(atkelos.subgraph(cs))
        if n > 1:
            print(f"  FIGYELEM: {megye} gráfja {n} részből áll")


if __name__ == "__main__":
    main()

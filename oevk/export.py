"""Térképexport GIS-programokhoz (ArcMap, QGIS): shapefile-ok EOV vetületben, egy ZIP-ben.

Rétegek (data/interim/export/oevk_javaslat_2026.zip):
- korzetek_ma:  a hatályos 106 körzet
- korzetek_A:   a javaslat (Tolna 2, Somogy 3, Budapest 17, Pest 15 körzet)
- egysegek:     települések és szavazókörök (Budapest, megosztott városok) a mai és a javasolt körzettel

A mezőnevek legfeljebb 10 karakteresek (shapefile), a kódolás UTF-8 (.cpg fájllal).
Futtatás: python -m oevk.export
"""

import json
import zipfile

import geopandas as gpd
import pandas as pd

from shapely.geometry import shape

from .adat import EOV, INTERIM, config, nvi_oevk

KI = INTERIM / "export"


def hozzarendeles(cfg, ag):
    """unit_id -> körzet az adott ágban (a nem érintett megyékben a hatályos)."""
    ki = {}
    for megye, db in cfg["forgatokonyvek"][ag].items():
        f = INTERIM / "javaslat" / f"{megye}_{db}.csv"
        t = pd.read_csv(f)
        ki.update(zip(t.unit_id, t.uj))
    return ki


def main():
    cfg = config()
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    e = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")
    e["geometry"] = e.geometry.buffer(0)
    szekhely = dict(zip(o.oevk, o.szekhely))
    KI.mkdir(parents=True, exist_ok=True)

    u = e[["unit_id", "nev", "megye", "jaras", "szint", "jogosult_2026", "oevk_jelenlegi", "geometry"]].rename(
        columns={"unit_id": "egyseg_id", "jogosult_2026": "valaszto", "oevk_jelenlegi": "oevk_ma"})
    retegek = {"korzetek_ma": u.oevk_ma}
    for ag in cfg["forgatokonyvek"]:
        h = hozzarendeles(cfg, ag)
        u[f"oevk_{ag}"] = u.egyseg_id.map(h).fillna(u.oevk_ma)
        u[f"valt_{ag}"] = (u[f"oevk_{ag}"] != u.oevk_ma).astype(int)
        retegek[f"korzetek_{ag}"] = u[f"oevk_{ag}"]
        for megye, db in cfg["forgatokonyvek"][ag].items():  # az új körzetek székhelye
            r = pd.read_csv(INTERIM / "javaslat" / f"{megye}_{db}_meroszam.csv").iloc[0]
            szekhely.update(json.loads(r.szekhelyek))
        # az új körzet székhelye vidéken a legnépesebb települése, ahogy a 2. mellékletben (oevk/melleklet.py)
        for k in set(u[f"oevk_{ag}"]) - set(o.oevk):
            t = u[u[f"oevk_{ag}"] == k]
            if t.megye.iloc[0] != "főváros":
                szekhely[k] = t.groupby("nev").valaszto.sum().idxmax()

    fajlok = []
    for nev, oszlop in retegek.items():
        d = u.assign(oevk=oszlop).dissolve("oevk", aggfunc={"valaszto": "sum", "megye": "first"}).reset_index()
        d["geometry"] = d.geometry.buffer(1).buffer(-1)
        d["szekhely"] = d.oevk.map(szekhely)
        d["elteres"] = (d.valaszto / A - 1).round(4)
        d = d[["oevk", "szekhely", "megye", "valaszto", "elteres", "geometry"]]
        fajlok += ment(d, nev)
    fajlok += ment(u, "egysegek")
    f = INTERIM / "melleklet" / "melleklet_A.json"  # a budapesti határvonal-tervezetek szakaszai (A terv)
    if f.exists():
        sorok = []
        for k in json.loads(f.read_text(encoding="utf-8"))["korzetek"]:
            for t in k.get("terkepek", []):
                for x in t["szakaszok"]:
                    sorok.append({"oevk": k["oevk"], "korzet": k["rovidites"], "kerulet": t["kerulet_nev"],
                                  "nev": x["nev"] or "", "ellenoriz": int(x["ellenorizendo"]), "szam": x["szam"] or 0,
                                  "geometry": shape(x["g"])})
        if sorok:
            fajlok += ment(gpd.GeoDataFrame(sorok, crs=4326).to_crs(EOV), "hatar_szakaszok")
    zf = KI / "oevk_javaslat_2026.zip"
    with zipfile.ZipFile(zf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fajlok:
            z.write(f, f.name)
        z.writestr("OLVASSEL.txt", OLVASSEL.format(A=round(A)))
    print(zf, f"{zf.stat().st_size / 1e6:.1f} MB")


def ment(gdf, nev):
    f = KI / f"{nev}.shp"
    gdf.to_file(f, driver="ESRI Shapefile", encoding="utf-8")
    f.with_suffix(".cpg").write_text("UTF-8", encoding="ascii")
    return [p for p in KI.glob(f"{nev}.*")]


OLVASSEL = """OEVK-javaslat 2026 – térképi export (Miklós Gyula, Mint a parlament)

Vetület: EOV (EPSG:23700). Kódolás: UTF-8 (.cpg).

korzetek_ma   a hatályos 106 országgyűlési egyéni választókerület
korzetek_A    a javaslat: Tolna 2, Somogy 3, Budapest 17, Pest 15 körzet
egysegek      települések; Budapesten és a 8 megosztott városban szavazókörök

Mezők: oevk (körzet), szekhely, megye, valaszto (2026-os névjegyzék, induló létszám),
elteres (eltérés az országos átlagtól, {A} választó), oevk_ma / oevk_A (körzet ma és
a javaslatban), valt_A (1 = másik körzetbe kerül), szint (település / szavazókör).

A szavazókör-poligonok az NVI egyszerűsített térképeiből készültek, a hiányzó részeket a legközelebbi
szavazókör tölti ki; utcaszinten közelítők.
Források: NVI (valasztas.hu), Lechner Tudásközpont (CC BY 4.0), KSH.
"""

if __name__ == "__main__":
    main()

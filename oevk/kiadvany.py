"""A csapatnak szóló interaktív oldalak (földrajzos, jogász) előállítása.

A web/*.html sablonokba beilleszti a térképadatot (WGS84, egyszerűsített geometria) és a
Leaflet stíluslapját (a megosztott oldal nem tölthet be külső CSS-t), az eredmény a
data/interim/web/ mappába kerül.

Javaslat: csak oda nyúlunk, ahol a korlát sérül (docs/elvek.md). A megyénkénti terveket az
oevk/javaslat.py számolja (config: javaslat), a forgatókönyvek (A, B) a körzetszámokat adják.

Futtatás: python -m oevk.kiadvany
"""

import json
import re

import geopandas as gpd
import networkx as nx
import pandas as pd
import requests
import shapely

from .adat import INTERIM, RAW, WGS84, GYOKER, config, nvi_oevk
from .graf import folyok
from .modell import Megye, adatok, megye_nev_ksh

LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
KI = INTERIM / "web"
NEMZ = ["cigány", "horvát", "német", "román", "szerb", "szlovák", "szlovén", "ruszin", "ukrán", "bolgár",
        "görög", "lengyel", "örmény"]
TOMB_KUSZOB = 0.10


def kerekit(geom, jegy=4):
    """GeoJSON-geometria koordinátái 4 tizedesre (kb. 10 m)."""
    g = json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]

    def k(c):
        return [k(x) for x in c] if isinstance(c[0], list) else [round(c[0], jegy), round(c[1], jegy)]

    g["coordinates"] = k(g["coordinates"])
    return g


def egyszerusit(gdf, tures_m):
    gdf = gdf.copy()
    gdf["geometry"] = gdf.geometry.simplify(tures_m, preserve_topology=True)
    return gdf.to_crs(WGS84)


def megyehatarok():
    g = gpd.read_file("zip://" + (RAW / "lechner" / "AdministrativeUnits2025.zip").as_posix()
                      + "!AU.AdministrativeUnits.2025.shp")
    g = egyszerusit(g[g.desn == "Vármegye"], 400)
    return [{"nev": r.namn, "g": kerekit(r.geometry, 3)} for r in g.itertuples()]


def folyo_poligonok():
    f = folyok(config()["graf"]["folyok"]).to_frame("geometry").reset_index()
    f = egyszerusit(gpd.GeoDataFrame(f, geometry="geometry", crs="EPSG:23700"), 40)
    return [{"nev": r.vizf_nev, "g": kerekit(r.geometry)} for r in f.itertuples()]


def atkelok_adat(e):
    """A folyón átnyúló szomszédságok pontként (a közös határ középpontja) + az érintett egységek."""
    sz = pd.read_csv(INTERIM / "szomszedsag.csv")
    fs = sz[sz.folyo.notna() & (sz.folyo != "")].reset_index(drop=True)
    geo = e.set_index("unit_id")
    pontok, erintett = [], set()
    for _, r in fs.iterrows():
        a, b = geo.geometry[r.a], geo.geometry[r.b]
        kozos = a.boundary.intersection(b.buffer(5))
        p = gpd.GeoSeries([kozos.centroid if not kozos.is_empty else a.union(b).centroid],
                          crs="EPSG:23700").to_crs(WGS84).iloc[0]
        erintett |= {r.a, r.b}
        pontok.append({
            "id": f"{r.a}~{r.b}", "a": geo.nev[r.a], "b": geo.nev[r.b], "ua": r.a, "ub": r.b,
            "oa": geo.oevk_jelenlegi[r.a], "ob": geo.oevk_jelenlegi[r.b], "megye": geo.megye[r.a],
            "folyo": r.folyo, "tipus": r.atkelo_tipus if isinstance(r.atkelo_tipus, str) else "",
            "atkelo": r.atkelo_nev if isinstance(r.atkelo_nev, str) else "", "el": bool(r.el),
            "megyen_belul": bool(r.azonos_megye), "hossz": int(r.hossz_m),
            "lat": round(p.y, 5), "lon": round(p.x, 5),
        })
    tel = egyszerusit(e[e.unit_id.isin(erintett)], 25)
    egysegek = [{"id": r.unit_id, "nev": r.nev, "oevk": r.oevk_jelenlegi, "g": kerekit(r.geometry)}
                for r in tel.itertuples()]
    return pontok, egysegek


def nemzetisegi_aranyok(e_tab):
    """unit_id -> {nemzetiség: arány}, csak az 5% feletti arányok (település szintű egységekre)."""
    ki = {}
    for r in e_tab.itertuples():
        nep = getattr(r, "nep_2022")
        if r.szint != "telepules" or not nep or pd.isna(nep):
            continue
        d = {n: round(float(getattr(r, f"nemz_{n}")) / nep, 3) for n in NEMZ
             if not pd.isna(getattr(r, f"nemz_{n}", float("nan")))}
        d = {n: a for n, a in d.items() if a >= 0.05}
        if d:
            ki[r.unit_id] = d
    return ki


def tombok(m, aranyok):
    """Összefüggő nemzetiségi tömbök a megyében: szomszédos települések, ahol ugyanaz a
    nemzetiség legalább TOMB_KUSZOB arányú (legalább két település)."""
    ki = []
    for n in NEMZ:
        tagok = [i for i, u in enumerate(m.e.unit_id) if aranyok.get(u, {}).get(n, 0) >= TOMB_KUSZOB]
        for resz in nx.connected_components(m.g.subgraph(tagok)):
            if len(resz) >= 2:
                resz = sorted(resz)
                ki.append({"nemz": n, "tagok": resz, "nevek": [m.e.nev[i] for i in resz],
                           "nep": int(sum(m.v[i] for i in resz))})
    return ki


def vagott_tombok(tomb_lista, x):
    return [k for k, t in enumerate(tomb_lista) if len({x[i] for i in t["tagok"]}) > 1]


def valtozat_nev(op, osszetetel=None):
    """Az opció „változata” a kiegyenlítés mértéke nélkül: melyik körzet szűnik meg / miből áll az új."""
    c = op["cimke"] if isinstance(op["cimke"], str) else "-"
    if c.startswith("megszűnik: "):
        return c.replace("megszűnik: ", "Megszűnik: ")
    if c.startswith("új körzet"):
        return f"Új körzet: {osszetetel} részeiből" if osszetetel else "Új körzet " + c.split("mag: ")[-1] + " környékén"
    return f"{op['db']} körzet, határkiigazítással"


def korzet_szinek(m, opciok, n_szin=9):
    """Körzetazonosító -> színindex: a bármelyik tervben szomszédos körzetek különböző színt kapnak,
    és egy körzet minden nézetben ugyanazt a színt viseli (mohó gráfszínezés)."""
    g = nx.Graph()
    for op in opciok:
        x = op["uj"]
        g.add_nodes_from(set(x))
        g.add_edges_from((x[a], x[b]) for a, b in m.el if x[a] != x[b])
    szin = {}
    for k in sorted(g.nodes, key=lambda k: (-g.degree(k), k)):
        foglalt = {szin[t] for t in g[k] if t in szin}
        szin[k] = next(i for i in range(n_szin * 3) if i not in foglalt) % n_szin
    return szin


def esetek(e_geo, e_tab, sz, A):
    """Megyénként: egységek, a hatályos állapot és az összes kiszámolt opció."""
    cfg = config()
    o = nvi_oevk()
    aranyok = nemzetisegi_aranyok(e_tab)
    ki = {}
    for megye in cfg["javaslat"]:
        m = Megye(e_tab, sz, megye_nev_ksh(megye))
        tures = 20 if megye == "Budapest" else 60
        g = egyszerusit(e_geo.set_index("unit_id").loc[m.e.unit_id].reset_index(), tures)
        egysegek = [{"id": r.unit_id, "nev": r.nev, "v": int(r.jogosult_2026), "o": r.oevk_jelenlegi,
                     "g": kerekit(r.geometry), **({"n": aranyok[r.unit_id]} if r.unit_id in aranyok else {})}
                    for r in g.itertuples()]
        tomb = tombok(m, aranyok)
        szekhely = {r.oevk: r.szekhely for r in o[o.megye.str.startswith(megye)].itertuples()}
        hatalyos = m.ertekel(m.regi, A)
        opciok = [{"id": "hatalyos", "db": len(szekhely), "tures": None, "cimke": "A hatályos térkép",
                   "uj": list(m.regi), "athelyezett": 0, "athelyezett_egyseg": 0,
                   "elteres": hatalyos["legnagyobb_elteres"], "uj_vagas": 0, "jaras": hatalyos["megosztott_jaras"],
                   "allapot": "", "szekhelyek": szekhely, "tomb_vagas": vagott_tombok(tomb, list(m.regi))}]
        for beall in cfg["javaslat"][megye]:
            if beall.get("utotag"):  # vizsgált változat, nem része a javaslatnak
                continue
            db = beall["db"]
            f = INTERIM / "javaslat" / f"{megye}_{db}.csv"
            if not f.exists():
                print(f"  hiányzik: {f.name} (python -m oevk.javaslat {megye})")
                continue
            r = pd.read_csv(INTERIM / "javaslat" / f"{megye}_{db}_meroszam.csv").iloc[0]
            uj = list(pd.read_csv(f).set_index("unit_id").loc[m.e.unit_id].uj)
            cimke = (f"megszűnik: {beall['megszunik']} ({szekhely[beall['megszunik']]})" if "megszunik" in beall
                     else "új körzet" if "uj_mag" in beall else "-")
            opciok.append({
                "id": str(db), "db": db, "tures": beall["tures"], "cimke": cimke, "uj": uj,
                "athelyezett": int(r.athelyezett_valasztopolgar), "athelyezett_egyseg": int(r.athelyezett_egyseg),
                "elteres": float(r.legnagyobb_elteres), "uj_vagas": int(r.uj_elvagott_el),
                "uj_hatar_km": float(r.uj_hatar_km), "jaras": int(r.megosztott_jaras), "allapot": r.allapot,
                "szekhelyek": json.loads(r.szekhelyek), "tomb_vagas": vagott_tombok(tomb, uj)})
        regiek = set(m.regi)
        for op in opciok:
            uj_id = sorted(set(op["uj"]) - regiek)
            osszetetel = None
            if uj_id:  # az új körzet: mely települések / kerületek részeiből áll
                nep = pd.Series(m.v)[[x == uj_id[0] for x in op["uj"]]].groupby(m.e.nev).sum().sort_values(ascending=False)
                nevek = [n.replace("Budapest ", "") for n in nep.index[:3] if nep[n] >= 0.1 * nep.sum()]
                osszetetel = " + ".join(sorted(nevek))
            op["valtozat"] = "Nincs változás" if op["id"] == "hatalyos" else valtozat_nev(op, osszetetel)
            if osszetetel:  # új körzetnél a változat egy döntés (új körzet), az összetétel részlet
                op["valtozat"], op["osszetetel"] = "Új körzet kialakítása", osszetetel + " részeiből"
        # azonos változat és tűrés mellett csak a legkisebb költségű (a gorbe rang szerinti első) marad
        latott, egyedi = set(), []
        for op in opciok:
            kulcs = (op["valtozat"], op["db"], op["tures"])
            azonos_a_mai = op["id"] != "hatalyos" and op["athelyezett"] == 0 and op["db"] == opciok[0]["db"]
            if kulcs not in latott and not azonos_a_mai:
                latott.add(kulcs)
                egyedi.append(op)
        opciok = egyedi
        hatar = e_geo.set_index("unit_id").loc[m.e.unit_id].dissolve("oevk_jelenlegi").reset_index()
        hatar["geometry"] = hatar.geometry.apply(tisztit)
        hatar = egyszerusit(hatar, 40)
        ki[megye] = {"egysegek": egysegek, "opciok": opciok, "tombok": tomb, "szekhely": szekhely,
                     "szin": korzet_szinek(m, opciok),
                     "hatar_ma": [{"id": r.oevk_jelenlegi, "g": kerekit(r.geometry)} for r in hatar.itertuples()]}
        print(f"  {megye}: {len(egysegek)} egység, {len(opciok)} opció, {len(tomb)} nemzetiségi tömb")
    return ki


def alapjavaslat(es, forgatokonyv):
    """Megyénként a forgatókönyv körzetszámához tartozó terv azonosítója (ha nincs, a hatályos marad)."""
    ki = {}
    for megye, d in es.items():
        db = forgatokonyv.get(megye, d["opciok"][0]["db"])
        jo = [o for o in d["opciok"] if o["db"] == db and o["id"] != "hatalyos"]
        if jo:
            ki[megye] = jo[0]["id"]
    return ki


def tisztit(geom, min_terulet=10_000):
    """Összeolvasztott körzetpoligon tisztítása: a szavazókör-térképek hajszálréseit 1 m-es
    zárással eltünteti, az 1 ha alatti lyukakat és darabokat elhagyja (ezek a vásznas
    rajzolásnál fehér foltként jelennének meg)."""
    g = shapely.make_valid(geom.buffer(1).buffer(-1))
    reszek = []
    for p in shapely.get_parts(g):
        if p.geom_type != "Polygon" or p.area < min_terulet:
            continue
        reszek.append(shapely.Polygon(p.exterior, [r for r in p.interiors if shapely.Polygon(r).area >= min_terulet]))
    return shapely.MultiPolygon(reszek) if len(reszek) > 1 else (reszek[0] if reszek else geom)


def korzet_poligonok(e_geo, hozzarendeles, A):
    """unit_id -> körzet hozzárendelésből körzetpoligonok (egyszerűsítve), létszámmal."""
    g = e_geo[["unit_id", "jogosult_2026", "megye", "geometry"]].copy()
    g["k"] = g.unit_id.map(hozzarendeles)
    d = g.dissolve("k", aggfunc={"jogosult_2026": "sum", "megye": "first"}).reset_index()
    d["geometry"] = d.geometry.apply(tisztit)
    d = egyszerusit(d, 150)
    return [{"oevk": r.k, "megye": r.megye, "v": int(r.jogosult_2026), "e": round(r.jogosult_2026 / A - 1, 4),
             "g": kerekit(r.geometry, 3)} for r in d.itertuples()]


def beilleszt(sablon, kimenet, adat, css):
    if not (GYOKER / "web" / sablon).exists():  # a belső (csapat) sablonok nincsenek a nyilvános repóban
        print(f"  {sablon}: nincs sablon, kihagyva")
        return
    html = (GYOKER / "web" / sablon).read_text(encoding="utf-8")
    html = html.replace("/*LEAFLET_CSS*/", css)
    html = html.replace("__ADAT__", json.dumps(adat, ensure_ascii=False, separators=(",", ":")))
    KI.mkdir(parents=True, exist_ok=True)
    (KI / kimenet).write_text(html, encoding="utf-8")
    print(f"  {kimenet}: {len(html) / 1e6:.1f} MB")


def main():
    cfg = config()
    css = requests.get(LEAFLET_CSS, timeout=60).text
    css = re.sub(r"url\([^)]*\)", "none", css)  # a képes ikonokat nem használjuk
    e_geo = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")
    e_tab, sz = adatok()
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    print("Esetek és opciók...")
    es = esetek(e_geo, e_tab, sz, A)

    print("Országos körzettérképek...")
    ma = dict(zip(e_geo.unit_id, e_geo.oevk_jelenlegi))
    szekhely = dict(zip(o.oevk, o.szekhely))
    forg = {}
    for nev, f in cfg["forgatokonyvek"].items():
        jav = alapjavaslat(es, f)
        hozz = dict(ma)
        nevek = dict(szekhely)
        for megye, oid in jav.items():
            op = next(x for x in es[megye]["opciok"] if x["id"] == oid)
            hozz.update(zip((u["id"] for u in es[megye]["egysegek"]), op["uj"]))
            nevek.update(op["szekhelyek"])
        forg[nev] = {"db": f, "javaslat": jav, "anomalia": {},
                     "korzetek": korzet_poligonok(e_geo, hozz, A), "szekhely": nevek}
    korzetek_ma = korzet_poligonok(e_geo, ma, A)

    nep = o.groupby("megye").indulo.sum()
    ma_db = o.groupby("megye").size()
    nev_rovid = {m: m.replace(" vármegye", "").replace(" főváros", "") for m in nep.index}
    elosztas = []
    for m in nep.index:
        r = nev_rovid[m]
        elosztas.append({"megye": r, "v": int(nep[m]), "ma": int(ma_db[m]),
                         **{k: int(f.get(r, ma_db[m])) for k, f in cfg["forgatokonyvek"].items()}})
    # d'Hondt összevetésül
    h = pd.Series(0, index=nep.index)
    for _ in range(cfg["oevk_szam"]):
        h[(nep / (h + 1)).idxmax()] += 1
    for x in elosztas:
        x["dhondt"] = int(h[next(m for m in nep.index if nev_rovid[m] == x["megye"])])

    alap = {"A": A, "megyek": megyehatarok(), "folyok": folyo_poligonok()}
    f = INTERIM / "melleklet" / "melleklet_A.json"  # az oldal csak a fő javaslat (A) szövegét mutatja
    melleklet = json.loads(f.read_text(encoding="utf-8"))["korzetek"] if f.exists() else []
    for k in melleklet:  # a címlistából csak rövid részlet kerül az oldalra; a teljes lista a Word-tervezetben
        k["cimlistak"] = [{"kerulet": c["kerulet"], "szavazokorok": len(c["szavazokorok"]), "valaszto": c["valaszto"],
                           "db": len(c["cimek"]), "minta": c["cimek"][:6]} for c in k.get("cimlistak", [])]
    beilleszt("foldrajz.html", "foldrajz.html",
              {**alap, "esetek": es, "korzetek_ma": korzetek_ma, "szekhely_ma": szekhely, "forgatokonyvek": forg,
               "tomb_kuszob": TOMB_KUSZOB, "melleklet": melleklet}, css)
    beilleszt("jog.html", "jog.html",
              {**alap, "esetek": es, "korzetek_ma": korzetek_ma, "szekhely_ma": szekhely,
               "forgatokonyvek": forg, "elosztas": elosztas, "tomb_kuszob": TOMB_KUSZOB}, css)


if __name__ == "__main__":
    main()

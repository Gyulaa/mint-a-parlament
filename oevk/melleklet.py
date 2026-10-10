"""A Vjt. 1. és 2. mellékletének módosítása a javaslat szerint: szövegtervezet a jogi csapatnak.

A 2. melléklet szerkezetét követi: körzetenként sorszám, rövidítés, székhely, terület (vidéken
településlista ábécérendben; Budapesten egész kerületek és kerületrészek határvonala). Csak a
változó körzetek kerülnek bele; a változatlan kerületrészek szövegét a hatályos mellékletből veszi át.

A budapesti kerületrészek határvonalát a program az egységek (szavazókörök) határából és az OSM
utcatengelyeiből állítja össze: ez tervezet, földrajzi ellenőrzés kell hozzá. Mellé a pontos
címlista kerül az NVI utcajegyzékéből (Korzethatar: melyik utca melyik házszáma melyik szavazókörbe
tartozik).

Kimenet: data/interim/melleklet/melleklet_<ág>.json
Futtatás: python -m oevk.melleklet
"""

import html
import json
import re
from collections import defaultdict

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from shapely.geometry import Point
from shapely.geometry.polygon import orient

from .adat import EOV, INTERIM, RAW, config, nvi_oevk, vtr_mappa

KI = INTERIM / "melleklet"
ROMAI = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII"]
MEGYE_CIM = {"Budapest": "Budapest", "Pest": "Pest megye", "Somogy": "Somogy megye", "Tolna": "Tolna megye"}
BETUK = ["a", "á", "b", "c", "cs", "d", "dz", "dzs", "e", "é", "f", "g", "gy", "h", "i", "í", "j", "k", "l", "ly",
         "m", "n", "ny", "o", "ó", "ö", "ő", "p", "q", "r", "s", "sz", "t", "ty", "u", "ú", "ü", "ű", "v", "w", "x",
         "y", "z", "zs"]
RANG = {b: i for i, b in enumerate(BETUK)}


def hu_kulcs(s):
    """Magyar ábécérend: kettős és hármas betűk; az ékezetes magánhangzó elsőre azonos rangú
    az ékezetlennel (a = á, o = ó, ö = ő …), csak döntetlennél számít."""
    def betuk(x):
        k, i = [], 0
        while i < len(x):
            for h in (3, 2, 1):
                if x[i:i + h] in RANG:
                    k.append(x[i:i + h])
                    i += h
                    break
            else:
                k.append(x[i])
                i += 1
        return k
    b = betuk(s.lower().replace("-", " "))
    elso = [-1 if x == " " else RANG.get(ROVID.get(x, x), 99) + 1 for x in b]  # a szóköz mindennél előbb
    masod = [-1 if x == " " else RANG.get(x, 99) + 1 for x in b]
    return elso, masod


ROVID = {"á": "a", "é": "e", "í": "i", "ó": "o", "ő": "ö", "ú": "u", "ű": "ü"}


def ig(nev):
    """„-ig” rag: utca -> utcáig, út -> útig."""
    if nev.endswith("a"):
        return nev[:-1] + "áig"
    if nev.endswith("e"):
        return nev[:-1] + "éig"
    return nev + "ig"


def nak(nev):
    """„-nak/-nek” rag a tengelyvonal elé nem kell; a névelő: a/az."""
    return ("az " if nev[:1].lower() in "aáeéiíoóöőuúüű" else "a ") + nev


# ---------- a hatályos 2. melléklet ----------

def hatalyos_melleklet():
    """{(megye, sorszám): {"szekhely": str, "tetelek": [str]}} a net.jogtar szövegéből."""
    s = (RAW / "jog" / "vjt_net_jogtar.html").read_text(encoding="utf-8", errors="ignore")
    t = html.unescape(re.sub(r"<br\s*/?>|</p>|</div>|</tr>", "\n", s))
    t = re.sub(r"<[^>]+>", " ", t)
    sorok = [re.sub(r"\s+", " ", x).strip(" *") for x in t.split("\n")]
    sorok = [x.replace(" * ", " ").strip() for x in sorok if x.strip()]
    i = next(k for k, x in enumerate(sorok) if x.startswith("Az egyéni választókerületek sorszáma, székhelye"))
    ki, megye, akt = {}, None, None
    for x in sorok[i + 1:]:
        if x.startswith("Megállapította:") or x.startswith("3. számú melléklet"):
            break
        if x == "Budapest" or (x.endswith(" megye") and len(x) < 40 and "választókerület" not in x):
            megye = x
            continue
        m = re.match(r"^(\d\d)\. számú országgyűlési egyéni választókerület$", x)
        if m:
            akt = ki.setdefault((megye, m.group(1)), {"szekhely": None, "tetelek": []})
            continue
        if akt is None:
            continue
        if x.startswith("Székhelye:"):
            akt["szekhely"] = x.split(":", 1)[1].strip()
        elif re.match(r"^\d+\. ", x):
            akt["tetelek"].append(re.sub(r"^\d+\. ", "", x))
    return ki


# ---------- budapesti kerületrészek ----------

def nvi_cimek(taz):
    """A kerület utcajegyzéke: [(utca teljes neve, int_tip, kezd, zaro, szavazókör)]."""
    f = vtr_mappa("ogy2026")["ver"] / "01" / f"Korzethatar-01-{taz}.json"
    d = json.loads(f.read_text(encoding="utf-8"))["data"]["korzethatarok"]
    return [((x["kt_nev"] + " " + x.get("kt_jelleg", "")).strip(), x["int_tip"], x.get("kezd_hsz"), x.get("zaro_hsz"),
             x["szavkor"]) for x in d]


def hsz(x):
    if x is None:
        return None
    if re.match(r"^9999\d\d", x):
        return "végig"
    return re.sub(r"(?<!\d)0+(?=\d)", "", x)


def cimlista(cimek, reszben):
    """A kerületrész címlistája: utcánként „teljes” vagy a házszám-tartományok."""
    utcak = defaultdict(list)
    for nev, tip, k, z, szk in cimek:
        utcak[nev].append((tip, k, z, szk in reszben))
    ki = []
    for nev in sorted(utcak, key=hu_kulcs):
        t = utcak[nev]
        if not any(b for *_, b in t):
            continue
        if all(b for *_, b in t):
            ki.append(f"{nev}: teljes")
            continue
        dar = []
        for tip, k, z, b in t:
            if not b:
                continue
            olda = {"2": "", "3": "páros oldal ", "4": "páratlan oldal ", "5": ""}.get(tip, "")
            if k is None:
                dar.append((olda.strip() or "teljes"))
            else:
                dar.append(f"{olda}{hsz(k)}–{hsz(z)}" + ("" if hsz(z) == "végig" else "."))
        ki.append(f"{nev}: " + ", ".join(dar))
    return ki


def osm_utcak():
    """Budapest névvel ellátott közútjai és vasútvonalai az OSM-ből, EOV-ben."""
    f = (RAW / "osm" / "hungary-latest.osm.pbf").as_posix()
    d = pyogrio.read_dataframe(f, layer="lines", columns=["name", "highway", "railway"],
                               bbox=(18.90, 47.33, 19.35, 47.62), where="name IS NOT NULL")
    d = d.to_crs(EOV)
    utcak = d[d.highway.notna()][["name", "geometry"]].reset_index(drop=True)
    vasut = d[d.railway.isin(["rail", "light_rail", "tram"])][["name", "geometry"]].reset_index(drop=True)
    return utcak, vasut


VEG = object()  # a felsorolás vége (nem tévesztendő össze a nem azonosított szakasszal)
NINCS = "[ellenőrizendő szakasz]"


def szakasz_nev(p, jelolt, idx_j, egyeb, idx_e, vasut, idx_v):
    """A ponthoz legközelebbi vonal neve: határutca (70 m), más utca (35 m), vasút (40 m)."""
    for gdf, idx, r, elotag in ((jelolt, idx_j, 70, ""), (egyeb, idx_e, 35, ""), (vasut, idx_v, 40, "vasút:")):
        t = idx.query(p.buffer(r), predicate="intersects")
        if len(t):
            tav = gdf.geometry.iloc[t].distance(p).values
            return elotag + gdf.name.iloc[t[int(np.argmin(tav))]]
    return None


def nevvel(x):
    if x is None:
        return NINCS
    if x.startswith("vasút:"):
        return "a " + x[6:] + " pályatengelye"
    return nak(x) + " tengelyvonala"


def hatarvonal(K, P, ker_nev, osm, hatarutcak, szamlalo, lepes=10.0):
    """Egy összefüggő kerületrész határvonalának szöveges leírása a 2. melléklet mintájára (tervezet).

    A kerületrész kerületét az óramutató járásával ellentétes irányban járja körbe; ahol a vonal
    a kerület határán fut, ott „a kerület határvonala”, egyébként a legközelebbi határutca (amelynek
    házszámai a két oldalon más körzetbe esnek), más utca vagy vasútvonal tengelye."""
    utcak, vasut = osm
    gyuru = orient(shapely.Polygon(P.exterior), 1.0).exterior
    K_hatar = K.buffer(5).buffer(-5).boundary
    n = max(int(gyuru.length / lepes), 8)
    pontok = [gyuru.interpolate(i * gyuru.length / n) for i in range(n)]
    jelolt = utcak[utcak.name.isin(hatarutcak)]
    egyeb = utcak[~utcak.name.isin(hatarutcak)]
    idx = (jelolt.sindex, egyeb.sindex, vasut.sindex)
    nevek = ["@hatar" if K_hatar.distance(p) < 40 else
             szakasz_nev(p, jelolt, idx[0], egyeb, idx[1], vasut, idx[2]) for p in pontok]
    if all(x == "@hatar" for x in nevek):
        return None, 0, []
    kezd = next((i for i in range(n) if nevek[i] != "@hatar" and nevek[i - 1] == "@hatar"), 0)
    nevek = nevek[kezd:] + nevek[:kezd]
    pontok = pontok[kezd:] + pontok[:kezd]
    # simítás: a 3 pontnál (30 m) rövidebb, nem kerülethatári futam az előző futam nevét kapja
    futam = futamok(nevek)
    for i, (x, a, b) in enumerate(futam):
        if b - a < 3 and x != "@hatar" and len(futam) > 1:
            uj = futam[i - 1][0] if i else futam[i + 1][0]
            nevek[a:b] = [uj] * (b - a)
            futam[i] = (uj, a, b)
    futam = futamok(nevek)
    if futam[0][0] == "@hatar":  # a kör ne kerülethatárral induljon
        futam = futam[1:] + futam[:1]
    szam = {}
    for k, (x, a, b) in enumerate(futam):
        if x is None:
            szamlalo[0] += 1
            szam[k] = szamlalo[0]
    szakaszok = [{"nev": x, "szam": szam.get(k),
                  "g": shapely.LineString([pontok[i % n].coords[0] for i in range(a, b)] + [pontok[b % n].coords[0]])}
                 for k, (x, a, b) in enumerate(futam)]
    bizonytalan = sum((b - a) * lepes for x, a, b in futam if x is None)
    sz = [x for x, _, _ in futam]
    nincs = lambda k: f"[ellenőrizendő szakasz {szam[k]}]"  # noqa: E731
    nev = lambda k: nincs(k) if sz[k] is None else nevvel(sz[k])  # noqa: E731
    jelzo = lambda k: (nincs(k) + " kezdőpontjáig") if sz[k] is None else \
        f"{nevvel(sz[k])}nak metszéspontjáig".replace("tengelyvonalanak", "tengelyvonalának").replace("pályatengelyenak", "pályatengelyének")  # noqa: E731
    reszek = []
    if "@hatar" in sz:
        eleje = (f"{nincs(0)} kezdőpontjától" if sz[0] is None else
                 f"{nevvel(sz[0])}nak metszéspontjától".replace("tengelyvonalanak", "tengelyvonalának").replace("pályatengelyenak", "pályatengelyének"))
        reszek.append(f"{ker_nev} határvonalának és {eleje}")
    else:
        reszek.append(f"{nev(0)} egy pontjától")
    for k, x in enumerate(sz):
        kov = k + 1 if k + 1 < len(sz) else None
        if kov is None:
            cel = "a kiindulási pontig"
        elif sz[kov] == "@hatar":
            cel = f"{ker_nev} határvonalának metszéspontjáig"
        elif sz[kov] is None:
            cel = None
        else:
            cel = sz[kov][6:] + " vasútvonalig" if sz[kov].startswith("vasút:") else ig(nak(sz[kov]))
        if x == "@hatar":
            cel = "a kiindulási pontig" if kov is None else jelzo(kov)
            reszek.append(f"a metszésponttól {ker_nev} határvonala az óramutató járásával ellentétes irányban {cel}")
        elif x is None:
            if k == 0:
                reszek.append(f"{nincs(k)} {cel}" if cel else nincs(k))
            else:
                reszek[-1] += f", majd {nincs(k)} {cel}" if cel else f", majd {nincs(k)}"
        else:
            reszek.append(f"{nevvel(x)} {cel}" if cel else nevvel(x))
    szoveg = ", ".join(reszek) + "."
    return szoveg[0].upper() + szoveg[1:], round(bizonytalan), szakaszok


def futamok(nevek):
    """[(név, kezdő index, záró index)] az egymást követő azonos nevekre."""
    ki, a = [], 0
    for i in range(1, len(nevek) + 1):
        if i == len(nevek) or nevek[i] != nevek[a]:
            ki.append((nevek[a], a, i))
            a = i
    return ki


def kozep(g):
    """A vonal (többrészesnél a leghosszabb része) felezőpontja: ide kerül a felirat."""
    return max(shapely.get_parts(g), key=lambda x: x.length).interpolate(0.5, normalized=True)


def wgs(geoms):
    """EOV-geometriák -> GeoJSON-szerű dict-ek WGS84-ben, 5 tizedesre kerekítve."""
    g = gpd.GeoSeries(list(geoms), crs=EOV).to_crs(4326)
    return [shapely.geometry.mapping(shapely.set_precision(x, 1e-5)) for x in g]


# ---------- összeállítás ----------

def main():
    cfg = config()
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    e = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")
    e["geometry"] = e.geometry.buffer(0)
    hat = hatalyos_melleklet()
    utcak = None
    KI.mkdir(parents=True, exist_ok=True)
    ma_db = o.groupby(o.megye.str.split().str[0]).size()

    for ag, korzetszam in cfg["forgatokonyvek"].items():
        ki = {"ag": ag, "melleklet1": [], "korzetek": []}
        for megye in ["Budapest", "Pest", "Somogy", "Tolna"]:
            db_ma = int(ma_db[megye])
            db = korzetszam.get(megye, db_ma)
            if db != db_ma:
                ki["melleklet1"].append({"megye": megye, "ma": db_ma, "javaslat": db})
            if megye not in korzetszam:
                continue
            t = pd.read_csv(INTERIM / "javaslat" / f"{megye}_{db}.csv")
            mer = pd.read_csv(INTERIM / "javaslat" / f"{megye}_{db}_meroszam.csv").iloc[0]
            szekhelyek = json.loads(mer.szekhelyek)
            u = e.set_index("unit_id").loc[t.unit_id].assign(regi=t.regi.values, uj=t.uj.values)
            # sorszámozás: a megmaradók eredeti sorrendben, az új a végén; folyamatos számozás
            sorrend = sorted(set(t.uj))
            uj_szam = {k: f"{i + 1:02d}" for i, k in enumerate(sorrend)}
            valtozo = {k for k in sorrend if set(u.index[u.uj == k]) != set(u.index[u.regi == k]) or uj_szam[k] != k[-2:]}
            megszunt = sorted(set(t.regi) - set(t.uj))
            for k in sorrend:
                if k not in valtozo:
                    continue
                tagok = u[u.uj == k]
                v = int(tagok.jogosult_2026.sum())
                sz = szekhelyek.get(k) if k in set(t.regi) else tagok.groupby("nev").jogosult_2026.sum().idxmax()
                sz = re.sub(r"^Budapest (\d+)\. ker(?:ület|\.)$", lambda m_: ROMAI[int(m_.group(1))] + ". kerület", sz)
                rec = {"megye": megye, "oevk": k, "sorszam": uj_szam[k], "regi_sorszam": k[-2:] if k in set(t.regi) else None,
                       "rovidites": f"{megye} {uj_szam[k]}. OEVK", "szekhely": sz,
                       "valaszto": v, "elteres": round(v / A - 1, 4), "tetelek": [], "bizonytalan": [], "cimlistak": []}
                if megye != "Budapest":
                    rec["tetelek"] = sorted(tagok.nev.unique(), key=hu_kulcs)
                else:
                    if utcak is None:
                        utcak = osm_utcak()
                    ma_tetelek = hat.get(("Budapest", k[-2:]), {}).get("tetelek", []) if k in set(t.regi) else []
                    for ker in sorted(tagok.nev.unique(), key=lambda x: int(re.search(r"(\d+)", x).group(1))):
                        sz_ = int(re.search(r"(\d+)", ker).group(1))
                        rom = ROMAI[sz_] + ". kerület"
                        kerulet = u[u.nev == ker]
                        resz = kerulet[kerulet.uj == k]
                        # térképhez: a körzet kerületenkénti területe, a szavazókör-térkép réseit 25 m-es zárással eltüntetve
                        terulet = shapely.make_valid(shapely.union_all(resz.geometry.values).buffer(25).buffer(-25)).simplify(5)
                        tg, tc = wgs([terulet, terulet.representative_point()])
                        rec.setdefault("keruletek", []).append({"nev": rom, "resz": len(resz) < len(kerulet), "g": tg,
                                                                "c": tc["coordinates"][::-1], "valaszto": int(resz.jogosult_2026.sum())})
                        if len(resz) == len(kerulet):
                            rec["tetelek"].append(rom)
                            continue
                        regi_resz = kerulet[kerulet.regi == k]
                        if set(resz.index) == set(regi_resz.index):
                            regi = next((x for x in ma_tetelek if x.startswith(f"A {rom}") or x.startswith(f"Az {rom}")), None)
                            if regi:
                                rec["tetelek"].append(regi + " [változatlan]")
                                continue
                        taz = f"{sz_:03d}"
                        reszben = {i.split("-")[-1] for i in resz.index}
                        cimek = nvi_cimek(taz)
                        tobbi = {i.split("-")[-1] for i in kerulet.index} - reszben
                        hatarutcak = {c[0] for c in cimek if c[4] in reszben} & {c[0] for c in cimek if c[4] in tobbi}
                        K = shapely.union_all(kerulet.geometry.values)
                        P = shapely.make_valid(shapely.union_all(resz.geometry.values).buffer(5).buffer(-5))
                        darabok = sorted((g for g in shapely.get_parts(P) if g.area > 20_000), key=lambda g: -g.area)
                        nevelo = "Az" if rom.split(".")[0] in ("I", "V", "XI") else "A"
                        kn = f"a {rom}" if nevelo == "A" else f"az {rom}"
                        szamlalo = [0]
                        leirasok = [hatarvonal(K, d, kn, utcak, hatarutcak, szamlalo) for d in darabok]
                        szak = [x for lr in leirasok for x in lr[2]]
                        gyanus = shapely.union_all([x["g"] for x in szak if x["nev"] is None] or [shapely.Point()])
                        kornyek = shapely.union_all([d.boundary for d in darabok]).buffer(250)
                        kozeli = utcak[0][utcak[0].intersects(kornyek)].copy()
                        kozeli["geometry"] = kozeli.geometry.intersection(kornyek).simplify(4)
                        kozeli = kozeli[~kozeli.geometry.is_empty].dissolve("name").reset_index()
                        terkep = {"kerulet": wgs([K.simplify(8)])[0], "resz": wgs([d.simplify(4) for d in darabok]),
                                  "szakaszok": [{"nev": (None if x["nev"] is None else "kerülethatár" if x["nev"] == "@hatar"
                                                         else x["nev"].replace("vasút:", "") + (" (vasút)" if x["nev"].startswith("vasút:") else "")),
                                                 "ellenorizendo": x["nev"] is None, "szam": x["szam"], "g": g,
                                                 "c": c["coordinates"][::-1]}
                                                for x, g, c in zip(szak, wgs([x["g"].simplify(2) for x in szak]),
                                                                   wgs([kozep(x["g"]) for x in szak]))],
                                  "utcak": [{"nev": n_, "g": g, "c": c["coordinates"][::-1], "h": round(h)}
                                            for n_, g, c, h in zip(kozeli.name, wgs(kozeli.geometry),
                                                                   wgs([kozep(x) for x in kozeli.geometry]), kozeli.geometry.length)],
                                  "gyanus_m": round(gyanus.length)}
                        if len(leirasok) == 1:
                            szoveg = leirasok[0][0]
                        else:
                            szoveg = " ".join(f"{chr(97 + i)}) {x[0]}" for i, x in enumerate(leirasok))
                        rec["tetelek"].append(f"{nevelo} {rom} választókerülethez tartozó részének határvonala: {szoveg} "
                                              "[TERVEZET]")
                        rec["bizonytalan"].append({"kerulet": rom, "darab": len(darabok),
                                                   "nem_azonositott_m": sum(x[1] for x in leirasok)})
                        rec.setdefault("terkepek", []).append({"kerulet_nev": rom, **terkep})
                        rec["cimlistak"].append({"kerulet": rom, "szavazokorok": sorted(reszben),
                                                 "valaszto": int(resz.jogosult_2026.sum()),
                                                 "cimek": cimlista(cimek, reszben)})
                ki["korzetek"].append(rec)
            for k in megszunt:
                ki["korzetek"].append({"megye": megye, "oevk": k, "megszunik": True,
                                       "szekhely": hat.get((MEGYE_CIM[megye], k[-2:]), {}).get("szekhely")})
        f = KI / f"melleklet_{ag}.json"
        f.write_text(json.dumps(ki, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f, len(ki["korzetek"]), "körzet")


if __name__ == "__main__":
    main()

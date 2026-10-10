"""A Vjt. 1. és 2. mellékletének módosítása a javaslat szerint: szövegtervezet a jogi csapatnak.

A 2. melléklet szerkezetét követi: körzetenként sorszám, rövidítés, székhely, terület (vidéken
településlista ábécérendben; Budapesten egész kerületek és kerületrészek határvonala). Csak a
változó körzetek kerülnek bele; a változatlan kerületrészek szövegét a hatályos mellékletből veszi át.

A budapesti kerületrészek határvonalát a program az egységek (szavazókörök) határából és az OSM
utcatengelyeiből állítja össze; ahol ez pontatlan, a kézi szöveg (data/manual/melleklet_kezi.yaml) kerül
be. A csapatoldalhoz minden kerületrész-tételhez térképes jelölés is készül: a szövegben említett utcák a
rész határa mentén, a kerülethatár és a záró mondatok házszámai (`jelolesek`, `kornyezet`).

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
import shapely.ops
from shapely.geometry import Point
from shapely.geometry.polygon import orient

import yaml

from .adat import EOV, GYOKER, INTERIM, RAW, config, nvi_oevk, vtr_mappa

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
            akt = ki.setdefault((megye, m.group(1)), {"szekhely": None, "rovidites": None, "tetelek": []})
            continue
        if akt is None:
            continue
        if x.startswith("Rövidítése:"):
            akt["rovidites"] = x.split(":", 1)[1].strip()
        elif x.startswith("Székhelye:") or x.startswith("Székhely:"):  # Zala 02.: „Székhely:”
            akt["szekhely"] = x.split(":", 1)[1].strip()
        elif re.match(r"^\d+[a-z]?\. ", x):  # a beszúrt tételek „9a.” sorszámúak
            t = re.sub(r"^\d+[a-z]?\. ", "", x).rstrip(";").strip()
            if t != "Területe:":  # a net.jogtár egy helyen a „Területe:” sort is beszámozza
                akt["tetelek"].append(t)
        elif "választókerülethez tartozó" in x:  # Szeged, Debrecen, Nyíregyháza: egyetlen, számozatlan tétel
            akt["tetelek"].append(x)
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


# ---------- a csapatoldal térképes jelölései ----------

def osm_keruletek():
    """Budapest kerületei (OSM admin_level 9), EOV-ben: {„X. kerület”: poligon}."""
    f = (RAW / "osm" / "hungary-latest.osm.pbf").as_posix()
    d = pyogrio.read_dataframe(f, layer="multipolygons", columns=["name"], bbox=(18.90, 47.33, 19.35, 47.62),
                               where="boundary='administrative' AND admin_level='9'").to_crs(EOV)
    return dict(zip(d.name, d.geometry))


def osm_cimek(poli):
    """A poligonon belüli házszámos OSM-címek (épületek és pontok): utca, házszám, geometria (pont)."""
    f = (RAW / "osm" / "hungary-latest.osm.pbf").as_posix()
    bb = tuple(gpd.GeoSeries([poli], crs=EOV).to_crs(4326).total_bounds)
    reszek = []
    for layer in ("multipolygons", "points"):
        d = pyogrio.read_dataframe(f, layer=layer, columns=["other_tags"], bbox=bb,
                                   where="other_tags LIKE '%addr:housenumber%'").to_crs(EOV)
        d["geometry"] = d.geometry.representative_point() if layer == "multipolygons" else d.geometry
        reszek.append(d)
    d = pd.concat(reszek)
    cimke = lambda s, k: (re.search(r'"%s"=>"([^"]*)"' % re.escape(k), s or "") or [None, None])[1]
    d["utca"] = d.other_tags.map(lambda s: cimke(s, "addr:street"))
    d["hsz"] = d.other_tags.map(lambda s: cimke(s, "addr:housenumber"))
    d = d.dropna(subset=["utca", "hsz"])
    return d[d.within(poli)][["utca", "hsz", "geometry"]]


def nevformak(nev, szoveg):
    """A közterület nevének ragozott alakjai a szövegben („Mádi utcáig”, „Sibrik Miklós úti”)."""
    szavak = nev.split()
    if len(szavak) < 2:
        return []
    tipus = szavak[-1]
    to = tipus[:-1] if tipus[-1] in "aeő" else tipus  # utca -> utcá-ig, lejtő -> lejtő-ig
    minta = r"(?<!\w)" + r"\s".join(re.escape(x) for x in szavak[:-1]) + r"\s" + re.escape(to) + r"\w*"
    return sorted(set(re.findall(minta, szoveg)), key=len, reverse=True)


def utca_graf(geom):
    """Egy utca vonalaiból gráf; a szétszakadt darabokat (pl. téren megszakadó utca) a legközelebbi
    pontpárral köti össze."""
    import networkx as nx
    g = nx.Graph()
    for l in shapely.get_parts(geom):
        c = list(l.coords)
        for a, b in zip(c[:-1], c[1:]):
            g.add_edge(a, b, w=Point(a).distance(Point(b)))
    cc = [list(x) for x in nx.connected_components(g)]
    while len(cc) > 1:
        a = np.array(cc[0]); best = None
        for i, o in enumerate(cc[1:], 1):
            b = np.array(o); d = np.sqrt(((a[:, None, :] - b[None, :, :]) ** 2).sum(-1)); k = np.unravel_index(d.argmin(), d.shape)
            if best is None or d[k] < best[0]:
                best = (d[k], tuple(a[k[0]]), tuple(b[k[1]]), i)
        g.add_edge(best[1], best[2], w=best[0])
        cc[0] += cc.pop(best[3])
    return g


def szakasz(geom, p, q):
    """Az utca p és q pont közötti része a gráf legrövidebb útja mentén."""
    import networkx as nx
    g = utca_graf(geom)
    n = list(g.nodes)
    cs = lambda x: n[int(np.argmin([Point(y).distance(x) for y in n]))]
    ut = nx.shortest_path(g, cs(p), cs(q), weight="w")
    return shapely.LineString([p.coords[0], *ut, q.coords[0]])


def metszes(a, b, kozel):
    """Két vonal metszéspontjai közül a `kozel` geometriához legközelebbi (ha nem metszik, a legközelebbi pontpár)."""
    m = a.intersection(b)
    pts = [x for x in shapely.get_parts(m) if x.geom_type == "Point"] if not m.is_empty else []
    if not pts:
        return shapely.ops.nearest_points(a, b)[0]
    return min(pts, key=lambda x: x.distance(kozel))


def szoveg_szakaszok(szoveg, geomok, kerulet_poli, resz_poli):
    """A határvonal mondataiból („a Mádi utca tengelyvonala a Tavas utcáig”) utcánként a hivatkozott
    szakasz: az előző és a következő említett utca (vagy a kerülethatár) metszéspontja között."""
    elo = sorted((m.start(), m.end(), nev, forma) for nev in geomok for forma in nevformak(nev, szoveg)
                 for m in re.finditer(r"(?<!\w)" + re.escape(forma) + r"(?!\w)", szoveg))
    elo = [x for i, x in enumerate(elo) if not any(y[0] <= x[0] < y[1] and y != x for y in elo[:i])]  # átfedők ki
    ki, elozo = {}, None
    for i, (a, b, nev, forma) in enumerate(elo):
        utana = szoveg[b:b + 25]
        if not re.match(r"\s(?:út\s)?tengelyvonala\b", utana):
            continue
        # honnan: az előző szakasz utcája; az első szakasznál a kiinduló mondat másik utcája vagy a kerülethatár
        honnan = elozo
        if honnan is None:
            elotte = [x[2] for x in elo[:i] if x[2] != nev]
            honnan = "@hatar" if "határvonal" in szoveg[szoveg.find(": ") + 2:a] or not elotte else elotte[0]  # a „…határvonala:” fejrész után
        # hova: a következő, más utcára vonatkozó említés, vagy a kerülethatár, ha előbb az jön
        kov = next(((x[0], x[2]) for x in elo[i + 1:] if x[2] != nev), (len(szoveg), None))
        hatar_poz = szoveg.find("határvonal", b)
        hova = "@hatar" if hatar_poz != -1 and hatar_poz < kov[0] and hatar_poz - b < 160 else kov[1]
        elozo = nev
        if hova is None:
            continue
        g = geomok[nev]
        cel = lambda x, p0=None: (metszes(g, kerulet_poli.boundary, resz_poli.boundary if p0 is None else p0) if x == "@hatar"
                                  else metszes(g, geomok[x], resz_poli.boundary))
        try:
            p = cel(honnan); q = cel(hova, p if hova == "@hatar" else None)
            if hova == "@hatar":  # a határ több helyen is metszheti: a p-hez az utcán legközelebbi
                m = g.intersection(kerulet_poli.boundary)
                jel = [x for x in shapely.get_parts(m) if x.geom_type == "Point"] or [q]
                q = min(jel, key=lambda x: szakasz(g, p, x).length)
            ki.setdefault(nev, []).append(szakasz(g, p, q))
        except Exception:
            continue
    return {n: shapely.union_all(v) for n, v in ki.items()}


def jeloles(szoveg, rom, resz_poli, utcak, kerulet_poli, hazszamok, cimek):
    """Egy kerületrész-tétel térképes jelölései: a szövegben említett utcák hivatkozott szakasza (ahol a
    mondatból nem határozható meg, a rész határa menti 150 m-es sáv), a kerülethatár érintett szakasza és a
    záró mondat házszámai."""
    sav = resz_poli.boundary.buffer(150)
    ki = {"kerulet": rom, "utcak": [], "hatar": None, "pontok": []}
    kozel = resz_poli.buffer(600)
    jelolt = utcak[utcak.name.isin({n for n in utcak.name.unique() if nevformak(n, szoveg)}) & utcak.intersects(kozel)]
    geomok = {n: shapely.line_merge(shapely.union_all(g.geometry.values).intersection(kozel)) for n, g in jelolt.groupby("name")}
    pontos = szoveg_szakaszok(szoveg, geomok, kerulet_poli, resz_poli) if kerulet_poli is not None else {}
    for nev, g in jelolt.groupby("name"):
        geom = pontos.get(nev)
        if geom is None or geom.length < 30:  # a mondatból nem határozható meg: a rész határa menti sáv
            geom = shapely.union_all(g.geometry.values).intersection(sav)
        if geom.is_empty or geom.length < 20:  # a szavazókör-térkép a lakatlan részt nem fedi: szélesebb sáv
            geom = shapely.union_all(g.geometry.values).intersection(resz_poli.boundary.buffer(400))
        if geom.is_empty or geom.length < 20:
            continue
        geom = shapely.line_merge(geom).simplify(3)
        gg, c = wgs([geom, kozep(geom)])
        ki["utcak"].append({"nev": nev, "formak": nevformak(nev, szoveg), "g": gg, "c": c["coordinates"][::-1]})
    hatar_formak = sorted(set(re.findall(re.escape(rom) + r"\shatárvonal\w*", szoveg)), key=len, reverse=True)
    if hatar_formak and kerulet_poli is not None:
        hg = kerulet_poli.boundary.intersection(resz_poli.buffer(150))
        if not hg.is_empty:
            ki["hatar"] = {"formak": hatar_formak, "g": wgs([hg.simplify(3)])[0]}
    belso = resz_poli.boundary if kerulet_poli is None else resz_poli.boundary.difference(kerulet_poli.boundary.buffer(60))
    volt = set()
    for utca, k, z, oldal, korzet in hazszamok:
        for r in cimek[cimek.utca == utca].itertuples():
            m = re.match(r"(\d+)", r.hsz)
            if not m:
                continue
            h = int(m.group(1))
            if h < k or (z is not None and h > z) or (oldal == "páros" and h % 2) or (oldal == "páratlan" and not h % 2):
                continue
            if r.geometry.distance(belso) > 150 or f"{utca} {r.hsz}" in volt:  # csak az új határ mentén, egyszer
                continue
            volt.add(f"{utca} {r.hsz}")
            ki["pontok"].append({"t": f"{utca} {r.hsz}", "k": korzet, "c": wgs([r.geometry])[0]["coordinates"][::-1]})
    ki["_vonal"] = shapely.union_all(list(pontos.values())) if pontos else None  # a térképi területhez (nem kerül a json-ba)
    return ki


def jogi_terulet(parok, keruletek_osm):
    """A kézi leírású kerületrészek térképi területe a leírt határvonal szerint, nem a szavazókör-térkép
    szerint (az csak közelítő, és az utcán átlóg). A kisebbik rész a kerülethatár és a mondatokból számolt
    szakaszok által közrezárt terület; a párja a saját szavazókör-területe ettől megtisztítva. A záró mondatok
    házszámai a térképen pontként látszanak."""
    for rom, lista in parok.items():
        K = keruletek_osm.get(rom)
        if K is None or len(lista) != 2:
            continue
        jelolt = []
        for i, (rec, ki_, jel, U) in enumerate(lista):
            v = jel.get("_vonal")
            if v is None or v.is_empty:
                continue
            darabok = [v]
            for l in shapely.get_parts(shapely.line_merge(v)):  # a vonalvégek ráhúzása a kerülethatárra
                for vp in (Point(l.coords[0]), Point(l.coords[-1])):
                    if 0 < vp.distance(K.boundary) < 60:
                        darabok.append(shapely.LineString([vp, shapely.ops.nearest_points(vp, K.boundary)[1]]))
            lapok = [f for f in shapely.get_parts(shapely.polygonize([shapely.union_all([K.boundary, *darabok])]))
                     if f.representative_point().within(K)]
            P = shapely.union_all([f for f in lapok if f.intersection(U).area > 0.5 * f.area] or [shapely.Polygon()])
            if not P.is_empty and 0.6 < P.area / U.area < 1.5 and P.area < 0.8 * K.area:
                jelolt.append((P.area, i, P))
        if not jelolt:
            continue
        _, i, P = min(jelolt)
        print(f"  {rom}: a {lista[i][0]['oevk']} része a leírt vonal szerint, {P.area / 1e4:.0f} ha (szavazókör-térkép: {lista[i][3].area / 1e4:.0f} ha)")
        for j, (rec, ki_, jel, U) in enumerate(lista):
            # a pár: a saját szavazókör-területe, a vonalig kitöltve (a szavazókör-térkép a vonal mentén réses lehet)
            g = P if j == i else U.union(P.buffer(40).difference(P).intersection(U.buffer(60)).intersection(K)).difference(P.buffer(1))
            g = shapely.make_valid(g).simplify(4)
            gg, c = wgs([g, g.representative_point()])
            rec["keruletek"][ki_].update({"g": gg, "c": c["coordinates"][::-1]})


def kornyezet(poligonok, utcak):
    """A kerületrészek határa körüli (250 m) többi utca, halványan a térkép alapjához."""
    zona = shapely.union_all([p.boundary.buffer(250) for p in poligonok])
    k = utcak[utcak.intersects(zona)].copy()
    k["geometry"] = k.geometry.intersection(zona).simplify(4)
    k = k[~k.geometry.is_empty].dissolve("name").reset_index()
    return [{"nev": n, "g": g, "c": c["coordinates"][::-1], "h": round(h)}
            for n, g, c, h in zip(k.name, wgs(k.geometry), wgs([kozep(x) for x in k.geometry]), k.geometry.length)]


# ---------- egységes szerkezetű mellékletek ----------

def egyseges(ki, hat, o, korzetszam):
    """A módosított 1. és 2. melléklet teljes szövege: a változó körzetek a javaslatból, a többi a hatályos
    szövegből. Körzetenként „allapot”: változatlan / módosul / új (az utóbbi kettő jelölést kap)."""
    megyek = list(dict.fromkeys(m for m, _ in hat))  # a hatályos melléklet sorrendje
    ma_db = {m: sum(1 for x, _ in hat if x == m) for m in megyek}
    m1 = [{"megye": m.replace(" megye", ""), "ma": ma_db[m],
           "javaslat": korzetszam.get(m.replace(" megye", ""), ma_db[m])} for m in megyek]
    m2 = []
    for m in megyek:
        uj = [k for k in ki["korzetek"] if MEGYE_CIM[k["megye"]] == m and not k.get("megszunik")]
        megszunt = {k["oevk"][-2:] for k in ki["korzetek"] if MEGYE_CIM[k["megye"]] == m and k.get("megszunik")}
        modosult = {k["regi_sorszam"] for k in uj if k["regi_sorszam"]}
        lista = {}
        for (mg, s), x in hat.items():
            if mg == m and s not in modosult and s not in megszunt:
                lista[s] = {"sorszam": s, "rovidites": x["rovidites"], "szekhely": x["szekhely"],
                            "tetelek": x["tetelek"], "allapot": "változatlan"}
        for k in uj:
            assert k["sorszam"] not in lista, (m, k["sorszam"])
            lista[k["sorszam"]] = {"sorszam": k["sorszam"], "rovidites": k["rovidites"], "szekhely": k["szekhely"],
                                   "tetelek": [re.sub(r" \[(változatlan|TERVEZET)\]$", "", t) for t in k["tetelek"]],
                                   "allapot": "új" if not k["regi_sorszam"] else "módosul", "regi_sorszam": k["regi_sorszam"],
                                   "valaszto": k["valaszto"], "elteres": k["elteres"]}
        db = next(x["javaslat"] for x in m1 if x["megye"] == m.replace(" megye", ""))
        assert sorted(lista) == [f"{i + 1:02d}" for i in range(db)], (m, sorted(lista))
        m2.append({"megye": m, "korzetek": [lista[s] for s in sorted(lista)]})
    return {"melleklet1": m1, "melleklet2": m2}


# ---------- összeállítás ----------

def main():
    cfg = config()
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    e = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")
    e["geometry"] = e.geometry.buffer(0)
    hat = hatalyos_melleklet()
    kezi = yaml.safe_load((GYOKER / "data" / "manual" / "melleklet_kezi.yaml").read_text(encoding="utf-8"))
    utcak = None
    keruletek_osm, cim_tar = None, {}
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
            kezi_par = {}
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
                    reszpoli = []
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
                        szoveg = None
                        if set(resz.index) == set(regi_resz.index):
                            regi = next((x for x in ma_tetelek if x.startswith(f"A {rom}") or x.startswith(f"Az {rom}")), None)
                            if regi:
                                szoveg, jel = regi, " [változatlan]"
                        if szoveg is None and f"{k}|{rom}" in kezi:  # kézi megfogalmazás (határvonal, kivételek)
                            szoveg, jel = kezi[f"{k}|{rom}"], ""
                        if szoveg is not None:
                            if keruletek_osm is None:
                                keruletek_osm = osm_keruletek()
                            hsz_ = kezi.get("_hazszamok", {}).get(rom, [])
                            if hsz_ and rom not in cim_tar:
                                cim_tar[rom] = osm_cimek(keruletek_osm[rom].buffer(200))
                            rec.setdefault("jelolesek", []).append(
                                {"tetel": len(rec["tetelek"]), **jeloles(szoveg, rom, terulet, utcak[0], keruletek_osm.get(rom),
                                                                         hsz_, cim_tar.get(rom))})
                            if not jel:  # kézi leírás: a térképi terület majd a leírt vonalból (jogi_terulet)
                                kezi_par.setdefault(rom, []).append((rec, len(rec["keruletek"]) - 1, rec["jelolesek"][-1], terulet))
                            reszpoli.append(terulet)
                            rec["tetelek"].append(szoveg + jel)
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
                    if reszpoli:
                        rec["kornyezet"] = kornyezet(reszpoli, utcak[0])
                ki["korzetek"].append(rec)
            if megye == "Budapest":
                jogi_terulet(kezi_par, keruletek_osm or {})
                for r_ in ki["korzetek"]:
                    for j_ in r_.get("jelolesek", []):
                        j_.pop("_vonal", None)
            for k in megszunt:
                ki["korzetek"].append({"megye": megye, "oevk": k, "megszunik": True,
                                       "szekhely": hat.get((MEGYE_CIM[megye], k[-2:]), {}).get("szekhely")})
        ki["egyseges"] = egyseges(ki, hat, o, korzetszam)
        f = KI / f"melleklet_{ag}.json"
        f.write_text(json.dumps(ki, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f, len(ki["korzetek"]), "körzet")


if __name__ == "__main__":
    main()

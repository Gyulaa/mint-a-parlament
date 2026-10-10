"""Közös útvonalak, konfiguráció és nyersadat-betöltők."""

import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml
from shapely.geometry import Point, Polygon

GYOKER = Path(__file__).resolve().parents[1]
RAW = GYOKER / "data" / "raw"
INTERIM = GYOKER / "data" / "interim"
EOV = "EPSG:23700"
WGS84 = "EPSG:4326"


@lru_cache
def config():
    return yaml.safe_load((GYOKER / "config.yaml").read_text(encoding="utf-8"))


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@lru_cache
def vtr_mappa(valasztas):
    """A VTR-verziómappák: {'ver': Path, 'szavossz': Path}."""
    alap = RAW / "nvi" / valasztas
    cfg = _json(alap / "config.json")
    return {"ver": alap / cfg["ver"] / "ver", "szavossz": alap / cfg["szavossz"] / "szavossz"}


def nev_kulcs(nev):
    """Névillesztési kulcs: kisbetű, egységes kerületnév, szóközök nélkül."""
    nev = str(nev).strip().lower()
    nev = re.sub(r"\bkerület\b|\bker\.", "ker", nev)
    return re.sub(r"[\s.]+", "", nev)


def nvi_megyek(valasztas="ogy2026"):
    """maz -> megyenév (a KSH helységnévtár írásmódjával: Budapestnél 'főváros')."""
    lista = _json(vtr_mappa(valasztas)["ver"] / "Megyek.json")["list"]
    lista = [m.get("leiro", m) for m in lista]
    return {m["maz"]: ("főváros" if m["maz"] == "01" else m["nev"])
            for m in lista}


def nvi_telepulesek(valasztas="ogy2026"):
    """Települések NVI-kóddal, jelenlegi OEVK-listával és létszámmal."""
    sorok = []
    for t in _json(vtr_mappa(valasztas)["ver"] / "Telepulesek.json")["list"]:
        leiro = t.get("leiro", t)
        sorok.append({
            "maz": leiro["maz"], "taz": leiro["taz"], "nvi_nev": leiro["megnev"],
            "evk_lst": list(leiro["evk_lst"]), "szk_db": leiro["szk_db"],
            "indulo": t["letszam"]["indulo"], "osszesen": t["letszam"]["osszesen"],
        })
    return pd.DataFrame(sorok)


def nvi_szavazokorok(valasztas="ogy2026"):
    sorok = []
    for f in sorted(vtr_mappa(valasztas)["ver"].glob("*/Szavazokorok-*.json")):
        d = _json(f)["data"]
        for s in d["szavazokorok"]:
            l = s["leiro"]
            sorok.append({
                "maz": d["maz"], "taz": d["taz"], "szk": l["sorszam"], "evk": l["evk"],
                "atj_kijelolt": l.get("atjKijelolt") == "I", "kozter": l.get("kozter"),
                "indulo": s["letszam"]["indulo"], "osszesen": s["letszam"]["osszesen"],
            })
    return pd.DataFrame(sorok)


def latlon_poligon(szoveg):
    """A VTR 'lat lon,lat lon,...' formátumú poligonja (WGS84)."""
    pontok = [tuple(map(float, p.split())) for p in szoveg.split(",") if p.strip()]
    if len(set(pontok)) < 3:  # az átjelentkezési szavazóköröknek nincs valódi területe
        return None
    return Polygon([(lon, lat) for lat, lon in pontok])


def nvi_szavkor_topo(maz, taz, valasztas="ogy2026"):
    """(szavazókör, poligon vagy None, középpont) hármasok, WGS84-ben."""
    f = vtr_mappa(valasztas)["ver"] / maz / f"Szavkor-Topo-{maz}-{taz}.json"
    ki = []
    for p in _json(f)["list"]:
        lat, lon = map(float, p["centrum"].split()) if p.get("centrum") else (None, None)
        ki.append((p["szk"], latlon_poligon(p.get("poligon") or ""), Point(lon, lat) if lat else None))
    return ki


def nvi_oevk(valasztas="ogy2026"):
    sorok = []
    for o in _json(vtr_mappa(valasztas)["ver"] / "OevkAdatok.json")["list"]:
        sorok.append({"oevk": f"{o['maz']}-{o['evk']}", "maz": o["maz"], "megye": o["maz_nev"],
                      "szekhely": o["szekhely"], "indulo": o["letszam"]["indulo"],
                      "osszesen": o["letszam"]["osszesen"]})
    return pd.DataFrame(sorok)


def lechner_telepulesek():
    import geopandas as gpd
    g = gpd.read_file("zip://" + (RAW / "lechner" / "AdministrativeUnits2025.zip").as_posix()
                      + "!AU.AdministrativeUnits.2025.shp")
    g = g[g.desn == "Település"].copy()
    g["ksh_kod"] = g.nuts_code.str[-5:]
    return g[["ksh_kod", "namn", "pop_sum", "geometry"]].rename(columns={"namn": "lechner_nev"})


def ksh_helysegnevtar():
    h = pd.read_excel(RAW / "ksh" / "hnt_letoltes_2026.xlsx", sheet_name=0, header=2, dtype=str)
    h = h.rename(columns={
        "Helység megnevezése": "nev", "Helység KSH kódja": "ksh_kod", "Helység jogállása": "jogallas",
        "Megye megnevezése": "megye", "Járás neve": "jaras", "Járás székhelye": "jaras_szekhely",
    })
    h = h[h.ksh_kod.notna() & h.megye.notna()].copy()
    nemz = [c for c in h.columns if "Nemzetiségi" in str(c) or c.strip().endswith(("  ",))]
    return h, nemz


def ksh_nemzetiseg():
    """2022-es népszámlálás (WBS003), 'nemzetiséghez tartozás az összes kérdés alapján' oszlopok.

    Megye + településnév szerint; a '…' (adatvédelmi okból elnyomott) érték NaN.
    """
    sorok = []
    for f in sorted((RAW / "ksh").glob("2022-nemzetiseg-*.xlsx")):
        df = pd.read_excel(f, sheet_name="Adattábla", header=None)
        fejlec = list(df.iloc[1])
        # az első blokk az "összes kérdés alapján" bontás: az összesen-oszloptól (a népesség) a
        # 'Nemzetiség' fejlécig (ha a második blokk is le van töltve), egyébként a sor végéig
        osszes = "Nemzetiséghez tartozás az összes kérdés alapján"
        if osszes not in fejlec:
            raise ValueError(f"{f.name}: hiányzik a(z) '{osszes}' oszlop (a település népessége, az arányok "
                             "nevezője); a KSH-lekérdezésben a nemzetiségi jellemzők összesen-sorát is ki kell jelölni")
        eleje = fejlec.index(osszes)
        vege = fejlec.index("Nemzetiség") if "Nemzetiség" in fejlec else len(fejlec)
        oszlopok = {i: fejlec[i] for i in range(eleje, vege)}
        megye = None
        for _, r in df.iloc[2:].iterrows():
            nev = r[1]
            if not isinstance(nev, str) or not nev.strip():
                continue
            if nev == "Budapest" or nev.endswith("vármegye"):
                megye = "főváros" if nev == "Budapest" else nev.removesuffix(" vármegye")
                continue
            if nev.endswith("járás"):
                continue
            sor = {"megye": megye, "nev": nev}
            for i, o in oszlopok.items():
                sor[o] = pd.to_numeric(r[i], errors="coerce")
            sorok.append(sor)
    df = pd.DataFrame(sorok).drop_duplicates(["megye", "nev"])
    rovid = {c: "nemz_" + nev_kulcs(c.split(" nemzetiséghez")[0]).replace("(roma)", "")
             for c in df.columns if "nemzetiséghez tartozó" in c}
    rovid["Nemzetiséghez tartozás az összes kérdés alapján"] = "nep_2022"
    return df.rename(columns=rovid)

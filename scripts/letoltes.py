"""Nyers adatok letöltése a data/raw/ alá.

Minden fájl érintetlenül, a forrás útvonalát követve kerül le; a data/manifest/
alatti CSV-k rögzítik az URL-t, a méretet és az SHA-256-ot, így a futás
visszakövethető. A már letöltött fájlokat nem tölti le újra (--ujra felülírja).

Használat:
    python scripts/letoltes.py nvi            # VTR ogy2026 + ogy2022
    python scripts/letoltes.py nyilt          # Lechner, KSH, jogszabályszöveg
    python scripts/letoltes.py mind
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

GYOKER = Path(__file__).resolve().parents[1]
RAW = GYOKER / "data" / "raw"
MANIFEST = GYOKER / "data" / "manifest"
VTR = "https://vtr.valasztas.hu"
FEJLEC = {"User-Agent": "mint-a-parlament adatletolto (oktatasi projekt)"}
OEVK_SZAM = 106

# Egyedi fájlok: (csoport, URL, cél a data/raw/ alatt)
NYILT_FORRASOK = [
    ("lechner", "https://inspire.lechnerkozpont.hu/inspire/atom/data/AdministrativeUnits2025.zip",
     "lechner/AdministrativeUnits2025.zip"),
    ("lechner", "https://inspire.lechnerkozpont.hu/inspire/hydrography/waterways_poly.zip",
     "lechner/waterways_poly.zip"),
    ("lechner", "https://inspire.lechnerkozpont.hu/inspire/transportation/road_network.zip",
     "lechner/road_network.zip"),
    ("ksh", "https://www.ksh.hu/docs/helysegnevtar/hnt_letoltes_2026.xlsx",
     "ksh/hnt_letoltes_2026.xlsx"),
    ("jog", "https://www.parlament.hu/irom42/09433/09433.pdf",
     "jog/T09433_torvenyjavaslat_2024.pdf"),
    ("jog", "https://net.jogtar.hu/jogszabaly?docid=a1100203.tv",
     "jog/vjt_net_jogtar.html"),
]


def munkamenet():
    s = requests.Session()
    s.headers.update(FEJLEC)
    ujra = Retry(total=5, backoff_factor=1.0, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=ujra, pool_maxsize=8))
    return s


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blokk in iter(lambda: f.read(1 << 20), b""):
            h.update(blokk)
    return h.hexdigest()


def letolt(s, url, cel, ujra=False, varakozas=0.0):
    """Letölt egy fájlt; visszaad egy manifest-sort (404-nél is, 'hianyzik' állapottal)."""
    cel = RAW / cel
    if cel.exists() and cel.stat().st_size > 0 and not ujra:
        allapot = "megvolt"
    else:
        time.sleep(varakozas)
        r = s.get(url, stream=True, timeout=120)
        if r.status_code == 404:
            return {"url": url, "fajl": "", "meret": 0, "sha256": "", "allapot": "hianyzik"}
        r.raise_for_status()
        cel.parent.mkdir(parents=True, exist_ok=True)
        tmp = cel.with_name(cel.name + ".tmp")
        with open(tmp, "wb") as f:
            for blokk in r.iter_content(1 << 16):
                f.write(blokk)
        tmp.replace(cel)
        allapot = "letoltve"
    return {"url": url, "fajl": cel.relative_to(RAW).as_posix(), "meret": cel.stat().st_size,
            "sha256": sha256(cel), "allapot": allapot}


def manifest_ir(nev, sorok):
    MANIFEST.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST / f"{nev}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["url", "fajl", "meret", "sha256", "allapot"])
        w.writeheader()
        w.writerows(sorted(sorok, key=lambda r: r["url"]))
    hiany = [r["url"] for r in sorok if r["allapot"] == "hianyzik"]
    print(f"{nev}: {len(sorok)} fájl, ebből {len(hiany)} hiányzik (404)")
    for u in hiany[:20]:
        print("   hiányzik:", u)


def telepules_lista(path):
    """maz, taz, indulo hármasok; a 2026-os (leiro/letszam) és a 2022-es (lapos) formát is kezeli."""
    adat = json.loads(path.read_text(encoding="utf-8"))["list"]
    for t in adat:
        leiro = t.get("leiro", t)
        yield leiro["maz"], leiro["taz"], t["letszam"]["indulo"]


def nvi(valasztas, s, ujra, workers, reszletes):
    """Egy választás VTR-adatai. reszletes=True: a megosztható egységek utcahatár- és címlistája is."""
    alap = f"{VTR}/{valasztas}/data"
    cel_alap = f"nvi/{valasztas}"
    sorok = [letolt(s, f"{alap}/config.json", f"{cel_alap}/config.json", ujra=True)]
    cfg = json.loads((RAW / cel_alap / "config.json").read_text(encoding="utf-8"))
    ver, szo = cfg["ver"], cfg["szavossz"]
    print(f"{valasztas}: ver={ver}, szavossz={szo}")

    def ut(verzio, relativ):
        return f"{alap}/{verzio}/{relativ}", f"{cel_alap}/{verzio}/{relativ}"

    orszagos = [ut(ver, f"ver/{n}.json") for n in
                ("Telepulesek", "OevkAdatok", "OevkPoligonok", "Megyek", "OsszLetszam", "Kodtablak")]
    orszagos += [ut(szo, f"szavossz/{n}.json") for n in ("OevkJkv", "ListasJkv", "LevelJkv")]
    sorok += [letolt(s, u, c, ujra) for u, c in orszagos]

    telepulesek = list(telepules_lista(RAW / cel_alap / ver / "ver" / "Telepulesek.json"))
    atlag = sum(t[2] for t in telepulesek) / OEVK_SZAM
    feladatok = [ut(ver, f"ver/{maz}/Telep-Topo-{maz}.json") for maz in sorted({t[0] for t in telepulesek})]
    for maz, taz, indulo in telepulesek:
        feladatok += [
            ut(ver, f"ver/{maz}/Szavazokorok-{maz}-{taz}.json"),
            ut(ver, f"ver/{maz}/Szavkor-Topo-{maz}-{taz}.json"),
            ut(szo, f"szavossz/{maz}/SzavkorJkv-{maz}-{taz}.json"),
        ]
        # Vjt. 4. § (3): csak fővárosi kerület vagy átlag feletti település osztható meg
        if reszletes and (maz == "01" or indulo > atlag):
            feladatok += [
                ut(ver, f"ver/{maz}/Korzethatar-{maz}-{taz}.json"),
                ut(ver, f"ver/{maz}/SzavkorKereso-{maz}-{taz}.json"),
            ]
    print(f"{valasztas}: {len(telepulesek)} település, {len(feladatok)} fájl")

    kesz = 0

    def egy(f):
        nonlocal kesz
        sor = letolt(s, *f, ujra=ujra, varakozas=0.1)
        kesz += 1
        if kesz % 500 == 0:
            print(f"   {kesz}/{len(feladatok)}", flush=True)
        return sor

    with ThreadPoolExecutor(max_workers=workers) as ex:
        sorok += list(ex.map(egy, feladatok))
    manifest_ir(f"nvi_{valasztas}", sorok)


def nyilt(s, ujra):
    sorok = []
    for csoport, url, cel in NYILT_FORRASOK:
        print(f"{csoport}: {url}", flush=True)
        sorok.append(letolt(s, url, cel, ujra))
    manifest_ir("nyilt", sorok)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mit", choices=["nvi", "nyilt", "mind"])
    p.add_argument("--ujra", action="store_true", help="a meglévő fájlokat is újra letölti")
    p.add_argument("--workers", type=int, default=3, help="párhuzamos letöltések (légy kíméletes)")
    a = p.parse_args()
    s = munkamenet()
    if a.mit in ("nvi", "mind"):
        nvi("ogy2026", s, a.ujra, a.workers, reszletes=True)
        nvi("ogy2022", s, a.ujra, a.workers, reszletes=False)
    if a.mit in ("nyilt", "mind"):
        nyilt(s, a.ujra)


if __name__ == "__main__":
    sys.exit(main())

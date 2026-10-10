"""A tömörségi súlyok kalibrálása: próbaesetek megoldása egy beállítással, térképpel.

Egy futás egy esetet old meg egy (tűrés, hess, kappa, beta, mag) beállítással, és PNG-térképet
rajzol (data/interim/kalibral/), a címben a mérőszámokkal: áthelyezett választók, új határ,
a választók átlagos távolsága a körzetközépponttól, Polsby–Popper tömörség, eltérés. Az
eredménysor a <név>.csv fájlba kerül, így több futás párhuzamosan indítható.

Futtatás: python -m oevk.kalibral <eset> [--tures 0.15] [--hess 1] [--kappa 0] [--beta 2000]
          [--mag auto|auto<i>|ker<NN>] [--ido 120]
"""

import argparse
import math

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .adat import INTERIM, config, nvi_oevk  # noqa: E402
from .modell import Megye, adatok, megye_nev_ksh  # noqa: E402

ESETEK = {
    "somogy": ("Somogy", 3, 0.1173, "megszunik", "15-03"),
    "bacs": ("Bács-Kiskun", 6, 0.086, None, None),
    "budapest": ("Budapest", 17, 0.10, "uj", None),
    "tolna": ("Tolna", 2, 0.187, "megszunik", "17-02"),
    "somogy4": ("Somogy", 4, 0.20, None, None),
    "pest": ("Pest", 15, 0.10, "uj", None),
}
KI = INTERIM / "kalibral"
SZINEK = ["#4e79a7", "#f28e2b", "#59a14f", "#b07aa1", "#e3b93c", "#76b7b2", "#e15759", "#9c755f", "#8f9b3a",
          "#1f3b73", "#ffbe7d", "#2f6b2a", "#e6a8d7", "#7a5c00", "#b8e0dc", "#ff9d9a", "#d4b9a6", "#555555",
          "#a0cbe8", "#c9b200"]


def polsby_popper(geo, x):
    d = geo.assign(k=x).dissolve("k")
    pp = 4 * math.pi * d.area / d.length ** 2
    return float(pp.mean()), float(pp.min())


def rajzol(geo, x, regi, cim, fajl, pontok=()):
    korok = sorted(set(x) | set(regi))
    szin = {k: SZINEK[i % len(SZINEK)] for i, k in enumerate(korok)}
    fig, ax = plt.subplots(figsize=(9, 8))
    geo.plot(ax=ax, color=[szin[k] for k in x], edgecolor="white", linewidth=0.2)
    tiszta = lambda d: d.geometry.buffer(2).buffer(-2)  # noqa: E731  (hajszálrések)
    tiszta(geo.assign(k=x).dissolve("k")).boundary.plot(ax=ax, color="black", linewidth=1.4)
    tiszta(geo.assign(k=regi).dissolve("k")).boundary.plot(ax=ax, color="black", linewidth=0.8, linestyle=(0, (3, 3)), alpha=0.6)
    mozdul = geo[[a != b for a, b in zip(x, regi)]]
    if len(mozdul):
        mozdul.boundary.plot(ax=ax, color="red", linewidth=0.6)
    for px, py in pontok:
        ax.plot(px * 1000, py * 1000, marker="*", color="black", markersize=12)
    ax.set_axis_off()
    ax.set_title(cim, fontsize=8)
    fig.tight_layout()
    fig.savefig(fajl, dpi=110)
    plt.close(fig)


def csoport_nevek(m):
    """Egységenként a közigazgatási csoport neve (szavazókörnél a kerület/település, egyébként a járás)."""
    return np.where(m.e.szint == "szavazokor", m.e.nev, m.e.jaras.fillna(m.e.nev))


def csoport_mag(m, nev):
    """A csoport (kerület, járás) választókkal súlyozott középpontjához legközelebbi egysége."""
    t = np.flatnonzero(csoport_nevek(m) == nev)
    c = m.kozeppont(t)
    return int(t[np.argmin(np.hypot(*(m.xy[t] - c).T))])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("eset", choices=ESETEK)
    ap.add_argument("--tures", type=float)
    ap.add_argument("--hess", type=float, default=1.0)
    ap.add_argument("--kappa", type=float, default=0.0)
    ap.add_argument("--beta", type=float, default=2000.0)
    ap.add_argument("--mag", default="auto")
    ap.add_argument("--ido", type=float, default=120)
    ap.add_argument("--ujra", type=int, default=3)
    ap.add_argument("--lepes", type=int, default=200_000)
    ap.add_argument("--kor", type=int, default=2, help="Hess-központ-újraszámolások száma")
    ap.add_argument("--csak-uj", action="store_true", help="megmaradó körzet csak az új körzetnek adhat")
    ap.add_argument("--egy-part", action="store_true", help="az új körzet nem lép át folyót")
    ap.add_argument("--hatar-csoport", action="store_true", help="vágás közigazgatási határ mentén ingyenes")
    a = ap.parse_args()
    megye, db, tures, tipus, megszunik = ESETEK[a.eset]
    tures = a.tures or tures
    cfg = config()
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    e, sz = adatok()
    m = Megye(e, sz, megye_nev_ksh(megye))
    m.alfa, m.beta, m.lam, m.hess, m.hess_korok = a.kappa * m.suruseg, a.beta, 0, a.hess, a.kor
    m.csak_uj, m.egy_part = a.csak_uj, a.egy_part
    if a.hatar_csoport:
        m.hatar_csoporton_belul()
    geo = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek").set_index("unit_id").loc[m.e.unit_id].reset_index()
    oo = o[o.megye.str.startswith(megye)]
    gyokerek = {r.oevk: m.gyoker(r.oevk, r.szekhely) for r in oo.itertuples()}
    if tipus == "megszunik":
        valtozatok = [{k: v for k, v in gyokerek.items() if k != megszunik}]
    elif tipus == "uj":
        uj_id = f"{oo.maz.iloc[0]}-{db:02d}"
        if a.mag.startswith("ker"):
            magok = [csoport_mag(m, f"Budapest {a.mag[3:]}. ker.")]
        elif a.mag.startswith("jar"):  # a megye járásai ábécérendben, sorszámmal
            magok = [csoport_mag(m, sorted(set(m.e.jaras.dropna()))[int(a.mag[3:])])]
        else:
            magok = m.uj_magok(A, 4)
            if a.mag != "auto":
                magok = [magok[int(a.mag[4:])]]
        valtozatok = [{**gyokerek, uj_id: i} for i in magok]
    else:
        valtozatok = [gyokerek]
    KI.mkdir(parents=True, exist_ok=True)
    nev = f"{a.eset}_t{tures * 100:g}_h{a.hess:g}_r{a.kor}_k{a.kappa:g}_b{a.beta:g}{'_cu' if a.csak_uj else ''}{'_ep' if a.egy_part else ''}{'_hc' if a.hatar_csoport else ''}_{a.mag}"
    legjobb = None
    for k in valtozatok:
        r = m.megold(k, A, tures, None, idokorlat=a.ido, ujrainditas=a.ujra, lepesek=a.lepes)
        if "x" in r and (legjobb is None or m.ar(r["x"], k) < legjobb[0]):
            legjobb = (m.ar(r["x"], k), k, r)
    if legjobb is None:
        print(f"{nev}: nincs megoldás", flush=True)
        pd.DataFrame([{"nev": nev, "allapot": "nincs megoldás"}]).to_csv(KI / f"{nev}.csv", index=False, encoding="utf-8-sig")
        return
    _, k, r = legjobb
    x = list(r["x"])
    ert = m.ertekel(r["x"], A)
    ert_ma = m.ertekel(m.regi, A)
    pp = polsby_popper(geo, x)
    uj = [j for j in k if j not in set(m.regi)]
    mag_nev = m.e.nev[k[uj[0]]] if uj else ""
    cim = (f"{megye} · tűrés {tures:.1%} · hess {a.hess:g} ({a.kor} kör) · kappa {a.kappa:g}{' · csak új' if a.csak_uj else ''}{' · egy part' if a.egy_part else ''}{' · közig. határ' if a.hatar_csoport else ''} · mag {a.mag} {mag_nev}\n"
           f"{ert['athelyezett_valasztopolgar']:,} fő áthelyezve · új határ {ert['uj_hatar_km']:.0f} km · "
           f"átl. táv. {ert['atlag_tav_km']:.2f} km (ma {ert_ma['atlag_tav_km']:.2f}) · "
           f"PP átl. {pp[0]:.2f}, min {pp[1]:.2f} · eltérés {ert['legnagyobb_elteres']:.1%} · {r['allapot']}")
    rajzol(geo, x, list(m.regi), cim, KI / f"{nev}.png", [tuple(m.xy[k[j]]) for j in uj])
    print(cim.replace("\n", " · "), flush=True)
    pd.DataFrame([{"nev": nev, "eset": a.eset, "tures": tures, "hess": a.hess, "kappa": a.kappa, "beta": a.beta,
                   "mag": a.mag, "mag_nev": mag_nev, **{kk: vv for kk, vv in ert.items() if kk != "korzetek"},
                   "atlag_tav_ma": ert_ma["atlag_tav_km"], "pp_atlag": pp[0], "pp_min": pp[1],
                   "allapot": r["allapot"], "ido_s": round(r["ido"])}]).to_csv(KI / f"{nev}.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()

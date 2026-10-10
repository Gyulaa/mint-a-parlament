"""A javaslat végleges számítása a config.yaml `javaslat` szakasza szerint.

Csak azok a megyék változnak, ahol a korlát sérül, illetve ahová a felszabaduló hely kerül
(döntési fa: docs/elvek.md). Megyénként és körzetszámonként egy terv készül a rögzített
beállításokkal (Hess-tömörség, organikus elv, megszűnő körzet vagy új körzet magja).

Kimenet: data/interim/javaslat/<megye>_<db>.csv (unit_id, regi, uj), javaslat.csv (mérőszámok),
<megye>_<db>.png (térkép).

Futtatás: python -m oevk.javaslat [megye ...]
"""

import json
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from .adat import INTERIM, config, nvi_oevk
from .modell import Megye, adatok, megye_nev_ksh

KI = INTERIM / "javaslat"


def terv(e, sz, megye, beall, A, mcfg, geo=None):
    """Egy megye egy körzetszámra: (mérőszámok, hozzárendelés)."""
    m = Megye(e, sz, megye_nev_ksh(megye))
    m.alfa = beall.get("hatar_kappa", mcfg["hatar_kappa"]) * m.suruseg
    m.beta = beall.get("szabdalas_beta", mcfg["szabdalas_beta"])
    m.hess = beall.get("hess", mcfg["hess"])
    m.hess_korok = beall.get("hess_korok", mcfg["hess_korok"])
    m.csak_uj = beall.get("csak_uj", False)
    m.egy_part = beall.get("egy_part", False)
    m.lam = 0
    if beall.get("hatar_csoporton_belul", mcfg["hatar_csoporton_belul"]):
        m.hatar_csoporton_belul()
    o = nvi_oevk()
    oo = o[o.megye.str.startswith(megye)]
    korzetek = {r.oevk: m.gyoker(r.oevk, r.szekhely) for r in oo.itertuples() if r.oevk != beall.get("megszunik")}
    szekhely = {r.oevk: r.szekhely for r in oo.itertuples() if r.oevk in korzetek}
    if "uj_mag" in beall:
        uj_id = f"{oo.maz.iloc[0]}-{beall['db']:02d}"
        korzetek[uj_id] = int(m.id[beall["uj_mag"]])
        szekhely[uj_id] = m.e.nev[korzetek[uj_id]].replace(" ker.", " kerület")
    assert len(korzetek) == beall["db"], f"{megye}: {len(korzetek)} körzet, {beall['db']} kellene"
    if "egesz_kerulet" in beall:  # egy egész kerület (település) az új körzeté; csak a környező körzetek mozdulhatnak
        uj = next(j for j in korzetek if j not in set(m.regi))
        benne = set(np.flatnonzero(m.e.nev.to_numpy() == beall["egesz_kerulet"]))
        erintett = {m.regi[i] for i in benne}
        valtozhat = erintett | {m.regi[b] for a, b in m.el if m.regi[a] in erintett} | \
            {m.regi[a] for a, b in m.el if m.regi[b] in erintett} | {uj}
        valodi_regi = m.regi.copy()  # a számítás idejére a kerület a 17. körzet „mai” területe (kötött)
        m.regi = m.regi.copy()
        m.regi[sorted(benne)] = uj
        eredeti = m.szabad_korzetek

        def szabad(korz, tav, uj_tav=15):
            sz_ = eredeti(korz, tav, uj_tav=60)
            return {i: [uj] if i in benne else ([m.regi[i]] if m.regi[i] not in valtozhat
                                                else [j for j in s_ if j in valtozhat]) for i, s_ in sz_.items()}
        m.szabad_korzetek = szabad
        print(f"{megye}: {beall['egesz_kerulet']} egészben -> {uj}; változhat: {sorted(valtozhat)}", flush=True)
    r = m.megold(korzetek, A, beall["tures"], None, idokorlat=beall.get("idokorlat", 300),
                 ujrainditas=beall.get("ujrainditas", 4), lepesek=beall.get("lepesek", 300_000))
    if "egesz_kerulet" in beall:
        m.regi = valodi_regi  # az áthelyezéseket a valódi mai beosztáshoz mérjük
    if "x" not in r:
        return {"megye": megye, "korzetszam": beall["db"], "allapot": r["allapot"]}, None
    x = r["x"]
    sor = {"megye": megye, "korzetszam": beall["db"], "tures": beall["tures"],
           **m.ertekel(x, A), "allapot": r["allapot"], "ido_s": round(r["ido"]),
           "szekhelyek": json.dumps(szekhely, ensure_ascii=False)}
    t = pd.DataFrame({"unit_id": m.e.unit_id, "regi": m.regi, "uj": x})
    if geo is not None:
        from .kalibral import polsby_popper, rajzol
        g = geo.set_index("unit_id").loc[m.e.unit_id].reset_index()
        pp = polsby_popper(g, list(x))
        sor["pp_atlag"], sor["pp_min"] = round(pp[0], 3), round(pp[1], 3)
        rajzol(g, list(x), list(m.regi),
               f"{megye} · {beall['db']} körzet · {sor['athelyezett_valasztopolgar']:,} fő áthelyezve · "
               f"eltérés {sor['legnagyobb_elteres']:.1%} · PP min {pp[1]:.2f} · {r['allapot']}",
               KI / f"{megye}_{beall['db']}{beall.get('utotag', '')}.png")
    return sor, t


def main():
    cfg = config()
    mcfg = cfg["modell"]
    o = nvi_oevk()
    A = o.indulo.sum() / cfg["oevk_szam"]
    e, sz = adatok()
    geo = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek")
    KI.mkdir(parents=True, exist_ok=True)
    megyek = sys.argv[1:] or list(cfg["javaslat"])
    for megye in megyek:
        for beall in cfg["javaslat"][megye]:
            sor, t = terv(e, sz, megye, beall, A, mcfg, geo)
            print(json.dumps({k: v for k, v in sor.items() if k not in ("korzetek", "szekhelyek")}, ensure_ascii=False),
                  flush=True)
            nev = f"{megye}_{beall['db']}{beall.get('utotag', '')}"
            pd.DataFrame([sor]).to_csv(KI / f"{nev}_meroszam.csv", index=False, encoding="utf-8-sig")
            if t is not None:
                t.to_csv(KI / f"{nev}.csv", index=False, encoding="utf-8-sig")
    meroszamok = sorted(KI.glob("*_meroszam.csv"))
    pd.concat([pd.read_csv(f) for f in meroszamok]).to_csv(KI / "javaslat.csv", index=False, encoding="utf-8-sig")


if __name__ == "__main__":
    main()

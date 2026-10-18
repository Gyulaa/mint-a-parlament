"""Nagy felbontású áttekintő térkép a javaslatról (poszter): az ország 106 körzete, Budapest kivágatban,
alul a négy érintett megye ma és a javaslatban.

Bemenet csak a nyilvános térképi export (data/interim/export/oevk_javaslat_2026.zip), így a teljes
számítás nélkül is lefut. A székhelyek a 2. melléklet szerintiek.
Kimenet: data/interim/terkep/oevk_2026_javaslat.png (300 dpi) és .pdf.
Futtatás: python -m oevk.terkep
"""

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patheffects
from matplotlib.patches import Patch, Rectangle
from matplotlib.lines import Line2D
from shapely.geometry import box

from .adat import INTERIM

ZIP = INTERIM / "export" / "oevk_javaslat_2026.zip"
KI = INTERIM / "terkep"

ATLAG = 72172

# eltérés-sávok (%) és színek: kék = átlag alatti, piros = átlag feletti, szürke közép
SAVOK = [-np.inf, -15, -10, -5, 5, 10, 15, np.inf]
SZINEK = ["#104281", "#3987e5", "#b7d3f6", "#f0efec", "#f4c1bd", "#e8807a", "#a8302d"]
SAV_NEV = ["−15% alatt", "−15 – −10%", "−10 – −5%", "±5%-on belül", "+5 – +10%", "+10 – +15%", "+15% felett"]

INK, INK2, MUTED, FELSZIN = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"


def halo(sotet):
    """Felirat-szegély, hogy a határvonalon is olvasható legyen."""
    return [patheffects.withStroke(linewidth=2.2, foreground="#1c3a66" if sotet else "white")]

ROMAI = ["", "I.", "II.", "III.", "IV.", "V.", "VI.", "VII.", "VIII.", "IX.", "X.", "XI.", "XII.", "XIII.",
         "XIV.", "XV.", "XVI.", "XVII.", "XVIII.", "XIX.", "XX.", "XXI.", "XXII.", "XXIII."]


def beolvas(reteg):
    d = gpd.read_file(f"zip://{ZIP.as_posix()}!{reteg}.shp")
    d["szin"] = [SZINEK[np.searchsorted(SAVOK, 100 * x, side="right") - 1] for x in d.elteres]
    d["cimke"] = d.szekhely.str.replace(r"Budapest (\d+)\. kerület",
                                        lambda m: ROMAI[int(m.group(1))] + " ker.", regex=True)
    return d


def szazalek(x):
    return f"{100 * x:+.1f}%".replace(".", ",").replace("-", "−")


def rajzol(ax, d, megyek, keret=None, valtozott=None, athelyezett=None, cimkek=True, betu=7, keret_vonal=True,
           kihagy=None):
    d.plot(ax=ax, color=d.szin, edgecolor="white", linewidth=0.5)
    if athelyezett is not None and len(athelyezett):
        athelyezett.plot(ax=ax, facecolor="none", edgecolor=INK2, hatch="////", linewidth=0)
    megyek.boundary.plot(ax=ax, color=INK2, linewidth=1.1)
    if valtozott is not None and len(valtozott):
        valtozott.boundary.plot(ax=ax, color=INK, linewidth=2.0)
    if keret is not None:
        x0, y0, x1, y1 = keret
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.set_anchor("N")
    ax.set_axis_off()
    if keret_vonal:
        ax.add_patch(Rectangle((0, 0), 1, 1, transform=ax.transAxes, fill=False, edgecolor="#d6d5d0", lw=0.8))
    if not cimkek:
        return
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    for _, r in d.iterrows():
        p = r.geometry.representative_point()
        if not (x0 < p.x < x1 and y0 < p.y < y1):
            continue
        if kihagy is not None and kihagy.contains(p):
            continue
        sotet = r.szin in (SZINEK[0], SZINEK[1], SZINEK[6])
        ax.annotate(f"{r.cimke}\n{szazalek(r.elteres)}", (p.x, p.y), ha="center", va="center",
                    fontsize=betu, color="white" if sotet else INK, linespacing=1.05,
                    path_effects=halo(sotet))


def keret_of(geo, rahagyas=0.04):
    x0, y0, x1, y1 = geo.total_bounds
    dx, dy = (x1 - x0) * rahagyas, (y1 - y0) * rahagyas
    return x0 - dx, y0 - dy, x1 + dx, y1 + dy


def main():
    A = beolvas("korzetek_A")
    M = beolvas("korzetek_ma")
    E = gpd.read_file(f"zip://{ZIP.as_posix()}!egysegek.shp")
    megyek = A.dissolve("megye").reset_index()
    megyek["geometry"] = megyek.geometry.buffer(1).buffer(-1)

    mozgo = E[E.valt_A == 1]
    erintett_id = set(mozgo.oevk_A) | set(mozgo.oevk_ma)
    valt_A = A[A.oevk.isin(erintett_id)]
    valt_M = M[M.oevk.isin(erintett_id)]

    fig = plt.figure(figsize=(24, 18.5), facecolor=FELSZIN)
    gs = fig.add_gridspec(3, 4, height_ratios=[0.11, 1.0, 0.62], width_ratios=[1, 1, 1, 1],
                          left=0.02, right=0.98, top=0.985, bottom=0.03, hspace=0.06, wspace=0.03)

    # fejléc
    fej = fig.add_subplot(gs[0, :])
    fej.set_axis_off()
    fej.text(0, 0.78, "Az országgyűlési egyéni választókerületek a javaslat szerint", fontsize=30,
             fontweight="bold", color=INK, va="center")
    fej.text(0, 0.30, "106 körzet, 2026-os névjegyzék (országos átlag: 72 172 választó). Tolna 3 → 2, Somogy 4 → 3, "
             "Budapest 16 → 17, Pest 14 → 15 körzet; a többi 16 megye változatlan. "
             "322 931 választó kerül új körzetbe.", fontsize=15, color=INK2, va="center")

    # országos térkép; a Budapest körüli sűrű pesti körzetek felirata lent, a részletes paneleken van
    ax = fig.add_subplot(gs[1, :3])
    bp = keret_of(A[A.megye == "főváros"], 0.03)
    agglo = box(bp[0] - 9000, bp[1] - 9000, bp[2] + 9000, bp[3] + 9000)
    rajzol(ax, A[A.megye != "főváros"], megyek, keret=keret_of(A, 0.01), valtozott=valt_A, betu=7.2,
           keret_vonal=False, kihagy=agglo)
    fo = A[A.megye == "főváros"]
    fo.plot(ax=ax, color=fo.szin, edgecolor="white", linewidth=0.3)
    valt_A[valt_A.megye == "főváros"].boundary.plot(ax=ax, color=INK, linewidth=1.0)
    ax.add_patch(Rectangle((bp[0], bp[1]), bp[2] - bp[0], bp[3] - bp[1], fill=False, edgecolor=INK, lw=1.2))

    # jobb oszlop: Budapest kivágat és jelmagyarázat
    jobb = gs[1, 3].subgridspec(2, 1, height_ratios=[1.0, 0.62], hspace=0.08)
    axb = fig.add_subplot(jobb[0])
    rajzol(axb, A[A.megye.isin(["főváros"])], megyek, keret=bp, valtozott=valt_A[valt_A.megye == "főváros"],
           betu=8.5)
    axb.set_title("Budapest (17 körzet)", fontsize=16, color=INK, loc="left", fontweight="bold")
    axl = fig.add_subplot(jobb[1])
    axl.set_axis_off()

    # alsó sor: ma és javaslat
    dd = megyek[megyek.megye.isin(["Tolna", "Somogy"])]
    kp = megyek[megyek.megye.isin(["Pest", "főváros"])]
    panelek = [
        ("Somogy és Tolna ma (7 körzet)", M, keret_of(dd, 0.02), valt_M, None),
        ("Somogy és Tolna a javaslatban (5 körzet)", A, keret_of(dd, 0.02), valt_A, mozgo),
        ("Budapest és Pest ma (30 körzet)", M, keret_of(kp, 0.02), valt_M, None),
        ("Budapest és Pest a javaslatban (32 körzet)", A, keret_of(kp, 0.02), valt_A, mozgo),
    ]
    for i, (cim, d, k, v, mz) in enumerate(panelek):
        a = fig.add_subplot(gs[2, i])
        bp_panel = i >= 2
        dd_ = d[d.megye.isin(["Pest", "főváros"] if bp_panel else ["Tolna", "Somogy"])]
        rajzol(a, d, megyek, keret=k, valtozott=v[v.megye.isin(dd_.megye.unique())], athelyezett=mz,
               cimkek=False)
        for _, r in dd_.iterrows():
            if bp_panel and r.megye == "főváros":
                continue
            p = r.geometry.representative_point()
            sotet = r.szin in (SZINEK[0], SZINEK[1], SZINEK[6])
            nev = r.cimke.replace("Szigetszentmiklós", "Sziget-\nszentmiklós")
            a.annotate(f"{nev}\n{szazalek(r.elteres)}", (p.x, p.y), ha="center", va="center",
                       fontsize=7 if bp_panel else 8.5, color="white" if sotet else INK, linespacing=1.05,
                    path_effects=halo(sotet))
        a.set_title(cim, fontsize=14, color=INK, loc="left", fontweight="bold")

    # jelmagyarázat
    n = [((A.elteres * 100 >= lo) & (A.elteres * 100 < hi)).sum() for lo, hi in zip(SAVOK[:-1], SAVOK[1:])]
    elemek = [Patch(facecolor=c, edgecolor="#d6d5d0", label=f"{s}  ({k} körzet)") for c, s, k in zip(SZINEK, SAV_NEV, n)]
    elemek += [Line2D([], [], color=INK, lw=2.0, label="megváltozó körzet határa"),
               Line2D([], [], color=INK2, lw=1.1, label="megye- és fővároshatár"),
               Patch(facecolor="white", edgecolor=INK2, hatch="////", label="új körzetbe kerülő terület")]
    axl.legend(handles=elemek, loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=1, fontsize=12, frameon=False,
               title="Eltérés az országos átlagtól (a javaslatban)", title_fontsize=13, alignment="left")
    axl.text(0.0, 0.0, "Felirat: a körzet székhelye és eltérése az országos átlagtól.\n"
             "A Budapest körüli pesti körzetek felirata a jobb alsó panelen.", transform=axl.transAxes,
             fontsize=11, color=INK2, va="bottom")

    fig.text(0.98, 0.008, "Miklós Gyula, Mint a parlament 2026. Források: NVI (2026-os névjegyzék, szavazókörök), "
             "Lechner Tudásközpont (CC BY 4.0). Budapesten a szavazókör-térkép egyszerűsített, utcaszinten közelítő.",
             ha="right", fontsize=10, color=MUTED)

    KI.mkdir(parents=True, exist_ok=True)
    fig.savefig(KI / "oevk_2026_javaslat.png", dpi=300, facecolor=FELSZIN)
    fig.savefig(KI / "oevk_2026_javaslat.pdf", facecolor=FELSZIN)
    print(KI / "oevk_2026_javaslat.png")


if __name__ == "__main__":
    main()

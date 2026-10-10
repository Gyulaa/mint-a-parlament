"""Megyénkénti újrarajzolás a lehető legkisebb változtatással (HiGHS + heurisztika).

Cél: áthelyezett választópolgárok + alfa * az ÚJ körzethatár hossza (km; olyan szomszédos
egységek között, amelyek ma egy körzetben vannak) + beta * az ÚJ közigazgatási szabdalás
(egy járás, Budapesten és a megosztott városokban egy kerület/település olyan körzetbe is
kerül, amelyben ma nincs része). alfa = kappa * a megye választó/km sűrűsége, így Budapesten
és vidéken ugyanazt jelenti. A meglévő határok megszüntetéséért nincs jutalom, ezért a program
nem „szépíti” a rendben lévő határokat, az új határ viszont drága: rövid, egyenes vágásokat
keres. Ehhez jön a Hess-féle tömörség (hess_koltseg): minden egység a körzete központjától mért
távolságával arányosan drága, így a kényszerű áthelyezéseknél a központhoz közeli egységek
kerülnek át, nyúlványok nem nőnek; a központokat a megoldás után a kapott körzetek
középpontjába tesszük, és újra megoldjuk (hess_korok). Mindez lineáris, így a HiGHS pontosan
megoldhatja. Feltéve,
hogy minden körzet összefüggő, létszáma az [A(1-c), A(1+c)] sávban van (A = országos átlag),
és a megmaradó körzetek székhelye a helyén marad.

Megoldás három lépésben:
1. heurisztikus kezdőmegoldás (a megszűnő körzet szétosztása + kiegyenlítés),
2. javítás szimulált hűtéssel (határmenti áthelyezések, összefüggőség megtartásával),
3. HiGHS egészértékű program (Shirabe-féle folyam az összefüggőségre), a 2. lépés
   megoldásából indítva, időkorláttal. Ha a HiGHS bizonyítja az optimumot, az eredmény
   "optimális"; különben a legjobb talált megoldás az optimalitási réssel.

A Megye osztályt az oevk/javaslat.py (végleges terv) és az oevk/kalibral.py (beállítások próbája) használja.
"""

from functools import lru_cache
import math
import time

import highspy
import networkx as nx
import numpy as np
import pandas as pd

from .adat import INTERIM, config

NAPLO = False
BUDAI = {1, 2, 3, 11, 12, 22}  # budai kerületek (a XXI. Csepel külön sziget, a többi pesti)


@lru_cache
def egyseg_alak():
    """unit_id -> (terület km², kerület km, középpont x km, y km) az egységtábla geometriájából."""
    import geopandas as gpd
    g = gpd.read_file(INTERIM / "egysegek.gpkg", layer="egysegek", columns=["unit_id"])
    c = g.geometry.centroid
    return dict(zip(g.unit_id, zip(g.geometry.area / 1e6, g.geometry.length / 1000, c.x / 1000, c.y / 1000)))


def adatok():
    e = pd.read_csv(INTERIM / "egysegek.csv", dtype={"maz": str, "taz": str, "ksh_kod": str})
    sz = pd.read_csv(INTERIM / "szomszedsag.csv")
    sz = sz[sz.el & sz.azonos_megye]
    return e, sz


class Megye:
    def __init__(self, e, sz, megye):
        self.e = e[e.megye == megye].reset_index(drop=True)
        self.id = {u: i for i, u in enumerate(self.e.unit_id)}
        elek = [(self.id[a], self.id[b], h / 1000, isinstance(f, str))
                for a, b, h, f in zip(sz.a, sz.b, sz.hossz_m, sz.folyo) if a in self.id and b in self.id]
        self.el = [(a, b) for a, b, _, _ in elek]
        self.hossz = np.array([h for _, _, h, _ in elek])  # km
        self.folyo_el = np.array([f for *_, f in elek], dtype=bool)  # folyón átívelő él (híd, komp)
        self.v = self.e.jogosult_2026.to_numpy().astype(int)
        self.regi = self.e.oevk_jelenlegi.to_numpy()
        # közigazgatási csoport: szavazókörnél a település/kerület, egyébként a járás
        csop = np.where(self.e.szint == "szavazokor", self.e.nev, self.e.jaras.fillna(self.e.nev))
        kod = {c: k for k, c in enumerate(sorted(set(csop)))}
        self.csoport = np.array([kod[c] for c in csop])
        self.suruseg = self.v.sum() / max(self.hossz.sum(), 1e-9)  # választó / km egységhatár
        mcfg = config()["modell"]
        self.alfa = mcfg.get("hatar_kappa", 30) * self.suruseg
        self.beta = mcfg.get("szabdalas_beta", 2000)
        self.lam = mcfg.get("alak_lambda", 0)
        alak = egyseg_alak()
        self.terulet = np.array([alak[u][0] for u in self.e.unit_id])
        kerulet = np.array([alak[u][1] for u in self.e.unit_id])
        belso = np.zeros(len(self.e))
        for (a_, b_), h in zip(self.el, self.hossz):
            belso[a_] += h
            belso[b_] += h
        self.kulso = np.clip(kerulet - belso, 0, None)  # a szomszédsággal nem fedett határ (megyehatár stb.)
        P0, A0 = self.korzet_alak(self.regi)
        self.alak0 = {k: P0[k] / math.sqrt(A0[k]) for k in P0}
        self.alak_median = float(np.median(list(self.alak0.values())))
        self.xy = np.array([alak[u][2:] for u in self.e.unit_id])
        self.hess = mcfg.get("hess", 0)
        self.hess_korok = mcfg.get("hess_korok", 2)
        self.kozpont = None  # a központok felülírása (Lloyd-iteráció közben)
        self.csak_uj = mcfg.get("csak_uj", False)  # megmaradó körzet egysége csak az új körzetbe mehet
        self.egy_part = mcfg.get("egy_part", False)  # az új körzet nem lép át folyót
        self.R = float(np.median([math.sqrt(a / math.pi) for a in A0.values()]))  # mai körzetek medián sugara, km
        self._hk = {}
        self.uj_el = np.array([self.regi[a] == self.regi[b] for a, b in self.el])  # ma belső él
        self.mai_par = {(self.csoport[i], self.regi[i]) for i in range(len(self.e))}
        if mcfg.get("hatar_csoporton_belul", False):
            self.hatar_csoporton_belul()
        self.g = nx.Graph(self.el)
        self.g.add_nodes_from(range(len(self.e)))
        assert nx.is_connected(self.g), f"{megye}: a szomszédsági gráf nem összefüggő"
        szaraz = nx.Graph([e for e, f in zip(self.el, self.folyo_el) if not f])
        szaraz.add_nodes_from(range(len(self.e)))
        self.part = np.zeros(len(self.e), dtype=int)  # folyóparti „szárazföldi” komponens sorszáma
        for k, c in enumerate(nx.connected_components(szaraz)):
            self.part[list(c)] = k
        ker = self.e.nev.str.extract(r"^Budapest (\d+)\. ker\.$")[0]
        if ker.notna().all():  # Budapesten a szavazókör-poligonok átfedik a Dunát: a part a kerületből
            ker = ker.astype(int)
            self.part = np.where(ker.isin(BUDAI).to_numpy(), 1, np.where(ker == 21, 2, 0))

    def hatar_csoporton_belul(self):
        """Az új határ csak ott számít (alfa), ahol egy közigazgatási csoportot (kerület, megosztott
        település, járás) vág ketté; a csoportok közötti határ mentén ingyenes („organikus elv”)."""
        self.uj_el = self.uj_el & np.array([self.csoport[a] == self.csoport[b] for a, b in self.el])

    def gyoker(self, oevk, szekhely):
        """A körzet székhelyének egysége (megosztott székhelynél a körzetbe eső legnagyobb)."""
        nev = szekhely.replace(" kerület", " ker.")
        jo = self.e[(self.e.nev == nev) & (self.e.oevk_jelenlegi == oevk)]
        if jo.empty:
            jo = self.e[self.e.oevk_jelenlegi == oevk]
        return int(jo.jogosult_2026.idxmax())

    def uj_magok(self, A, db=5):
        """Jelölt magok egy új körzethez: több mai körzet találkozásánál fekvő egységek, ahol a
        szomszédos körzetek a legjobban túlterheltek; minden jelölt más körzet-kombinációból."""
        nep = pd.Series(self.v).groupby(self.regi).sum()
        jeloltek = []
        for i in range(len(self.e)):
            korok = frozenset({self.regi[i]} | {self.regi[t] for t in self.g[i]})
            if len(korok) >= 2:
                jeloltek.append((sum(nep[k] / A - 1 for k in korok) / len(korok) ** 0.5, korok, i))
        magok, latott = [], set()
        for _, korok, i in sorted(jeloltek, key=lambda t: -t[0]):
            if korok not in latott:
                latott.add(korok)
                magok.append(i)
            if len(magok) == db:
                break
        return magok

    def szabad_korzetek(self, korzetek, tav, uj_tav=15):
        """Egy megmaradó körzet egysége csak a saját körzetébe vagy egy legfeljebb `tav` lépésre
        lévő körzetbe kerülhet; a megszűnő körzet egysége bármelyikbe. Új körzet (amelynek nincs
        mai területe) a magjától legfeljebb `uj_tav` lépésre terjedhet."""
        n = len(self.e)
        regiek = set(self.regi)
        tavolsag = {j: nx.multi_source_dijkstra_path_length(
            self.g, [i for i in range(n) if self.regi[i] == j], cutoff=tav) if j in regiek
            else nx.single_source_shortest_path_length(self.g, korzetek[j], cutoff=uj_tav) for j in korzetek}
        szabad = {i: [j for j in korzetek if self.regi[i] not in korzetek or i in tavolsag[j]] for i in range(n)}
        if self.csak_uj:  # a megmaradó körzetek egymás között nem cserélnek, csak az új körzetnek adnak
            uj = {j for j in korzetek if j not in regiek}
            szabad = {i: [j for j in s if self.regi[i] not in korzetek or j == self.regi[i] or j in uj]
                      for i, s in szabad.items()}
        if self.egy_part:  # az új körzet csak a magja folyópartján terjedhet
            szabad = {i: [j for j in s if j in regiek or self.part[i] == self.part[korzetek[j]]]
                      for i, s in szabad.items()}
        return szabad

    def kozeppont(self, tagok):
        w = self.v[tagok].astype(float)
        return (self.xy[tagok] * w[:, None]).sum(0) / max(w.sum(), 1.0)

    def hess_koltseg(self, korzetek):
        """Hess-féle tömörség: ha i egység a j körzetbe kerül, ára hess * v_i * d(i, j központja) / R.

        A központ a mai körzet választókkal súlyozott középpontja (új körzetnél a magja), R a megye
        mai körzeteinek medián sugara. Egy egység így magától csak akkor kerül át, ha az új körzete
        központjához legalább R/hess-sel közelebb van; a kényszerű áthelyezéseknél pedig a központhoz
        közeli egységek a kedvezőbbek, ezért nem nőnek nyúlványok. Lineáris, a HiGHS pontosan kezeli."""
        if not self.hess:
            return None
        if self.kozpont is not None:
            return {j: self.hess * self.v * np.hypot(*(self.xy - self.kozpont[j]).T) / self.R for j in korzetek}
        kulcs = (self.hess, tuple(sorted(korzetek.items())))
        if kulcs not in self._hk:
            regiek = set(self.regi)
            hk = {}
            for j, r in korzetek.items():
                c = self.kozeppont(np.flatnonzero(self.regi == j)) if j in regiek else self.xy[r]
                hk[j] = self.hess * self.v * np.hypot(*(self.xy - c).T) / self.R
            self._hk[kulcs] = hk
        return self._hk[kulcs]

    def hatar_km(self, x):
        return float(sum(h for (a, b), h in zip(self.el, self.hossz) if x[a] != x[b]))

    def uj_hatar_km(self, x):
        return float(sum(h for (a, b), h, u in zip(self.el, self.hossz, self.uj_el) if u and x[a] != x[b]))

    def szabdalas(self, x):
        """Hány „fölösleges” (csoport, körzet) pár van: csoportonként a körzetek száma mínusz 1."""
        return len({(self.csoport[i], x[i]) for i in range(len(x))}) - len(set(self.csoport))

    def uj_szabdalas(self, x):
        """Hány olyan (csoport, körzet) pár van, amely ma nincs."""
        return len({(self.csoport[i], x[i]) for i in range(len(x))} - self.mai_par)

    def korzet_alak(self, x):
        """Körzetenként (kerület km, terület km²)."""
        P, A = {}, {}
        for i in range(len(x)):
            P[x[i]] = P.get(x[i], 0.0) + self.kulso[i]
            A[x[i]] = A.get(x[i], 0.0) + self.terulet[i]
        for (a, b), h in zip(self.el, self.hossz):
            if x[a] != x[b]:
                P[x[a]] += h
                P[x[b]] += h
        return P, A

    def alak_buntetes(self, k, P, A):
        """lam * mennyivel rosszabb a körzet kerület/sqrt(terület) aránya a mainál (új körzetnél a mediánnál)."""
        if not self.lam or A <= 0:
            return 0.0
        return self.lam * max(0.0, P / math.sqrt(A) - self.alak0.get(k, self.alak_median))

    def ar(self, x, korzetek, suly=None):
        athelyezett = sum(self.v[i] for i in range(len(x)) if self.regi[i] in korzetek and self.regi[i] != x[i])
        P, A = self.korzet_alak(x)
        alak = sum(self.alak_buntetes(k, P[k], A[k]) for k in P)
        hk = self.hess_koltseg(korzetek)
        tav = float(sum(hk[x[i]][i] for i in range(len(x)))) if hk else 0.0
        return athelyezett + self.alfa * self.uj_hatar_km(x) + self.beta * self.uj_szabdalas(x) + alak + tav

    # --- 1. kezdőmegoldás -------------------------------------------------------------------

    def kezdo_megoldas(self, korzetek, L, U, szabad, lepesek=5000):
        """Megengedett kezdőmegoldás heurisztikával (vagy None).

        Növesztés: a megszűnő körzet egységeit mindig a legkisebb létszámú szomszéd körzet kapja.
        Kiegyenlítés: a sávon kívüli körzet határmenti egységet ad át vagy kap, de csak úgy, hogy
        a fogadó kisebb maradjon az átadónál (a létszámok négyzetösszege csökken, nincs körbeforgás).
        """
        n, K = len(self.e), list(korzetek)
        x = np.array([self.regi[i] if self.regi[i] in korzetek else None for i in range(n)], dtype=object)
        regiek = set(self.regi)
        for j, r in korzetek.items():
            if j not in regiek:  # új körzet: a magjából indul
                x[r] = j
        nep = {j: int(self.v[x == j].sum()) for j in K}
        kiosztatlan = {i for i in range(n) if x[i] is None}
        while kiosztatlan:
            for j in sorted(K, key=nep.get):
                hatar = [k for k in kiosztatlan if j in szabad[k] and any(x[t] == j for t in self.g[k])]
                if hatar:
                    k = max(hatar, key=lambda k: sum(x[t] == j for t in self.g[k]))
                    x[k] = j
                    nep[j] += int(self.v[k])
                    kiosztatlan.discard(k)
                    break
            else:
                return None

        gyokerek = set(korzetek.values())
        for _ in range(lepesek):
            hibak = {j: max(nep[j] - U, L - nep[j], 0) for j in K}
            if max(hibak.values()) == 0:
                return x
            lepett = False
            for j in sorted(K, key=hibak.get, reverse=True):
                if hibak[j] == 0:
                    break
                lehetosegek = []
                for i in range(n):
                    if i in gyokerek:
                        continue
                    v = int(self.v[i])
                    szomszed = {x[t] for t in self.g[i]}
                    if nep[j] > U and x[i] == j:
                        parok = [(j, c) for c in szomszed - {j} if c in szabad[i] and nep[c] + v < nep[j]]
                    elif nep[j] < L and x[i] != j and j in szomszed and j in szabad[i]:
                        parok = [(x[i], j)] if nep[x[i]] - v > nep[j] else []
                    else:
                        continue
                    for ado, kap in parok:
                        lehetosegek.append((self.regi[i] == ado, abs(v - hibak[j]), i, ado, kap))
                for _, _, i, ado, kap in sorted(lehetosegek):
                    if self.osszefuggo_marad({t for t in range(n) if x[t] == ado}, i):
                        x[i] = kap
                        nep[ado] -= int(self.v[i])
                        nep[kap] += int(self.v[i])
                        lepett = True
                        break
                if lepett:
                    break
            if not lepett:
                return None
        return None

    # --- 2. javítás szimulált hűtéssel -------------------------------------------------------

    def osszefuggo_marad(self, tagok, i):
        """Összefüggő marad-e a körzet (tagok halmaza), ha i kikerül belőle."""
        maradek = tagok - {i}
        if not maradek:
            return False
        start = next(iter(maradek))
        latott, verem = {start}, [start]
        while verem:
            for t in self.g[verem.pop()]:
                if t in maradek and t not in latott:
                    latott.add(t)
                    verem.append(t)
        return len(latott) == len(maradek)

    def javit(self, x, korzetek, L, U, szabad, suly, lepesek=150_000, mag=0):
        """Határmenti egységek áthelyezése; energia = ar() + büntetés a sávon kívüli létszámért.

        A körzetek mindvégig összefüggők, a gyökerek a helyükön; a legjobb megengedett
        állapotot adja vissza (vagy None, ha nem talált ilyet).
        """
        rng = np.random.default_rng(mag)
        x = x.copy()
        K = list(korzetek)
        gyokerek = set(korzetek.values())
        tagok = {j: set(np.flatnonzero(x == j)) for j in K}
        nep = {j: int(self.v[list(t)].sum()) for j, t in tagok.items()}
        v = self.v

        hk = self.hess_koltseg(korzetek)

        def koltseg(i, j):
            return (v[i] if self.regi[i] in korzetek and self.regi[i] != j else 0) + (hk[j][i] if hk else 0)

        def buntetes(p):
            return 20 * (max(0, p - U) + max(0, L - p))

        ar = self.ar(x, korzetek)
        legjobb, legjobb_ar = x.copy(), (ar if all(L <= nep[j] <= U for j in K) else math.inf)
        mozgathato = [i for i in range(len(x)) if i not in gyokerek]
        szomszed_hossz = [[] for _ in range(len(x))]  # (szomszéd, hossz, ma belső él-e)
        for (a_, b_), h, u in zip(self.el, self.hossz, self.uj_el):
            szomszed_hossz[a_].append((b_, h, u))
            szomszed_hossz[b_].append((a_, h, u))
        Pk, Ak = self.korzet_alak(x)
        csop_db = {}
        for i in range(len(x)):
            k = (self.csoport[i], x[i])
            csop_db[k] = csop_db.get(k, 0) + 1
        T0 = max(200.0, float(np.median(v)), 2 * self.alfa * float(np.median(self.hossz)))
        for lepes in range(lepesek):
            T = T0 * (1 - lepes / lepesek) + 1
            i = mozgathato[rng.integers(len(mozgathato))]
            a = x[i]
            celok = [x[t] for t in self.g[i] if x[t] != a and x[t] in szabad[i]]
            if not celok:
                continue
            b = celok[rng.integers(len(celok))]
            hossz_d = sum(h if x[t] == a else (-h if x[t] == b else 0) for t, h, u in szomszed_hossz[i] if u)
            g_ = self.csoport[i]
            szab_d = ((csop_db.get((g_, b), 0) == 0 and (g_, b) not in self.mai_par)
                      - (csop_db[(g_, a)] == 1 and (g_, a) not in self.mai_par))
            vagas = self.alfa * hossz_d + self.beta * szab_d
            if self.lam:
                dPa = -self.kulso[i] + sum(h if x[t] == a else -h for t, h, _ in szomszed_hossz[i])
                dPb = self.kulso[i] + sum(-h if x[t] == b else h for t, h, _ in szomszed_hossz[i])
                ujPa, ujAa, ujPb, ujAb = Pk[a] + dPa, Ak[a] - self.terulet[i], Pk[b] + dPb, Ak[b] + self.terulet[i]
                vagas += (self.alak_buntetes(a, ujPa, ujAa) - self.alak_buntetes(a, Pk[a], Ak[a])
                          + self.alak_buntetes(b, ujPb, ujAb) - self.alak_buntetes(b, Pk[b], Ak[b]))
            d = (koltseg(i, b) - koltseg(i, a) + vagas
                 + buntetes(nep[a] - v[i]) - buntetes(nep[a]) + buntetes(nep[b] + v[i]) - buntetes(nep[b]))
            if d > 0 and rng.random() >= math.exp(-d / T):
                continue
            if not self.osszefuggo_marad(tagok[a], i):
                continue
            x[i] = b
            tagok[a].discard(i)
            tagok[b].add(i)
            nep[a] -= v[i]
            nep[b] += v[i]
            csop_db[(g_, a)] -= 1
            csop_db[(g_, b)] = csop_db.get((g_, b), 0) + 1
            if self.lam:
                Pk[a], Ak[a], Pk[b], Ak[b] = ujPa, ujAa, ujPb, ujAb
            ar += koltseg(i, b) - koltseg(i, a) + vagas
            if ar < legjobb_ar and all(L <= nep[j] <= U for j in K):
                legjobb, legjobb_ar = x.copy(), ar
        return legjobb if legjobb_ar < math.inf else None

    # --- 3. egészértékű program ---------------------------------------------------------------

    def mip(self, korzetek, L, U, szabad, suly, kezdo, idokorlat):
        n, K = len(self.e), list(korzetek)
        h = highspy.Highs()
        h.setOptionValue("output_flag", NAPLO)
        h.setOptionValue("mip_rel_gap", 1e-4)
        h.setOptionValue("time_limit", float(idokorlat))
        x = {(i, j): h.addBinary() for i in range(n) for j in szabad[i]}
        for i in range(n):
            h.addConstr(sum(x[i, j] for j in szabad[i]) == 1)
        for j, r in korzetek.items():
            h.addConstr(x[r, j] == 1)
            for i in range(n):  # nem gyökér egységnek kell szomszéd ugyanabban a körzetben
                if i != r and (i, j) in x:
                    h.addConstr(x[i, j] - sum(x[k, j] for k in self.g[i] if (k, j) in x) <= 0)
            letszam = sum(int(self.v[i]) * x[i, j] for i in range(n) if (i, j) in x)
            h.addConstr(letszam >= L)
            h.addConstr(letszam <= U)

            # összefüggőség: a gyökér a körzet minden egységének 1 egységnyi folyamot küld
            iranyitott = [(a, b) for a, b in self.el + [(b, a) for a, b in self.el] if (a, j) in x and (b, j) in x]
            f = {(a, b): h.addVariable(lb=0, ub=n - 1) for a, b in iranyitott}
            be, ki = {}, {}
            for a, b in iranyitott:
                ki.setdefault(a, []).append(f[a, b])
                be.setdefault(b, []).append(f[a, b])
                h.addConstr(f[a, b] - (n - 1) * x[b, j] <= 0)
            for i in range(n):
                if i != r and (i, j) in x:
                    h.addConstr(sum(be.get(i, [])) - sum(ki.get(i, [])) - x[i, j] == 0)

        # tömörség: y_e >= |x[a,j] - x[b,j]|, azaz y_e = 1, ha az él körzethatár; súlya alfa * hossz
        tagok_cel = [int(self.v[i]) * (1 - x[i, self.regi[i]]) for i in range(n) if self.regi[i] in korzetek]
        hk = self.hess_koltseg(korzetek)
        if hk:
            tagok_cel += [float(hk[j][i]) * x[i, j] for (i, j) in x]
        for (a, b), hossz, uj in zip(self.el, self.hossz, self.uj_el):
            if not uj:
                continue
            y = h.addVariable(lb=0, ub=1)
            for j in K:
                xa, xb = x.get((a, j)), x.get((b, j))
                if xa is not None and xb is not None:
                    h.addConstr(y - xa + xb >= 0)
                    h.addConstr(y - xb + xa >= 0)
                elif xa is not None:
                    h.addConstr(y - xa >= 0)
                elif xb is not None:
                    h.addConstr(y - xb >= 0)
            tagok_cel.append(float(self.alfa * hossz) * y)
        # szabdalás: z_gj >= x_ij a csoport minden i egységére; a csoportok körzetszáma
        if self.beta:
            for g_ in set(self.csoport):
                tagok = np.flatnonzero(self.csoport == g_)
                for j in K:
                    benne = [x[i, j] for i in tagok if (i, j) in x]
                    if benne and (g_, j) not in self.mai_par:
                        z = h.addVariable(lb=0, ub=1)
                        for xi in benne:
                            h.addConstr(z - xi >= 0)
                        tagok_cel.append(float(self.beta) * z)
        h.setObjective(h.qsum(tagok_cel), highspy.ObjSense.kMinimize)

        if kezdo is not None:
            idx = [x[i, kezdo[i]].index for i in range(n)]
            h.setSolution(len(idx), np.array(idx, dtype=np.int32), np.ones(len(idx)))
        h.run()
        allapot = h.modelStatusToString(h.getModelStatus())
        if not h.getInfo().primal_solution_status:
            return allapot, None, None
        sol = h.getSolution().col_value
        megoldas = np.array([max(szabad[i], key=lambda j: sol[x[i, j].index]) for i in range(n)], dtype=object)
        return allapot, megoldas, h.getInfo().mip_gap

    def megold(self, korzetek, A, c, suly, idokorlat=60, tav=4, ujrainditas=3, lepesek=150_000):
        """korzetek: {oevk-azonosító: gyökér egység}; c: tűrés (pl. 0.15).

        A javító keresés újraindításai láncban futnak: mindegyik az addigi legjobbról indul,
        más véletlen maggal (az első a heurisztikus kezdőmegoldásról)."""
        L, U = math.ceil(A * (1 - c)), math.floor(A * (1 + c))
        szabad = self.szabad_korzetek(korzetek, tav)
        kezdet = time.time()
        heur = self.kezdo_megoldas(korzetek, L, U, szabad)
        eredmeny = None
        korok = 1 + (self.hess_korok if self.hess else 0)
        try:
            for kor in range(korok):
                if kor:  # Hess: a központok a kapott körzetek választókkal súlyozott középpontjába kerülnek
                    heur = eredmeny["x"]
                    self.kozpont = {j: self.kozeppont(np.flatnonzero(heur == j)) for j in korzetek}
                if heur is not None:
                    for mag in range(ujrainditas if kor == 0 else 1):
                        jelolt = self.javit(heur, korzetek, L, U, szabad, suly, lepesek=lepesek, mag=mag)
                        if jelolt is not None and self.ar(jelolt, korzetek, suly) < self.ar(heur, korzetek, suly):
                            heur = jelolt
                if self.lam:  # az alakvédelem nemlineáris: a javító keresés eredménye a végső
                    if heur is None:
                        return {"allapot": "nincs megoldás (heurisztika)", "ido": time.time() - kezdet}
                    return {"allapot": "javító keresés", "ido": time.time() - kezdet, "x": heur}
                allapot, x, res = self.mip(korzetek, L, U, szabad, suly, heur, idokorlat)
                if x is None:
                    if eredmeny is not None:
                        break
                    return {"allapot": "nincs megoldás" if allapot == "Infeasible" else "eldöntetlen (időkorlát)",
                            "ido": time.time() - kezdet}
                if heur is not None and self.ar(heur, korzetek, suly) < self.ar(x, korzetek, suly):
                    x = heur  # a HiGHS nem javított a kezdőmegoldáson
                allapot = "optimális" if allapot == "Optimal" else f"legjobb talált, rés {res:.0%}"
                eredmeny = {"allapot": allapot, "ido": time.time() - kezdet, "x": x}
        finally:
            self.kozpont = None
        eredmeny["ido"] = time.time() - kezdet
        return eredmeny

    def ertekel(self, x, A):
        mozdul = np.array([self.regi[i] != x[i] for i in range(len(x))])
        cimke = np.asarray(x, dtype=str)
        letszam = pd.Series(self.v).groupby(cimke).sum()
        jaras = self.e.assign(k=cimke).groupby("jaras").k.nunique()
        tav = 0.0  # választók átlagos távolsága a (tényleges) körzetközépponttól
        for k in set(cimke):
            t = np.flatnonzero(cimke == k)
            tav += float((self.v[t] * np.hypot(*(self.xy[t] - self.kozeppont(t)).T)).sum())
        return {
            "athelyezett_valasztopolgar": int(self.v[mozdul].sum()),
            "athelyezett_egyseg": int(mozdul.sum()),
            "legnagyobb_elteres": float((letszam / A - 1).abs().max()),
            "megosztott_jaras": int((jaras > 1).sum()),
            "elvagott_el": int(sum(x[a] != x[b] for a, b in self.el)),
            "uj_elvagott_el": int(sum(x[a] != x[b] and self.regi[a] == self.regi[b] for a, b in self.el)),
            "hatar_km": round(self.hatar_km(x), 1),
            "uj_hatar_km": round(self.uj_hatar_km(x), 1),
            "szabdalas": int(self.szabdalas(x)),
            "atlag_tav_km": round(tav / self.v.sum(), 2),
            "korzetek": "; ".join(f"{k}: {v:,} ({v / A - 1:+.1%})" for k, v in letszam.items()),
        }


def megye_nev_ksh(megye):
    """A config/NVI megyeneve -> az egységtábla (KSH) megyeneve."""
    return "főváros" if megye == "Budapest" else megye

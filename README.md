# OEVK 2026 – az országgyűlési egyéni választókerületek felülvizsgálata

Javaslat a 106 országgyűlési egyéni választókerület (OEVK) határainak módosítására a 2026-os
választói névjegyzék alapján. A munka a **Mint-a-parlament** vetélkedőre készült; nem valós
jogalkotási javaslat, de valós, nyilvános adatokkal és a hatályos jogszabály szerint számol.

Készítette: **Miklós Gyula**, a csapattal egyeztetve.

## Röviden: mi a probléma, és mi a javaslat?

A választási törvény (2011. évi CCIII. törvény, Vjt. 4. §) szerint egy választókerületben a
választópolgárok száma legfeljebb **15%-kal** térhet el az országos átlagtól (2026-ban 72 172 fő), és
ha az eltérés **20%** fölé nő, a beosztást kötelező módosítani. A 2026. áprilisi választás
névjegyzéke szerint négy körzet lépi túl a 20%-ot: **Tolna mindhárom körzete** (kb. −21%) és a
**barcsi körzet** Somogyban (−20,5%).

A javaslat alapelve: **a körzetek száma marad 106, és csak oda nyúlunk, ahol a korlát sérül.**
A többi tizenhat megye beosztása változatlan.

| Megye | Változás | Választók, akik új körzetbe kerülnek |
| --- | --- | ---: |
| Tolna | 3 → 2 körzet (a dombóvári megszűnik) | 58 355 |
| Budapest | 16 → 17 körzet: a 17. körzet a **teljes XVIII. kerület**, ahogy 2011 és 2024 között | 100 780 |
| Somogy | 4 → 3 körzet (a marcali megszűnik) | 70 709 |
| Pest | 14 → 15 körzet (új körzet Ecser–Gyömrő környékén) | 93 087 |
| **Összesen** | | **322 931** |

Tolna három körzettel nem javítható: a megye választóinak száma három körzetre osztva is átlagosan
−21%. Ezért Tolna két körzetet kap. Somogyban a marcali körzet szűnik meg, így ott is minden körzet
±15%-on belül marad. A két felszabaduló hely oda kerül, ahol a legnagyobb a túlterhelés: Budapestre
és Pest megyébe.

A körzetszámok megegyeznek azzal, amit a szakirodalom is javasol: a
Sainte-Laguë-, a Hamilton- és a leximin-elosztással ([ELTE KRTK, 2026](https://krtk.elte.hu/wp-content/uploads/2026/01/krtk_policy_brief_no_03_hu.pdf)),
valamint a Választási Földrajz 2024-es javaslatával ([Telex](https://telex.hu/valasztasi-foldrajz/2024/08/12/uj-valasztasi-rendszer-2026-aranytalansag)).

A javaslat után egyetlen körzet sem tér el 20%-nál jobban, és Tolna kivételével mind 15%-on belül
van (Tolna két körzete +18,6% és +18,5%, amit a törvény a megyehatár miatt megenged; két körzettel
ennél jobb nem érhető el).

## Hogyan készült a javaslat?

**1. Adatok.** A Nemzeti Választási Iroda (NVI) nyilvános választási adataiból szavazókörönként
ismert, hány választó van és melyik körzethez tartozik. Az építőkövek az egész települések;
Budapesten és a nyolc kettéosztott nagyvárosban (pl. Debrecen, Szeged) a szavazókörök, mert ott a
körzethatár településen belül is fut. A térképi határok a Lechner Tudásközpont nyílt
közigazgatási adataiból, a hidak és kompok az OpenStreetMapből származnak.

**2. Szomszédság.** Egy körzetnek összefüggőnek kell lennie. Két település (vagy szavazókör) akkor
számít szomszédosnak, ha legalább 50 méteren közös a határuk. A Dunán és a Tiszán át csak ott,
ahol közúti híd vagy komp köti össze őket.

**3. Mit keres a számítás?** Megyénként azt a beosztást, amelyben **a lehető legkevesebb választó
kerül másik körzetbe**, úgy, hogy minden körzet összefüggő, legfeljebb ±15%-kal tér el, és a
megmaradó körzetek székhelye a helyén marad. Ez egy egészértékű optimalizálási feladat, amelyet a
nyílt forráskódú [HiGHS](https://highs.dev) megoldó old meg. A végleges megoldások mindegyikéről a
megoldó **bizonyította**, hogy ugyanezekkel a szempontokkal nincs jobb.

**4. Az alak.** Ha csak az áthelyezések számát néznénk, nyúlványos, szabálytalan körzetek is
kijöhetnének. Ezért a számítás két dolgot is figyel: (a) minden település annál „drágább”, minél
messzebb van a körzete közepétől (az ún. Hess-modell), és (b) az új határ lehetőleg kerület- vagy
járáshatáron fusson; ami egy kerületet vagy járást kettévág, az drága (az „organikus elv”,
Bódi–Kovalcsik, 2024). Ennek ára, hogy néhol valamivel több választó kerül át a minimumnál:
Somogyban 70 709 a 61 187 helyett, cserébe ott minden új határ járáshatáron fut.

**5. Beállítás és ellenőrzés.** A súlyokat kb. 400 próbafutással állítottuk be. A fontosabb esetek
térképeit Miklós Gyula nézte át, és ezek alapján döntött; a nyúlványos vagy furcsa alakú
változatokat elvetettük. Az új körzet helyét Budapesten mind a 23 kerületből, Pesten mind a 18 járásból indítva kipróbáltuk.
Budapesten végül a folytonosság mellett döntöttünk: a 17. körzet a teljes XVIII. kerület, ahogy
2011 és 2024 között (Budapest 15. OEVK). Ez kb. 37 ezerrel több áthelyezést jelent, mint a legkisebb
változtatás, de nincs nyúlvány, és a törvényszövegben egyszerűen „XVIII. kerület” áll.

**6. Pártsemlegesség.** Választási eredmény (pártok szavazatai) nem kerül a számításba.

**7. A törvényszöveg.** A Vjt. 1. melléklete a megyénkénti körzetszámot, a 2. melléklet
körzetenként a területet adja meg: vidéken településlistával, Budapesten egész kerületekkel és a
kerületrészek határvonalával. A program elkészíti a két melléklet teljes, módosított szövegét
(Word, a jogászoknak, jelölések nélkül): a változatlan körzetek szövege szó szerint a hatályos
mellékletből való, a változók a javaslatból. A két új budapesti kerületrész (X. és XX. kerület)
leírása kézi (`data/manual/melleklet_kezi.yaml`), a hatályos budapesti szöveg formájában: zárt
határvonal utcatengelyek mentén, a szomszéd körzetnek ugyanaz a vonal ellentétes irányban, és ahol a
lakótelepen a szavazókör határa a házak mögött fut, egy záró mondat sorolja fel a túloldalra eső
házszámokat. A leírást a két kerület minden házszámos címére összevetettük az NVI címjegyzékével
(XX. kerület: 5955 cím, nincs eltérés; X. kerület: 3000 cím, 2 eltérés, mindkettő a változatlan,
hatályos határon).

### Korlátok, amiket érdemes tudni

- Az eredmény **elsősorban matematikai**. Lehetnek olyan helyi szempontok (közlekedés, összetartozó
  közösségek, földrajzi adottságok), amelyeket a számítás nem tudott figyelembe venni.
- Budapesten a határ csak szavazókör-határon mozdulhat, és az NVI szavazókör-térképei egyszerűsítettek.
  A két új budapesti kerületrész leírását az OSM utcatengelyeivel és házszámos címeivel ellenőriztem;
  hivatalos (földhivatali) térképpel nem vetettem össze.
- A nemzetiségi közösségeket a 2022-es népszámlálás alapján mértük: a négy érintett megyében ma 2,
  a javaslatban 1 nemzetiségi „tömböt” (legalább két szomszédos település, legalább 10% azonos
  nemzetiségű lakossággal) vág ketté körzethatár.

## Az eredmény fájljai

A végeredmény a repóban is megtalálható, a számítás újrafuttatása nélkül:

| Fájl | Tartalom |
| --- | --- |
| [`data/interim/melleklet/OEVK_2026_mellekletek.docx`](data/interim/melleklet/OEVK_2026_mellekletek.docx) | a Vjt. 1. és 2. mellékletének teljes, módosított szövege (Word) |
| [`data/interim/export/oevk_javaslat_2026.zip`](data/interim/export/oevk_javaslat_2026.zip) | térképi export (shapefile, EOV): a mai körzetek, a javaslat és az egységek; leírás az `OLVASSEL.txt`-ben |
| `data/interim/javaslat/<megye>_<körzetszám>.csv` | a négy érintett megye terve egységenként (`unit_id`, `regi` = mai körzet, `uj` = javasolt körzet) |
| `data/interim/javaslat/<megye>_<körzetszám>.png` | a terv térképe |
| `data/interim/javaslat/<megye>_<körzetszám>_meroszam.csv` | mérőszámok: áthelyezett választók, körzetenkénti létszám és eltérés, székhelyek |

## Replikálás

A teljes számítás bárki által megismételhető; minden bemenet nyilvános.

**Szükséges:** Python 3.11+ (3.13-mal teszteltük), kb. 2 GB szabad hely, internet. A Word-fájlhoz
Node.js 18+. Windowson és Linuxon is fut.

```
python -m venv .venv
.venv\Scripts\activate            # Linuxon: source .venv/bin/activate
pip install -r requirements.txt
```

**Kézzel letöltendő** (a többit a szkript tölti le):

| Fájl | Hová | Honnan |
| --- | --- | --- |
| OpenStreetMap Magyarország (`hungary-latest.osm.pbf`, kb. 300 MB) | `data/raw/osm/` | <https://download.geofabrik.de/europe/hungary-latest.osm.pbf> |

A **KSH népszámlálási adatai** (2022, „A népesség adatai településenként” tábla, WBS003) egy
lekérdezésben túl nagyok, ezért öt részletben, régiónként kell letölteni őket. Lépések minden sorra:

1. A „lekérdezés” linkre kattintva a KSH népszámlálási adatbázisa pontosan azzal a beállítással nyílik
   meg, amellyel a számításhoz letöltöttük (régió, településenként, a nemzetiségi jellemzők összes oszlopa).
2. A táblát Excel-fájlként kell letölteni.
3. A fájlt a megadott néven a `data/raw/ksh/` mappába kell menteni.

| Fájlnév | Régió | Megyék | Letöltés |
| --- | --- | --- | --- |
| `2022-nemzetiseg-01.xlsx` | Közép-Magyarország, Közép-Dunántúl | Budapest, Pest, Fejér, Komárom-Esztergom, Veszprém | [lekérdezés][ksh01] |
| `2022-nemzetiseg-02.xlsx` | Nyugat-Dunántúl | Győr-Moson-Sopron, Vas, Zala | [lekérdezés][ksh02] |
| `2022-nemzetiseg-03.xlsx` | Dél-Dunántúl | Baranya, Somogy, Tolna | [lekérdezés][ksh03] |
| `2022-nemzetiseg-04.xlsx` | Észak-Magyarország, Észak-Alföld | Borsod-Abaúj-Zemplén, Heves, Nógrád, Hajdú-Bihar, Jász-Nagykun-Szolnok, Szabolcs-Szatmár-Bereg | [lekérdezés][ksh04] |
| `2022-nemzetiseg-05.xlsx` | Dél-Alföld | Bács-Kiskun, Békés, Csongrád-Csanád | [lekérdezés][ksh05] |

A számításhoz a „Nemzetiséghez tartozás az összes kérdés alapján” blokk kell, az összesen-oszloppal
együtt (ez a település népessége, a nemzetiségi arányok nevezője). Ha ez hiányzik, a program
hibaüzenettel jelzi. A letöltött fájl „Adatlap” munkalapján a „Forrás cím” sor mutatja, melyik
lekérdezésből készült.

**Futtatás, sorrendben:**

```
python scripts/letoltes.py mind     # NVI, Lechner, KSH, jogszabályszöveg (kb. 360 MB; 30–60 perc)
python -m oevk.egysegek             # építőkövek: települések + szavazókörök
python -m oevk.graf                 # szomszédság, hidak és kompok
python -m oevk.javaslat             # a javaslat megyénként (8 magos gépen kb. 15 perc)
python -m oevk.melleklet            # a módosított 1. és 2. melléklet szövege (json)
python -m oevk.export               # térképi export (shapefile, EOV) GIS-programokhoz
```

A Word (a két melléklet teljes, módosított szövege, `data/interim/melleklet/OEVK_2026_mellekletek.docx`):
`npm install docx@9.5.1`, majd `node scripts/melleklet_docx.js`.
A beállítások próbája: `python -m oevk.kalibral <eset> [--tures] [--hess] [--kappa] …`
(lásd a fájl elején).

Minden paraméter és döntés a `config.yaml`-ban van. A letöltött fájlok URL-jét, méretét és
ellenőrzőösszegét a `data/manifest/` rögzíti, így ellenőrizhető, hogy ugyanazokkal az adatokkal
számolunk. Mivel a végleges megoldások bizonyítottan optimálisak, az újrafuttatás ugyanazt a
célértéket adja; ahol több egyformán jó megoldás van, a kiválasztott beosztás apróbb részletekben
eltérhet.

## A repó felépítése

```
config.yaml              minden paraméter és döntés (körzetszámok, tűrés, tömörségi súlyok)
scripts/letoltes.py      a nyilvános adatok letöltése, ellenőrzőösszeggel
scripts/melleklet_docx.js  a Vjt. 1. és 2. melléklete módosított, egységes szövegben (Word)
oevk/adat.py             adatbetöltés (NVI, Lechner, KSH)
oevk/egysegek.py         építőkövek: települések és szavazókörök térképe, létszámmal
oevk/graf.py             szomszédsági gráf; folyón át csak híd vagy komp
oevk/modell.py           a megyénkénti optimalizálás (HiGHS)
oevk/javaslat.py         a végleges javaslat kiszámítása a config.yaml szerint
oevk/kalibral.py         egy beállítás kipróbálása, térképpel
oevk/melleklet.py        a Vjt. 1. és 2. mellékletének módosított szövege (json), a térképes jelölésekkel
oevk/export.py           shapefile-export (ArcMap, QGIS)
oevk/kiadvany.py         a csapaton belüli bemutató oldal (a sablon nincs a repóban)
data/manifest/           a letöltések jegyzéke (URL, méret, SHA-256)
data/manual/             kézi kivételek a szomszédsághoz; a budapesti kerületrészek kézi leírása (melleklet_kezi.yaml)
data/raw/, data/interim/ letöltött és számított adat (a szkriptek előállítják; a repóban csak a fenti
                         eredményfájlok vannak)
```

## Hogyan dolgoztunk: emberi munka és MI-segítség

A javaslatban szereplő választókerületek kidolgozása Miklós Gyula feladata volt. A munkához egy
MI-alapú programozási asszisztenst (Claude, Anthropic) is használtunk, eszközként. A munka így
oszlott meg:

- **Tervezés és döntések (Miklós Gyula):** a feladat értelmezése a csapat anyaga alapján; az
  alapelvek (106 körzet marad, csak a korlátot sértő helyeken változtatunk); a forgatókönyvek és a
  végső választások, például Tolna két körzete, Somogy három körzete a ±15% miatt, Budapesten a teljes
  XVIII. kerület a folytonosság miatt, a budapesti kerületrészek határvonalas leírása; az adatforrások kiválasztása és a kézi letöltések; az egyeztetés a
  csapattal.
- **Ellenőrzés (Miklós Gyula):** a fontosabb esetek térképeinek és a szövegeknek az átnézése, és
  ezek alapján a döntések. Több kört is visszaküldött: a nyúlványos körzeteket, a gyenge szemléltetést, a pontatlan vagy túlzó
  megfogalmazásokat. A tömörségi módszer ennek nyomán többször is átdolgozásra került.
- **Kódolás, számítás és dokumentáció (MI-asszisztens, irányítással):** a kód nagy részének
  megírása, a számítások futtatása, módszertani javaslatok (pl. a Hess-modell), szakirodalom-keresés,
  szövegtervezetek és a dokumentáció megírása. Minden javaslatot ember fogadott el vagy vetett el.

A döntésekért és az eredményért a csapat felel. A teljes számítás nyílt adatból, nyílt kóddal,
bárki által megismételhető; ez az átláthatóság a javaslat egyik fő érve.

## Adatforrások és licencek

- Nemzeti Választási Iroda, [valasztas.hu](https://www.valasztas.hu): 2026-os és 2022-es névjegyzék,
  szavazókörök, szavazóköri térképek és utcajegyzék (közadat).
- Lechner Tudásközpont: közigazgatási határok és vízrajz, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- © OpenStreetMap-közreműködők: hidak, kompok, utcatengelyek, [ODbL](https://opendatacommons.org/licenses/odbl/).
- Központi Statisztikai Hivatal: Helységnévtár 2026, népszámlálás 2022.
- 2011. évi CCIII. törvény (Vjt.) hatályos szövege ([net.jogtar.hu](https://net.jogtar.hu/jogszabaly?docid=a1100203.tv)).
- Szakirodalom: Sziklai–Kóczy (ELTE KRTK Policy Brief No. 3, 2026); Bódi–Kovalcsik (Területi Statisztika,
  2024); Kovalcsik–Vida–Dudás (Területi Statisztika, 2019); a Velencei Bizottság választási
  ajánlásai (Code of Good Practice in Electoral Matters).

[ksh01]: https://nepszamlalas2022.ksh.hu/adatbazis/#/table/WBS003/N4IgFgpghgJiBcBtEAVAogGQPoGUBaWAggCKEogC6ANCAM4CWMECyKAkgLJpYAKaASmwDyxEDXT8AqtgDiaIQFZKNWhADGAF3oB7AHYtqIAGb0ANhogAnWglABrerrjwQHKAAcxICLo2X6EDZIrJzcfIIiYvaOziA4EBpeAG5QpgCugSwgAEwADNnZlAC-1KwC0lhyilEgDk4IcQnJqRlByAASkgCMXblenV15Xrm5XcP54wDM4wAs40o0IwBs4wDs4wAc4wCcw717Y4uDe9NHc0cLIKMrR-tHW0e7i0PPh1cFw9mnINu_w9sKJY3K6TLqrJ4gLobXJLCG5BQzJZ3SGTSbbQo0LpLBQbYHZbarGbnHII-FefE44G9VYjLxdGbZLHkxEE5n4iFY1HInqg4m5DZ5B7vHoYnLojaXXIzUZvGH5KmgjYc_L0ryTGZdNF0yYKVZCwaiwbfQbEwaXQZU7Lc7L6_HavqY0Haw2o7WmnXahXcyb6rWYpZQoW5baa2UzaH6gG5b5Wwa-7YzOGo2k0SYw7bA4MKbbfNOot4FcNBjZK2Xq3LW-Gir5WoWohQKUXB35vLoKfLEm1Qy7q0GSgXQ5mN5HZdvq8l61ai0HY42ajXkmHS4YKKHExU9Om9KVq_GrS7ZIlAz6rWHkvL8ul6y-pvJW_6H5HBjaJ3e9YGTAppldd8lpjbfPyqLVqsPqZks-LGhmApqqCUJ0riTK3gGDo5JMSyvjQh6jLmz76g2AHDEsL6oWCoJNhqCJERKEIFNCpoAayjrhqhn4NnC17IuqWIfpR3KrHqMblnC0q6uS9I4v8vSmvu2z6gBDLntGB6gn8ixLMp5KAveizSvuWnPghMynv8RIFgSHpYXqOmQvCq5qjMaIjnmQoFIerlrk-cmMueOKSiGHyppqAbDOh6JupZORgpqwz7opWG4goxrtm2V55qZZJBeCVIaoidIzLqBb0ki5K4kSu4Ca2BJITkyx4hmoyxfS665fqjnLosjbbKRmoZrFPp8qsvT6l0ObrjqIWYqMN5ihh3L8jVwb0qhUpojJ2QaeSEHZrFGw0nSq4SuePSduqSyAcRgUkuh1Zye2ar8sGCGgbKL5ibp3WSudU4HUSqEbYyuajedpUaoBvygf8OKdvC46LBm3V0hWDbOgJpUAuuFYvGKArGntaMJcGT6Jnq57qj2kyga5iLguel3DAV-2YsZ-lZZ-DNQgWiaLbCxl0ui4ZI6BXGU3azMNQhuq5o5rpYbCR2OhSP42VaxFPhKBUIcRtGaiWDPpc8lOkRtiMJbieKJnDVzZmC_MlpmgJyVeQLU4dSPooaNoJltGypTQnSMm8AfHP7kiA7FT6k4stOLIOsevU2L7DArkL7Jim7p4aMXp-aqqYoR-cMeauLPQh8kcqbkIhvzhqriZU3hq2WKHg9CIwyMTZfDV7J-pCur3Vh6qV72ML8wiHJHuahIwc8-6kT6TFXEqo6xVK6uIlS515am7VNnBB7Kb6iKe-dvF5By-6NqvjVy_O_M6p23XwfD3WsVaSWfNC1ZKpXyOj9HJs6S8yDICJURFdRUj2h1Wy-I8SjQ2hObMtF-5FT1DlAErY2LIOuKFRMdYGQg1jjiAs6FowHRDB5dUFFsRwjyH7KKIxJQ4jFkvUCrEehkPzqOPkSVNpYVGjNT8eRAIFBTO8XsE4kTyXDCpHE-oBKEk_jmH2LcsKNgLiiNs1YqH8SpuSbq6FdzoVOrzE8XwtLqnXG2H0nwCoX0pniPs4MBJwiRFbGEJ1dyjHwgSQ0LtcLYlIiGPOJIhrmjRJwnIJZBaYn3CvIKX9PiwmQctLcAk8T5H_iAVEn4Cx7UypCcMKt0QlViRBacHZpYFG5EicqWEcwo3ziU88IZSJSl_jQx-51XKridPU3U3JGyNJJOGEcG1KalVHAeGk9c-46mrFCRRzMgS0VhJE_kxFiz7jam2Hs0pzFWXOoaX2vcYT00HhKasDI6kkgKLRL4vtk4QVNBhGq-YnpcJ-upIEppmxT2TA9UY05RqV3PntXclIGYMjrF8beVd0JAwZNOYx_1gwHOtkSVZOZ_pfC-VcF6bx8yEKuAVeJ-LzqsQrMeVMOoeaNibqWVuH8aXc3EgyVsSpIqc3epCKc9lMTqOBRtR-jJkUAQPBqG-7xVyos5LBAUeINqjQegUA-gwRwZhYWcyGWF8j8pgQPfFSo6yjB1bVRyI5pQ7gSiKIBsJqz8mZfimEez2UrgAq5BMk13iMjhKuGJkINJ4sPGFFcbrdJnIZg2JsoEA1pkbJmUCvdRz_lCljcSYIp5tk7BKKVuzsSfG7ERBFK5ASdlHCHNCIZjQjHCrEmU54CpllAVuBEU9owQjTIic0QJASLgVWqTUFZSpGwZqeHsXYc24t3KrJG-T5VDVKqMc0IYFyx0JMg7Ej902DxpCtaFrk0xSrTFCECBIdbSmNMZHlWJswHiVHi-EbYRwDNWY7fKIaGbnVlFGGNaZbq9NijaJ8RyNXdW0R7LaGpLWDHuU_Cc8IYV7Vcsux-xk2lEnNFaeKVx0R1sDUNEcepn5V1jXSR8rkt2tgDDh-E_IRzfT5OhNOYp8TltEX-QE-6Xacf1duKV_IAZaToSubECzZJI2lG-9F-Ja2DoTCu3EI0JQHixMOoKUztRmmZKeEcYICY5AgtawzGFqbYllISGyq0fKpjRTJMExzRoxlxIugV_Igx8tIgyJmJK5JPgbMM0cL5kHZkAklPWU0XV_mmvfQx9TfgxinOp7JeZaI6kXlKQEBYaxPk_KUyEX4gwIrrANPkAJsYdiukFyJEknXwi3ltaMkccwkIKp2Py8jdT_WBoaScYYkqdmlNA_Ik5QZXQ7QG-rZK0zgmNJTR9NJ8PuWrrE3J-j2oOUZEGCyxoNpURpeqq8FrmQwh6QVViDJ9u1S61uRyHIuvmmg8lASJWEytl4QWBs1K0LYhQ_uD8BRK2xgmZiEMfVXje3TgyFapCLOQf9BtJ8sZTRgny4yRyPUaRCUJHiJBhKpQsbotnbJeqrkYWBckz4OZIESkcVCf65nTQNj5oPVcPbwyrMTLsCgJQqBlGwPgIgpByBUGiPUFw8REg0BSOkTISAQAADk0AcDwF4AAQmgGQXhNfa5kFgTouusCiBoJrrAQhDcK8IIbtXkhDcyDYHb_ghuADCTuTd654Ob93lQ0CG8IG7kApv-Be8D3rqQhucC--9zgAA0hHjAhvJBx5oBrvXBuU-m-NyAVPZv1em8t3nvXNvC-VAdxnvXMgA859dyXz3Je5Al_9yX4Pzfbfl9wFH7PpvY8l5wAn9vSfigUB50UIAA
[ksh02]: https://nepszamlalas2022.ksh.hu/adatbazis/#/table/WBS003/N4IgFgpghgJiBcBtEAVAogGQPoGUBaWAggCKEogC6ANCAM4CWMECyKAkgLJpYAKaASmwDyxEDXT8AqtgDiaIQFZKNWhADGAF3oB7AHYtqIAGb0ANhogAnWglABrerrjwQHKAAcxICLo2X6EDZIrJzcfIIiYvaOziA4EBpeAG5QpgCugSwgAEwADNnZlAC-1KwC0lhyilEgDk4IcQnJqRlByAASkgUAjF6dBYU0_dkAzF65ABwAbOMTAOyzE7MAnOPLuWu9NLnLgyDdczM0BwvHc0tnq8cTG9db-xN73ctjx8sALF7PSm9H-8unf4XEAjUETH45eZTK4gXJTZ5_OEFW6w94jKaA7oKBS5e7ZOaTCG5d65EYw7LPA5ePLZCbA0HLZaIqZTd5_brdbJTPZc958r5kznjDEEr5MkaA0bvCZ4uYjYnjd5zXbUpUU6m49FfBT4177BTvArjCUKPXZQ2TcZcqnbcFat5cxGg1mKg57fKjTFTaYwjl0p65BRTFEMnHC-Hk7q5c7a-YQrGkvVw5ZBq1wlHZbETT7HEbPendPPsl47cZzaX3PPnTE62ka4M5_YUwvU2nTVVTUFeItcr60oU0Z1zQH5dGVkYGvWclNErkT7U68mm-eDsnQvvczHdd4KL0YxucklEnHb6kfaPa4kBhR07UpxsjTMp1t8nkjbNJkl5L65fLkiagg-6LPjQFLLDc2qcvc27KlOfLvtqcynts3Jkl85wQdsO4TEuyqStC6qgeBgbUt00wQvicowvk0a-sSBrdviNo5Bi6x9vKwIHOsFG7IRIJogo0FKtKZYyn8zremKoy-tyfGcrSZpygo1FKgB1Iyu8MIjHyA5NkyjZcjegJ5gBvrZrptIvH8yLcuMyn8scGKWoOcIxracx8cSErFnMOqqvK8ZMRRZG4uhOIjtMcJfIa8KkQC47LMhORcolip0iiUbEhFQZ6vKlLUp2Srap6Xycqaax0kSHzzD-Uw3n27xJVi2m5duJLoUy1GHJpXzZqS1Kgr53bdJ2RLeiBIIch8VqaRCj4vOSLx1qBEpyq2AFCd6xmFqK2zDmypVwvSv6eeCZFnjsGa7uapXAWKGJmrRTyds8iqyYx5q-hOJGrpmeLesGGokhlQblds5otqBpLgla2LiRKoWrkhGUeQCxp0pi6wrjkuz9ds8psaBBLTaB0kon--I_qMTwjcqP6JbleT2vs0Icn25qYtpvZQ4y1l8tmGqTI2OwvCOylg6izwZdKpbHNdZrwmixr7lapmMdyvokhi1LDi8awFNReaGuhNHGol0HKYTOTJkS8rM_KhpLh8iI3JDOPmWeO4BhiiK7m726MsZ-Qjb1pI8mRCF7QC23ehmLLfqTSHWXVTJioc0EckVuamjyHk4ehbbUgaozGtkJOwhiIeDmXCf6umZ4-msGJPNpEtRp2GZ5s5FfmsC0bYtBdUKscHpTsOZcze1bw6vc-R0geH7k8qU-wjiJfg2is-PEhfbbhlzxK45GNnjiB4Gu2R-PnZ5Zx8S1m4rLOOTEJwcDY-GZ5A5sJ0o8P55pWJIarbEEiyAqv4MrQ2FgaQ4pU6qz1RoicCMDQIindOsXaLEsQ0yxOJCkt4obpVukAiuWszwphHJmcs3ZJgeSLocEMZEhrbF2GpFB5oIEflbCZPsXlorgWBGXHC7Igw7xQdGXKkwZTqW5OyQMdNQKFiiigw4EjywCMEblKsTxRjYwpKabagZZ6JQms1bSGptKRlZGaTMPVbTzE_AUAyj5iEEyUf8VuAo56lz4nmOGJs9bKOZqMaY_0bj3yWsNG8U4Rpdj2hSKBUZ3SditvNAWK0xJfHhIJAURlVQRx1qSDKuopxknquDE8jEAJPDlNrcGV5VQ4nJEeL63oDKklqfsZUqcR7KUxD_Kc-Q3KwiQqInIypAZEQIqqG4GYyrC3lI_EaFI9jvx3A3IZTNy7ygJDyZSv8iISinBSYesJHHJxiuzFUidMzsWYo-Q8YppScXxDdMRLpQLzG6SCHYxtmEeWFo8bmqJWQhkDIyaZEo06H2GSyEcScabXTLPiPueY0Z_PwWMwOJ9JJYWhHNPIUizgnTFLsLqhYKLzA2TFJ4u51zHBGr862pJySgnyOjJqNxGq9UNHiR4v5GLVQGjhTimk3GjE5LI708ZGr7JBPEpJBpfQhSKcY9CwNFTEuuIcekzjOIE2gocl2hwtxgp1nySUOwwxYRibDVhON0QGRvDDFyOEUYgJyXSoEJiyR8T0fyrCSozTVV9IJCyBKQy8k5oGeMHEVkDFlNKaJSpAq7gpbTFYVdJrgTxPEysjpbYTiJLNDMiUJks3BBGwSU4CLS0EZEq5nS_SlWxAvOqPJ4SxTOHaRUnV1aR2GbuckvlbL4w8i7NEZloQCKNgeX8qYo4XxBGSIZlqmEs0-hqD4s8WoHmWQGOk1FjlmijElWiOKl1IKLqpahvkRx1XlNQrFtosnRQKPGTssq_puy5FyPumYJ6gR3FbMijxySshHbCUtBYy54g5GhFChYkkHAETBYsjDMmmmgmXVKxwy4HVw5Mai6x84jxStMta9KCWtiZHNLBWkCgdMfGOou-RZzrC-nCAyvkgX_qjH2ehj7YksyrXw-RQJlIsb8pM-dk0OQ8jZGWiG_asR-JQiImaJzowEgjc8Lc5x4ykhEoOEazE_y0NJh8PpQYF47EQe-cmvInHvgPCmCyEqJHoj7oGzijS-noiKQBN10KoznB5LSYc9Zv0tUlbY2TsX8SaTjQSHVho-5hM4unINw5Z55DRU2U0dEXi8sfLbEDjE4RmlNBLdMoyKQSnJKSXSI1n6PLE4NBthSGLg3joqYdGobzkgpCuvk2J1Jsj7h2rqdVOI3HXjkIMj9JimtAgaJKBLdGfT6SmVq5Y8RKmQfsNU5NdwnMpBsqMVrIPTElOWOqBVkk6w8uTGUiN_hLeNA8lyrlSojSJP6ARypsnAK5n_Nlxw0RGltHdD5s0ZqLvfl1nI74zFHy-YeL5ds3agkLIiLk3dCx5W5fFpkdre7vOGaFzJv5qLYkhdXdYaCZTPQdVaRRdk8GPbXeaJi0VCSkWXf16FHM8ZNmDE02klbIfDOpibXcxRSioEwLgAgJAyA1DqLEeIiQaApHSJkJAIAAByaAOB4C8AAITQDILwVubcyCwJ0O3WBRA0Ct1gIQTvDeECd-byQTuZBsH9_wJ3ABhYPrv7c8A9xHyoaAneEHDyAN3_Bo9J_t1IJ3OA48x5wAAaUzxgJ3kh880Et_bx3pe3cu5AGX93Fu3de_r_b33TfKiB8r_bmQifa9h9b1H1vchW8J9bynkffuO-4GzzXt3efW84ELxP4v8uKBFCKEAA=
[ksh03]: https://nepszamlalas2022.ksh.hu/adatbazis/#/table/WBS003/N4IgFgpghgJiBcBtEAVAogGQPoGUBaWAggCKEogC6ANCAM4CWMECyKAkgLJpYAKaASmwDyxEDXT8AqtgDiaIQFZKNWhADGAF3oB7AHYtqIAGb0ANhogAnWglABrerrjwQHKAAcxICLo2X6EDZIrJzcfIIiYvaOziA4EBpeAG5QpgCugSwgAEwADNnZlAC-1KwC0lhyilEgDk4IcQnJqRlByAASktkAzACMXp09hTSD3d1e-QAsE9lKNPkAbDMA7DMAHDMAnBPduTv9893DILljXr2TezQXByAXxxfj15PTz3N3k0vPq9fLV3fLW69ZYPZZPAGvAHvXIKS7g3qbXK5DY0Ma9WETBYg97ZZZrNa3AprBYou5I7qki6TNbwhb5H4nbqbNaQ3prBQcrwFbILL4nFnLaEKOkM3KTXrdPkI7FchQE0EUnEFQVcybLSbbeaw9nnI7E3XdNVeMY9cEwkHHXIkvoTTbazEE8G7DWWw1_c4LbI665euVc7rLBaQo69OlcwXI87C7o45Z_Y4FSbZSG-7Kak4FIMTP7qibUzbpsZIhPq3K3XZ224wgvpnmXUmzZMM4F0lObQVm2G7Lk8pHGpk9fuCqUXfJ56mWxG5UVg3lDhbQy7U1WXBOTAOU8UI21svmzNbZKuTLu2haS8ObM40NObOeHQ18k3o854gv9os99spvFnrkFvL-na6YXAu_y9GWMZcsinr9hO_pqq6ZaUligLnL0h6ii8AZQbiwGzMu8wkvq17sjSEwHm-1xBgsVYKBKhaHnR5zriSOxrLeXLsWymK5JRIDOhS5w0s-qLIueqKPFWFJHB67bvBcdGime4mMrCYEcoJhH_saErseGVrNrxlw7HiYHAt21ybOKOLgRxVG9CJdxeliL7JgmChpmu7JKrMoqXpGlnCaqgIJgUDnZgsVnhmmlJrH8rKGnxwI0tCvpKcszLnJsEoPCSMKqp6kL5ESuovKyzJxucdbybenznMisyySyUYsqSVrEm1TIqteYpZqJYq1mymwPFaUWWYiQLqtuqI9NlO4KINkVtfi013DSV45OBg6HL6mLWZir5CYiy0LlWBLgUJxJCuKlrrt6dxBuuUaHsB52Eu1UrEjR2Zlv8PQKFaQkwn9cXijpgIJViOK8XinEKJpa10bWdEFP2uGnr-EnDQyybDfJ4HEfxVoXMaPRgpxNE4_KhK4oaVUUiDdKkrspxgUGmXzMO_xFs117ol6OmXnuBYEYyYzNuqfVkrCDwOWR17xkCXoall2V_aGob7Ex1zTnV15Jjye0ZbKwJ-cef1WgtUYwlWPLw5x2NcsCYrZui8Lw3pM1JvjdFtRyq1DPl8z4n2qJwscfRWtzuIvEJcqWnSMEkVMEwebxqfsQ8aIW-xtZ9EnORM6FCiBmhdoPLi2s5CyLu_Ai_zTuhfJimmOMwh55GGoS6KrfksLNgDxszUi6a8WspwtXeOR5KhPp5ECJq1qcpec3S7savJfSa9cYwLtm8Pgoxc07-yVZxuTJG0z2vLBkyMnXrsuaorsU-jXvwclxHTJB05MaHzGSZsxghxuXBMdpjLP1zuGUMrJxTHzWj0PcZ40wvgymAwMt06J7gZiA-4sppzqy9OWSUEoPQxhxAuWGWoPKUjUsGGeCZIpjX5LpVU5dUFGlEmqehGVR6RQutceUDcFqz34hKDuO8aJAjlLzHI1I9Z3GygDJ2YwzQ0R_siLctpSIen3GhMU6kFpgOlJxEhUFPQJlOIeVOANo4siBGPKUQZpx_lMsaMsAcJSOXAmvdxt4wK3gDnGWRPJdhAkuOhcMGk0IHkpHfEGdE_oAyetcC4sixTsnhOidOzxPROheBPSB9seogkLBSAu5k_S5PvicIMVdZq1zWmeIqHlMZEwPM2akbSeRQw9AeM0fxhRcjPMNUmapo50m7uyKUVlAGpPAlWEklUw5siKgGSCM1xb1QBkg3Eoo4qFJyMKAk5EDEzDVDjdcJMdbEikvmXUzIlSLE4nWTEcpoTZWWUTEuhI5QWQeiCZuIsgXDUpA5UZ1wjES3RteOpZpEQc2rudWUxJmw9PhAeXEUYwSWLVGopMKYiKbnKVlGEZoJxSg3AvdU8kW443hqIxB_zdjshTLxH-fRDSH1DBIzaLxazHhUtKd0YcxSLJuFVUMcSMrc2gk6HkT8xHoXLLiceuoDzBmVa9acDZTj_K9LeQ-cVtqMnFFKakGJIXgUPiXQGPp2zys-EeS8loQQ_wVScyyZYcaBmuYXFka4HJgXVPA2mXzpwBnkseAuh4jisiDCKwu8NXS8Oiom5ULjYXckxIecs05uoQgUQ5YE9DyFx1Dg9Hxso07Zmyjauik1hQOKAqSw28w8hV3RJ6PcHZoS8grRkjZTTM1ExAhnARciaKb0ivCPEsd5jYyKgSeWJxapRqZPJEKzYmTMIUnxZENIGRd0vKqCkVN2RUzTJNKyKrx7vBDI5YGVDC6Cm_JKWKsI9wXvjWCPtyIAmfAboCYEZdt4PUmWwkdRJUaHA5AK48mEFq0MSUJNJf4rSH2rJ1PI_8t7MSsqCM8hIKy3XQkepMQqkYpiZKxQiSIGxxT9V6fOUFAR_QVU6GBLTcRfyZC0mMhJ-XwiRBO1RK87gLRyfxWNToYRqshcyd65oqpxWbkjM07JERjLAws4pOQR5ZM-I-XYJdhnoRxOxKTVoNSdOXVlZWLUAKwpBPS-GtY4zhXbXqp2YJJpsbeZEiSbIcQvE8_pv4xDEq6k9GBLinTWYemPBHPdpN2RgXXI0w8np7203xgWZmI82w9CAySVKwp72nCtguo42C0yfVvKFdcmHB7MTpKlDKUp6OH2ysmMuibLZVLEQDKsdomSp18_TNtHxwJ_UvNhQRFJaFImbl0ycAYgQFgRnkAkSkJp_l5D7NpDkQrkWJCmDUntptS1OMSYCvVZPCktOxb6z9bV5nVPSupzFgN9KY7iF7q7xQpi-rLIi9mxzBxeJSDKfrgR2llQa4Z7d3tln9DDl8zjwyBj3HLIqkzRRELPvkdzbIE6-t1H8UewoAe8RopSO0910THiXnid2LH5gvClqT7p0asmnG7pKC2TbMRnlFIaRq-sEQPHYvJo5MdiilFQJgXABASBkBqHUWI8REg0BSOkTISAQAADk0AcDwF4AAQmgGQXhre25kFgTo9usCiBoNbrAQhndG8IM7i3khncyDYAH_gzuADCIe3cO54J7yPlQ0DO8IBHkA7v-Ax-Tw7qQzucDx9jzgAA0lnjAzvJAF5oFbh3Tuy_u9dyAcvHvLfu-9w3h3fvm-VCD1Xh3Mgk91_D236Pbe5Bt8T231Po__ed9wDn2v7v89t5wEXyfJeFcUCKEUIAA===
[ksh04]: https://nepszamlalas2022.ksh.hu/adatbazis/#/table/WBS003/N4IgFgpghgJiBcBtEAVAogGQPoGUBaWAggCKEogC6ANCAM4CWMECyKAkgLJpYAKaASmwDyxEDXT8AqtgDiaIQFZKNWhADGAF3oB7AHYtqIAGb0ANhogAnWglABrerrjwQHKAAcxICLo2X6EDZIrJzcfIIiYvaOziA4EBpeAG5QpgCugSwgAEwADNnZlAC-1KwC0lhyilEgDk4IcQnJqRlByAASkgDMAIw9Xp29hTSDPV1euQoALBMKSjSTAGyzAOyzAByzAJwTi7m7_QuLwyC5i-NHM0fzp4vLR2tHm0c7ND25FyDvV1-TXu_3X6PX7PX6vL49QF9YF9UF9cE9PL_bKHHJdFboiZdLbYiYrFY9cEolGgrqTXJwnpTKagvLraleLq9daonoKdY4iY4nowrYFfY0bLouZebJbMafMZbFaA3p7OEfBTAgoKFGila5KZElZTMWMpkfbbZQEU7FQxYrLYIsYKAUgXpbab_XIrbJwpkKKF8zlvRHGibZKaLWme12zXJ_N5nRGi469f7spUB_I_aHsia6tn6qaE0XSnn_RYSxkquEWhSfCku5U6z2iikE_5Un1fIuWvHrDmioNnUXrc43Kkcu2Qrb5Z3C_6d3Ko7IrdZdWWTAtRqk_D6O3lzwfUvVvFn0vMWn5C6XAilaysVpnO1U_A00gM61nZObK6UUxmahei4mfN0Yic7xjieNLrEBBKLv8Wz0naVb9qKSq6v8Gp3NBSqAm6KJEp6PS0gS4olsGkrTGMjLvFmCwwWSCZ3CcxoEqCiqOgGc7_kWMETJ2QZTlsDJvNSOpcjqEE4vRuRbIsCIKDiUL9lM_4kjC7K4lR2JElqGpNlJynGieYp1lGkm0lMGJ2oGupwbB9FdDm7oyv-Y5Or67Kzu86wwu8BT6hJlbgSuOQKGy4K2WKcFBghNByo2CxzIRRxSayeG5gJ4o3Ci0yYeKnaMlMZxEmSe72jmSKrjFpxdMS_wKWRbx7M5EJ9COpmHgsrpCli4H_uiKWtvO5kVla_xdAulY9TCI05VFHz4ohhKDkWga7BqE0ybKboebs0onm-Ny2X0qKTP2e1ii2fSVZKfE3vu6LWjqGlsiaplFQUo5ThyJwUpCe2aqZrHxWCs3TS6mHvJVWL4rOA4mhWvaCvOY5cfkn1BkDpxuo-byep-sX0sqOaLHtiIRr-sHIupJZarSdzjvD2I_VMhlfBt6WvumgrGm6sa1qK8KfMyrUVbaJ4YvGCxkiyvMWuZUlauqPKKaZCLrBWMJ3CNXEfvWGLusaTF8ZJyI0sqyXNUyqJknc4KTL0P15LyeWYfSMnVW6OFSXaoVhoKQWarGhMwqZtOnBqGuCusHyStSfIBh5g4LkFXKLvRnaqTk82Vot_4ylJ5Guvzc7HMJcOnBHft1Uqyr5NdXyehHeIyqmeS2SWEnmc-cH1SRfGDhKNnzvR-JJlFr5ixVkLheK66W5d7w7nls6voasX5ciqFfmM57TOzrZxdBeyezy871kFmE6kJ4fLl-EYkc24aG1jbb1jSNkFPz7wl19F8h-yIZCnCBIJK7B7E2dECpFyyj6BaPscc-zTHxqPBMEVYwKUHEKIubwNSY1OEFUqOQ0ovhgkBSSix1xSSKmMMYqZIR7CxGOeiPJgxYmpJWAe6VETe2ZkGEKLo054UDOlDym1xbFjeK9cyC5OILCwjLJktIYJUgzEKbq15ZhahPAuF0EN-I5EtMhQU_CiSIigm8Jk38ZoYK-B5by4sKyHTHJCWMtobi_V6sY8qDogE-xGlZKk556SCxRF0ROBjPRkMJi4ns64CjgWRMFPMgYEQYjltItkTE5ixNigI2OaEFgsiKmSWycEfEuP7DXN0wSThknnPeHxtJqw7UqrKEaAVbbvAhjjdOOoRw4kltNMUcJNFQjZHODMeVPZNPMnkIaUVESZPtI9QRWFZikMlJaYROQ8o2NLjTZ-AM5lqkFHsNxdx2mClMjvMYpD6nn0LJVBUgZZwR3bPDKSZ96rvTOfgwu6oUQmjkUBSplYnL0RzH9I4tl0orCCsCQqRYAwKKxD8kePJpLVNFOpdKtouyzLos6Oyv5CQmkYiOCiwLJIizjN2OYJ5Ko5kLG3LkeRDrQsojg9BKEKypiZGHUuF1oLGL7BSSkOZDoyWCciW0QElQP13nlPMmp0rBheQsmksoFJLQEuyOCSoXazMDP8oKrDHnMNVIWekrJGKLzJESFMKMqR7QUiqskC9uxXX1MGd5touREN5u1XYtpFLBNAkKdKM48LVVVE9C8U43SskZhKt4jpoEjxIRi2ycISplgnihSEUcQZ4lNBi6kO4cSVjFOcZ0xwnlzChIGcGUYXTco8kSA1PTJI7msXiBSmF8hsuJlpKiexrYq1GXVM4koLqsjpSOAoL0NQxlMQHZEM4TT_yMTiVmMkTwzkZuGb1bVKqzqCodFkTMMrzNfOrWYdLhp5FTMq6mo0Jhsk6WKB0lMtHwzSiWMk5lqKfTpdbAiIVJojmFLSzUMIhFPXpLUrl3YFK2pdIOHEnCPSvg3iTeG2q-yEnXDKQ59oxR9E6vSgSQp7z5EHcRj9CxdQhK-DKPVORjQigMZaPa5sgL0j4nQlsDZF07P0bo-tw16TEMZodBSNFcY_janlBEM4Znp3OKmEC943ZLh_XVBj3Z9pcg-OuGCfGHgKX0x1UxjFyI5klHhHiUUj1LnphimCJppTSgzMEpiC4Nlij00m5kKF-w2XAmg-aCZKqRNtOeEC_4czmPOH0nIEZsEfDuC4mS9csbomKfcqcxwsXTB8yrdhmooYcmVL5okxwWKOfGRmDys5lPNVIbOGTgK513IBqFZLtlFzHrwa-ecJklSfRGVCMCLLHRKaPVLeFPstTNMDJ9Ocx8jmSRNl5OJY98OebpvKlyiNw7cWgus3YxxSRklI4KA2oJBhEYeycB7wLgXGZcbKiSsX9ZKZHDOZ0QEFutkB5KUhhYFrmjVmWBE2C75YxHIxkZkWkEJkHEzNkyk4QsZzdI7KCZnwZlhLRHRUWmHizo7XSEsLbIOasajNeU0vhWnR7ZmEAjWvrdbFaSULJoV5mxIdP5sLzpWXdeLYi5FI7vXBaXMcvIJI4Q8phJkZ0LSWIOry78AU2RjEPl92YSp_yZRqzyTuxooTwJhLWLFFLVhk82SiZU7JTMQgXE7iMwvNSAcVciCO_MczBzBi2IUKJ7wLwfXXX8jsMXQi_M7JsfIdxFnXDCwc59_wsmXqcPinPC7kZS-GwlB7iP-eqjfA4GyLqXvKyOkz_tg-qnPS_eRnZzxRaYkKL9twbXOkhPRIsjjBTYkO_afrvJEqITY6TFj1SbusbyKJXPeVIqsfOwYg6w0gr6W9ISyMVjpkJhZLOYJKrlFp1fHhZXNoEwGtyhGSJfI1kOsQuKAqPIXzUkXqGZ0-JFL4k9h8OXClslFyG-L-L0sNKbqsHVsRsLLsEFpfCXPelzKYmes_LToUivqHi7oSCyPzNXCeJdk9MaBIjEqAnvvtHzlFHlMXn0KGgGMcBbkhK7F3oiLqFeB5CnviDWCrCeDiLTowjAcyLkiHFqAjiRrzBjtVAuKDMGAiHGP-q6E7FJNJPOMqHODiiHKOoWKQueM-Okq-HwSNIBuiMCscDWL0OWlFsNOcEYmFF-B5joRQtwpAqZE7nyLSDEqmO1PeHhMPJsq5F-G1t2BJEqirNaiYmiMGGnhlFOPfr-DOLChGCrORNiLSByMlnOmnBJMGIQigdngSEqu8NBpxrxOVMUfsuiGOqcFqLKvNJcnkEDi6PSAXP2AiHxJqqXLaPIelvzthgUYjncITBiotHmDBNEsKnmJaCFDyLQXyHPlBl8saNKGfDBPhPCM6AuHwXvCPOQihLqLSJNEpj2uRGxKcZiJgrzohmli2iLMaM1iQXerVF8ANp9ByFIgsuBKLi3EcNuH2NCgjpJJdCtBsP9j7OcGfGyETNKIBirM1IJN2pwsSNUUfEzEsDRhjLtlaDHCdsHBJFepLozl5HvnOB_FxPiFlNKDuNiliLoVHmyiDDKJAeZgJMEtbHyMMW1MzkROjuBMdhCKEUKrQvDDqHCCSKDIbgkRWFiOyCaKVg-puB6tjuGsqFFmbGjOlhQjOP6KYsppypofkBaCyiWu9OYjqJWgYjSC4tckxJaEAXSmakPssZsV3nOHyL4TKOyfkCdJXIZkDnmv0brrThSI6DxjJIdFJLyssTvPkD3E2KdJsY6TkJ2C2L0HlKBPOJEviNElaJ7CHukW4fvOxl8DSHuljBHFUn0DvK-NKFeOVn2NSHBI_pSKSbGIuC4iNJzt9NsmxrQRqILJHPsmwbUt5vWIUr8phkPq6J4TqH5JZChI0fqM_qYnMLOhJJmhiNbNHKyOKLnOchcr8kmebnPv1ozmcDJpKgJuKM8aGp0ShvttnsEuxDSKQbTo0WjP5oPjUUWJOhGP-iwvqNmSsl-TkQ1KblQczBaP3hJBbJVJ0Y0fbmYvJszHONQoiAiCNMKfgteV5kJhJOwWMgIcGrBbcnTNsnhLeotvnn4fkW7GWbolSFCAPL2jyEBISK6dCjogrics3MNDNMUKUKgJgLgAQCQGQDUHULEPEIkDQCkOkJkEgCAAAHJoAcB4BeAABCaAMgXg2lulMgWAnQ-lWAogNA2lWAQgxlSlhAxlGlkgxlMgbADl_AxlAAwi5WZQZTwJZZ5ZUGgMZYQB5SAOZfwD5cFQZVIMZTgP5b5TgAANJRUYDGWSAJU0BaUGVGVpXmWmUgDpUWWaXmXWUFUGV2XFWVBOVZUGUyBBV5XuVlXeVlVyBlWBVlWhWtX2WVW4AxW5XmXxVlU4BJWdUpUCUUBFBFBAA===
[ksh05]: https://nepszamlalas2022.ksh.hu/adatbazis/#/table/WBS003/N4IgFgpghgJiBcBtEAVAogGQPoGUBaWAggCKEogC6ANCAM4CWMECyKAkgLJpYAKaASmwDyxEDXT8AqtgDiaIQFZKNWhADGAF3oB7AHYtqIAGb0ANhogAnWglABrerrjwQHKAAcxICLo2X6EDZIrJzcfIIiYvaOziA4EBpeAG5QpgCugSwgAEwADNnZlAC-1KwC0lhyilEgDk4IcQnJqRlByAASkgDMXQCMXp09hTSDPV65XQAs411KNBMAbDMA7DMAHDMAnOOTuTv985PDILmTXTvTh0uHcyeTq4cbh9vzCnuvBycKx7kK5_PLd4nZafXLLH7Lf7Ay7A25g64gXpg3ovRG5XprIHZcFTLxddEKW69BQLTao3q9bKY8YLU4w7I9BQPHLLTHkyYKSYw3JrUnMibfH5dBYkrzZBb3T69BZdSFeJF_KGUkkIim8mGMtao_KbTl4jGTJ6I7KbWVihS625dbKcrGUjlitZrPKOqZK03Y8abSak-VraWq2kYsUypHylELUHLb7c1mR8O01X3BYI05I7XW_HjbK9SYZpnMjHR8lrDlG7GluESo543Iy47S7Gp3nLVEmilE3VZ-ZrVlW4WneULE0w3rLBa8-VTHl42abI19H0L4UFHa5U3y1sMkMT-k27vA8ELjEb15xzcLZbMhm_QOm8l1y9ilFc8ZrfFE07g-UM180XO_EaPLrrcOZkqi-K0p2rLaqaf6Ii2QIYjmRoovOUI2mcxzZHm854lS240D0oYhl075ijq_LYr88qcn05qmvy75vGK0YgvhZz0v6Cjlps-SFn8eE0FShqqgoxKoXkNpvrK5ZnJsqpkXWeK7Ap4atvSFKGs-dbauOlLjDxopESiwbCf6B42nWUpkvcFHfFWUnPpSWIcg6RF1oRiKqaO3y5EC06siGgIQX0fHjJCp4nH0ykmdaRLiv62azD8mzjkh95Aqc2Lkia_nygpVLhvOoVgqBhL5GKhool6WGzhy_Ymsy1q6vybzWjMPqfDmeRtrqup-ki2G7PRwk5h1Y3RscfRMqOTpkUOpyga2sWIsSwoUeOVrokV_5FlC-LWthtK7XcOENv1GqUqd4onhRDVeuJUo5leb44fSkFwoJhYSriwkKWG_6RaO8LchOg7CV0pqgkcq0oja15rCS5XSnJsxZcOTLZuD-o9PS9zevK-S9qxZzlmRgJTpKP42qqt2odKxK1tKmnzWKXbdQUUW_BSnMSgiNp8Vl765uakIYcShI0yK7NIgLwrjvhVJWkNo45YjFoNpGaXykc3zZpSoJ_K2Xo5khwopjulvzGSUuvIVEWzIWPOgeuov_tiJsAtGjmlkTPTav6mzTfiLqHFMEFIl7Jwynq8xQ9bOS5gZrycqqV4y0RRzuTkuyvR5fxEj05H_lqZJvX8uuTIDiJ9PGJmAgl_nNcRP0KUmwejnxw4Re-e5khdaWjjiGGbGOEE4VqVeihQJRUGU2D4EQpDkFQ0T1C48SJDQKTpJkSAgAAcmgHB4F4ABCaAyF4V83zIWCdHfWCiDQV9YEIT-H4QT_n5IT8yGwf-_An4AGFgGv3vjwD-EDKhoCfoQcBIA378GgUg--Ugn44DgTAnAABpTBGAn6SHwTQS-99H6kLfi_EAZD34Xzfl_eh99f5MMqIAyh98ZCINoWA1hUDWFyFYQg1hKCRF_w4bgbBNC354NYTgQhEjiHFAoLPIoQA

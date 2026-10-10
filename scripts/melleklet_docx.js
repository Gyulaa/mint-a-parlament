// Futtatás: npm install docx@9.5.1 (egyszer), majd node scripts/melleklet_docx.js
// A Vjt. 1. és 2. mellékletének módosítása: szövegtervezet Word-dokumentumban a jogi csapatnak.
// Bemenet: data/interim/melleklet/melleklet_A.json, melleklet_B.json (python -m oevk.melleklet)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, PageBreak,
} = require("docx");

const GY = path.resolve(__dirname, "..");
const A = JSON.parse(fs.readFileSync(path.join(GY, "data/interim/melleklet/melleklet_A.json"), "utf8"));
const B = JSON.parse(fs.readFileSync(path.join(GY, "data/interim/melleklet/melleklet_B.json"), "utf8"));
const KI = path.join(GY, "data/interim/melleklet/OEVK_2026_melleklet_tervezet.docx");

const BETU = "Times New Roman";
const SZURKE = "666666";
const szaz = x => (x >= 0 ? "+" : "−") + Math.abs(x * 100).toFixed(1).replace(".", ",") + "%";
const ezres = n => n.toLocaleString("hu-HU").replace(/\u00a0/g, " ");
const MEGYE_CIM = { Budapest: "Budapest", Pest: "Pest megye", Somogy: "Somogy megye", Tolna: "Tolna megye" };
const SORREND = ["Budapest", "Pest", "Somogy", "Tolna"];

const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [runs], spacing: { after: 80, line: 276 }, ...o });
const t = (s, o = {}) => new TextRun({ text: s, font: BETU, size: 22, ...o });
const megj = s => p(t(s, { italics: true, color: SZURKE, size: 20 }), { spacing: { after: 60 } });

// a [változatlan], [TERVEZET] és [ellenőrizendő szakasz] jelölések kiemelve
function szovegFutasok(s) {
  const ki = [];
  let jel = null;
  if (s.endsWith(" [változatlan]")) { s = s.slice(0, -14); jel = "változatlan"; }
  if (s.endsWith(" [TERVEZET]")) { s = s.slice(0, -11); jel = "TERVEZET"; }
  s.split(/(\[ellenőrizendő szakasz(?: \d+)?\](?:nak)?)/).forEach(d => {
    if (!d) return;
    if (d.startsWith("[ellenőrizendő szakasz")) ki.push(t(d.replace(/nak$/, ""), { shading: { type: ShadingType.CLEAR, fill: "FFF176", color: "auto" }, bold: true }));
    else ki.push(t(d));
  });
  if (jel === "változatlan") ki.push(t("  [változatlan, a hatályos szöveg]", { italics: true, color: SZURKE, size: 20 }));
  if (jel === "TERVEZET") ki.push(t("  [TERVEZET – földrajzi ellenőrzés szükséges]", { bold: true, color: "B00020", size: 20 }));
  return ki;
}

function korzet(k) {
  const ki = [];
  ki.push(new Paragraph({ children: [t(`${k.sorszam}. számú országgyűlési egyéni választókerület`, { bold: true })],
    spacing: { before: 240, after: 60 }, keepNext: true }));
  const info = [k.regi_sorszam ? `hatályos: ${k.megye} ${k.regi_sorszam}. OEVK` : "új körzet", `választópolgár: ${ezres(k.valaszto)} (${szaz(k.elteres)})`];
  if (k.regi_sorszam && k.regi_sorszam !== k.sorszam) info.push(`új sorszám (a hatályos ${k.regi_sorszam}. helyett)`);
  ki.push(megj(info.join(" · ")));
  ki.push(p(t(`Rövidítése: ${k.rovidites}`), { keepNext: true }));
  ki.push(p(t(`Székhelye: ${k.szekhely}`), { keepNext: true }));
  ki.push(p(t("Területe:"), { keepNext: true }));
  k.tetelek.forEach((x, i) => ki.push(new Paragraph({
    children: [t(`${i + 1}. `), ...szovegFutasok(x)],
    indent: { left: 567, hanging: 567 }, spacing: { after: k.megye === "Budapest" ? 100 : 0, line: 264 },
  })));
  return ki;
}

function megszunt(k, ag) {
  const utodok = ag.korzetek.filter(x => x.megye === k.megye && !x.megszunik).map(x => x.sorszam + ".").join(", ");
  return [new Paragraph({ children: [t(`A hatályos ${k.oevk.slice(-2)}. számú (${k.szekhely} székhelyű) országgyűlési egyéni választókerület megszűnik; `
    + `területét a(z) ${utodok} számú választókerület veszi át.`, { italics: true })], spacing: { before: 200, after: 120 } })];
}

function agResz(ag, megyek) {
  const ki = [];
  megyek.forEach(m => {
    const ks = ag.korzetek.filter(k => k.megye === m);
    if (!ks.length) return;
    ki.push(new Paragraph({ text: MEGYE_CIM[m], heading: HeadingLevel.HEADING_3, spacing: { before: 360, after: 120 } }));
    ks.filter(k => k.megszunik).forEach(k => ki.push(...megszunt(k, ag)));
    ks.filter(k => !k.megszunik).forEach(k => ki.push(...korzet(k)));
  });
  return ki;
}

// 1. melléklet: táblázat
const W = [3000, 1800, 1800, 1800]; const TW = W.reduce((a, b) => a + b, 0);
const keret = { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB" };
const cella = (s, i, fej) => new TableCell({
  width: { size: W[i], type: WidthType.DXA }, borders: { top: keret, bottom: keret, left: keret, right: keret },
  shading: fej ? { type: ShadingType.CLEAR, fill: "EEEEEE", color: "auto" } : undefined,
  margins: { top: 60, bottom: 60, left: 100, right: 100 },
  children: [new Paragraph({ alignment: i ? AlignmentType.RIGHT : AlignmentType.LEFT, children: [t(s, { bold: !!fej, size: 20 })] })],
});
const m1 = {}; A.melleklet1.forEach(x => { m1[x.megye] = { ma: x.ma, A: x.javaslat }; });
B.melleklet1.forEach(x => { m1[x.megye] = { ...(m1[x.megye] || { ma: x.ma }), B: x.javaslat }; });
const tabla1 = new Table({
  width: { size: TW, type: WidthType.DXA }, columnWidths: W,
  rows: [new TableRow({ tableHeader: true, children: ["Megye", "Hatályos", "A ág", "B ág"].map((s, i) => cella(s, i, true)) }),
    ...SORREND.map(m => { const x = m1[m]; return new TableRow({ children: [m, x.ma, x.A ?? x.ma, x.B ?? x.ma].map((s, i) => cella(String(s), i)) }); }),
    new TableRow({ children: ["Összesen", 106, 106, 106].map((s, i) => cella(String(s), i, true)) })],
});

// címlisták (függelék)
function cimlistak(ag) {
  const ki = [];
  ag.korzetek.filter(k => k.cimlistak && k.cimlistak.length).forEach(k => k.cimlistak.forEach(c => {
    ki.push(new Paragraph({ text: `${k.rovidites} – ${c.kerulet} választókerülethez tartozó része`, heading: HeadingLevel.HEADING_3, spacing: { before: 300, after: 80 } }));
    ki.push(megj(`${c.szavazokorok.length} szavazókör (${c.szavazokorok.join(", ")}), ${ezres(c.valaszto)} választópolgár; a közterületek és házszámok az NVI szavazóköri címjegyzéke szerint.`));
    c.cimek.forEach(x => { const i = x.indexOf(": "); ki.push(new Paragraph({ children: [t(x.slice(0, i), { bold: true, size: 19 }), t(": " + x.slice(i + 2), { size: 19 })], spacing: { after: 0, line: 240 } })); });
  }));
  return ki;
}

const bevezeto = [
  new Paragraph({ children: [t("OEVK-felülvizsgálat 2026", { bold: true, size: 36 })], spacing: { after: 80 } }),
  new Paragraph({ children: [t("A 2011. évi CCIII. törvény (Vjt.) 1. és 2. számú mellékletének módosítása – szövegtervezet", { size: 26 })], spacing: { after: 120 } }),
  p(t("Miklós Gyula · Mint a parlament · 2026. október", { color: SZURKE, size: 20 }), { spacing: { after: 240 } }),
  new Paragraph({ text: "A dokumentumról", heading: HeadingLevel.HEADING_2 }),
  p(t("A tervezet a hatályos 2. melléklet szerkezetét követi: körzetenként sorszám, rövidítés, székhely és terület. Csak a változó körzetek szerepelnek benne; a többi körzet szövege változatlan. A vidéki körzetek területe településlista (magyar ábécérendben). Budapesten a teljes kerületek nevükkel szerepelnek, a megosztott kerületek választókerülethez tartozó részét határvonal írja le.")),
  p(t("A javaslat alapelve: csak oda nyúltam, ahol a törvényi korlát sérül (Vjt. 4. § (6): 20% fölötti eltérés). A 2026-os névjegyzékkel ez Tolna mindhárom és Somogy 02. számú (barcsi) körzete. Tolna három körzettel nem javítható, ezért 2 körzetet kap; a felszabaduló hely Budapesté (17. körzet). Somogyra két változat készült:")),
  p([t("A ág (fő javaslat): ", { bold: true }), t("Somogyban is legfeljebb ±15%; Somogy 3 körzetet kap (a marcali körzet megszűnik), a hely Pest megyéé (15. körzet).")], { indent: { left: 360 } }),
  p([t("B ág (tartalék): ", { bold: true }), t("Somogyban a ±20% elég; Somogy 4 körzet marad, csak a 02. (barcsi) és a 03. (marcali) számú körzet határa változik, 600 választót érintve. Pest megye változatlan.")], { indent: { left: 360 } }),
  p(t("Jelölések:", { bold: true }), { spacing: { before: 120, after: 40 } }),
  p([t("[változatlan, a hatályos szöveg]", { italics: true, color: SZURKE, size: 20 }), t(" – a kerületrész nem változik, a hatályos melléklet szövege szó szerint átvéve.")], { indent: { left: 360 } }),
  p([t("[TERVEZET – földrajzi ellenőrzés szükséges]", { bold: true, color: "B00020", size: 20 }), t(" – a határvonal leírását a program állította össze a szavazókörök térképéből és az OpenStreetMap utcatengelyeiből; véglegesítés előtt földrajzi ellenőrzés kell.")], { indent: { left: 360 } }),
  p([t("[ellenőrizendő szakasz]", { shading: { type: ShadingType.CLEAR, fill: "FFF176", color: "auto" }, bold: true }), t(" – itt a határ nem utca mentén fut, vagy a program nem tudta azonosítani az utcát.")], { indent: { left: 360 } }),
  p(t("A budapesti kerületrészek pontos tartalmát a Függelék címlistája adja meg (közterületek és házszámok a Nemzeti Választási Iroda szavazóköri címjegyzéke szerint). A határvonal-leírás véglegesítésekor ez a mérvadó.")),
  p(t("Megjegyzés: az eredmény matematikai számításon alapul (a legkevesebb áthelyezett választó, összefüggő és tömör körzetek, a közigazgatási határok követése). Lehetnek olyan helyi szempontok – közlekedés, összetartozó közösségek, földrajzi adottságok –, amelyeket nem tudtam figyelembe venni.", { italics: true })),
  p(t("Nyitott kérdés a sorszámozásról: a tervezet a megszűnő körzet utáni sorszámokat folyamatosan újraszámozza (pl. Tolna 03 → 02), az új körzet a megye utolsó sorszámát kapja. Ha a hatályos sorszámokat érdemes megtartani, ez egyszerűen módosítható.")),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: "1. Az 1. számú melléklet módosítása (körzetek száma)", heading: HeadingLevel.HEADING_2 }),
  p(t("A többi megye körzetszáma változatlan. Az összesen 106 körzet mindkét ágban megmarad.")),
  tabla1,
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: "2. A 2. számú melléklet módosítása – A ág (fő javaslat)", heading: HeadingLevel.HEADING_2 }),
  megj("A hatályos melléklet érintett részeinek helyébe lépő szöveg."),
  ...agResz(A, SORREND),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: "3. A 2. számú melléklet módosítása – B ág (tartalék)", heading: HeadingLevel.HEADING_2 }),
  p(t("Budapest és Tolna megye szövege azonos az A ággal; Pest megye változatlan. Somogy megye szövege a B ágban:")),
  ...agResz(B, ["Somogy"]),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ text: "Függelék: a budapesti kerületrészek címlistája", heading: HeadingLevel.HEADING_2 }),
  p(t("Közterületenként: „teljes” = a közterület minden házszáma; egyébként a választókerülethez tartozó házszámok (páros, páratlan oldal vagy folyamatos tartomány). „végig” = a tartomány a közterület végéig tart.")),
  ...cimlistak(A),
];

const doc = new Document({
  creator: "Miklós Gyula", title: "OEVK-felülvizsgálat 2026 – mellékletmódosítás (tervezet)",
  styles: {
    default: { document: { run: { font: BETU, size: 22 } } },
    paragraphStyles: [
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: BETU, size: 28, bold: true }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: BETU, size: 24, bold: true }, paragraph: { spacing: { before: 240, after: 100 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1247, right: 1247 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [t("OEVK 2026 – mellékletmódosítás, tervezet · ", { size: 18, color: SZURKE }), new TextRun({ children: [PageNumber.CURRENT], font: BETU, size: 18, color: SZURKE })] })] }) },
    children: bevezeto,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(KI, b); console.log(KI, (b.length / 1024).toFixed(0) + " kB"); });

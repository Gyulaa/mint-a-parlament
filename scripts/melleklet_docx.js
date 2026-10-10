// Futtatás: npm install docx@9.5.1 (egyszer), majd node scripts/melleklet_docx.js
// A Vjt. 1. és 2. melléklete a javaslat szerint módosítva, egységes szerkezetben (Word), a jogi csapatnak.
// Csak a törvényszöveg: a jogászok bemásolják a saját dokumentumukba, ezért nincs benne bevezető, jelölés, kiemelés.
// Bemenet: data/interim/melleklet/melleklet_A.json „egyseges” része (python -m oevk.melleklet)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, Footer, PageNumber, PageBreak,
} = require("docx");

const GY = path.resolve(__dirname, "..");
const E = JSON.parse(fs.readFileSync(path.join(GY, "data/interim/melleklet/melleklet_A.json"), "utf8")).egyseges;
const KI = process.argv[2] ? path.resolve(process.argv[2]) : path.join(GY, "data/interim/melleklet/OEVK_2026_mellekletek.docx");  // ha a Word nyitva tartja, más néven

const BETU = "Times New Roman";
const t = (s, o = {}) => new TextRun({ text: s, font: BETU, size: 22, ...o });
const p = (runs, o = {}) => new Paragraph({ children: Array.isArray(runs) ? runs : [runs], spacing: { after: 60, line: 264 }, ...o });
const kozep = (s, o = {}) => p(t(s, { bold: true, ...o }), { alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 } });

// ---- 1. melléklet ----
const W = [900, 5000, 2700]; const TW = W.reduce((a, b) => a + b, 0);
const keret = { style: BorderStyle.SINGLE, size: 4, color: "999999" };
const cella = (s, i, o = {}) => new TableCell({
  width: { size: W[i], type: WidthType.DXA }, borders: { top: keret, bottom: keret, left: keret, right: keret },
  shading: o.fej ? { type: ShadingType.CLEAR, fill: "EEEEEE", color: "auto" } : undefined,
  margins: { top: 40, bottom: 40, left: 100, right: 100 },
  children: [new Paragraph({ alignment: i === 2 ? AlignmentType.CENTER : AlignmentType.LEFT, children: [t(s, { bold: !!o.fej, size: 21 })] })],
});
const melleklet1 = [
  kozep("1. számú melléklet a 2011. évi CCIII. törvényhez"),
  kozep("Az egyéni választókerületek száma a megyékben és a fővárosban", { bold: false }),
  new Table({
    width: { size: TW, type: WidthType.DXA }, columnWidths: W,
    rows: [
      new TableRow({ tableHeader: true, children: [cella("", 0, { fej: true }), cella("", 1, { fej: true }), cella("Egyéni választókerületek száma", 2, { fej: true })] }),
      ...E.melleklet1.map((x, i) => new TableRow({ children: [cella(`${i + 1}.`, 0), cella(x.megye, 1), cella(String(x.javaslat), 2)] })),
      new TableRow({ children: [cella("", 0), cella("Összesen", 1, { fej: true }), cella(String(E.melleklet1.reduce((s, x) => s + x.javaslat, 0)), 2, { fej: true })] }),
    ],
  }),
];

// ---- 2. melléklet ----
function korzet(k) {
  const fej = [t(`${k.sorszam}. számú országgyűlési egyéni választókerület`, { bold: true })];
  const ki = [
    new Paragraph({ children: fej, spacing: { before: 200, after: 40 }, keepNext: true }),
    p(t(`Rövidítése: ${k.rovidites}`), { keepNext: true, spacing: { after: 0 } }),
    p(t(`Székhelye: ${k.szekhely}`), { keepNext: true, spacing: { after: 0 } }),
    p(t("Területe:"), { keepNext: true, spacing: { after: 0 } }),
  ];
  k.tetelek.forEach((x, i) => ki.push(new Paragraph({
    children: [t(`${i + 1}. ${x}`)], indent: { left: 567, hanging: 567 },
    spacing: { after: x.length > 80 ? 60 : 0, line: 252 }, alignment: x.length > 80 ? AlignmentType.JUSTIFIED : AlignmentType.LEFT,
  })));
  return ki;
}
const melleklet2 = [
  new Paragraph({ children: [new PageBreak()] }),
  kozep("2. számú melléklet a 2011. évi CCIII. törvényhez"),
  kozep("Az egyéni választókerületek sorszáma, székhelye és területi beosztása", { bold: false }),
];
E.melleklet2.forEach(m => {
  melleklet2.push(new Paragraph({ children: [t(m.megye, { bold: true, size: 24 })], alignment: AlignmentType.CENTER, spacing: { before: 360, after: 80 }, keepNext: true }));
  m.korzetek.forEach(k => melleklet2.push(...korzet(k)));
});

const doc = new Document({
  creator: "Miklós Gyula", title: "A Vjt. 1. és 2. melléklete a javaslat szerint",
  styles: { default: { document: { run: { font: BETU, size: 22 } } } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1247, right: 1247 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: [PageNumber.CURRENT], font: BETU, size: 18 })] })] }) },
    children: [...melleklet1, ...melleklet2],
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(KI, b); console.log(KI, (b.length / 1024).toFixed(0) + " kB"); });

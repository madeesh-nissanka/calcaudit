import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from calcaudit.ingest import load_document, md_tables
from calcaudit.rules import load_cards, run_all


def tiny_pdf(lines):
    """Hand-built one-page PDF with Helvetica text lines (no third-party library)."""
    content = "BT /F1 12 Tf 50 750 Td 14 TL\n" + "\n".join(
        f"({l.replace('(', chr(92)+'(').replace(')', chr(92)+')')}) Tj T*" for l in lines) + "\nET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n"
    return out.encode("latin-1")


class PdfTest(unittest.TestCase):
    def test_pdf_equations_low_confidence(self):
        try:
            import pypdf  # noqa: F401
        except ImportError:
            import shutil
            if not shutil.which("pdftotext"):
                self.skipTest("no PDF text extractor installed")
        p = os.path.join(tempfile.mkdtemp(), "t.pdf")
        open(p, "wb").write(tiny_pdf(["Settlement note", "v = k i (1)", "Some prose here."]))
        doc = load_document(p)
        self.assertTrue(doc.equations)
        self.assertTrue(all(e.confidence == "low" for e in doc.equations))
        doc.glossary = {"v": "m/s", "k": "kPa", "i": "1"}
        rep = run_all(doc, load_cards())
        bad = [f for f in rep.findings if f.outcome.value == "violated" and f.rule == "U01"]
        self.assertTrue(bad)
        self.assertNotEqual(bad[0].severity.value, "serious")
        self.assertIn("PDF", bad[0].evidence)


class TableTest(unittest.TestCase):
    def test_markdown_table_headers(self):
        t = md_tables("| Settlement (kPa) | Time (s) |\n|---|---|\n| 1 | 2 |\n")
        self.assertEqual(t[0]["columns"], ["Settlement (kPa)", "Time (s)"])

    def test_docx_table_headers(self):
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>'
               '<w:tr><w:tc><w:p><w:r><w:t>Stress (m)</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Time (s)</w:t></w:r></w:p></w:tc></w:tr>'
               '</w:tbl></w:body></w:document>')
        p = os.path.join(tempfile.mkdtemp(), "t.docx")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", xml)
        rep = run_all(load_document(p), load_cards())
        u03 = [f for f in rep.findings if f.rule == "U03" and f.outcome.value == "violated"]
        self.assertEqual(len(u03), 1)


if __name__ == "__main__":
    unittest.main()

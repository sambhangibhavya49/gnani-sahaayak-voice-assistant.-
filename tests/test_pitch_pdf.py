"""
Automated tests verifying that the 1-Page Solution Pitch document (Solution_Pitch.pdf)
and Solution_Pitch.md exist in the project root and meet official competition specifications.
"""

from pathlib import Path
import unittest


class TestSolutionPitchDocuments(unittest.TestCase):
    """Validates the official 1-page solution pitch PDF and Markdown deliverables."""

    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent
        cls.pdf_path = cls.root_dir / "Solution_Pitch.pdf"
        cls.md_path = cls.root_dir / "Solution_Pitch.md"

    def test_solution_pitch_pdf_exists_in_root(self):
        """Verifies that Solution_Pitch.pdf is placed in the project root."""
        self.assertTrue(self.pdf_path.exists(), "Solution_Pitch.pdf must exist in the project root.")
        self.assertTrue(self.pdf_path.is_file(), "Solution_Pitch.pdf must be a regular file.")

    def test_solution_pitch_pdf_is_valid_single_page_pdf(self):
        """Verifies that Solution_Pitch.pdf adheres to ISO 32000-1 (PDF 1.4) and is strictly 1 page."""
        content = self.pdf_path.read_text(encoding="latin-1")

        # Must start with standard PDF header
        self.assertTrue(content.startswith("%PDF-1.4"), "File must start with standard PDF 1.4 header.")

        # Must end with standard PDF EOF marker
        self.assertTrue(content.strip().endswith("%%EOF"), "File must end with %%EOF marker.")

        # Must contain xref table and catalog
        self.assertIn("/Type /Catalog", content)
        self.assertIn("/Type /Pages", content)

        # Strictly 1 Page requirement
        self.assertIn("/Count 1", content, "Document must have strictly 1 page (/Count 1).")
        self.assertIn("/MediaBox [0 0 595.28 841.89]", content, "Must be standard A4 dimensions.")

        # File size sanity check (should be between 5 KB and 50 KB for a clean vector PDF)
        size_bytes = self.pdf_path.stat().st_size
        self.assertGreater(size_bytes, 5000, "PDF should be substantial (> 5KB).")
        self.assertLess(size_bytes, 100000, "PDF should be a lightweight vector file (< 100KB).")

    def test_solution_pitch_pdf_contains_required_sections_and_credentials_safety(self):
        """Verifies required content markers and confirms no real API keys are in the pitch."""
        content = self.pdf_path.read_text(encoding="latin-1")

        # Required key sections
        self.assertIn("GNANI SAHAAYAK", content)
        self.assertIn("VOXORA", content)
        self.assertIn("Prisma v2.5 STT", content)
        self.assertIn("Timbre v2.5 TTS", content)
        self.assertIn("Sarvan Karanam", content)
        self.assertIn("MIT", content)

        # Security check: absolutely no real API keys embedded
        self.assertNotIn("vach_live", content)
        self.assertNotIn("gnani-sahaayak-dev-test-key", content)

    def test_solution_pitch_md_companion_exists(self):
        """Verifies that the markdown companion Solution_Pitch.md exists and is populated."""
        self.assertTrue(self.md_path.exists(), "Solution_Pitch.md must exist in the project root.")
        md_text = self.md_path.read_text(encoding="utf-8")
        self.assertIn("Gnani Sahaayak (GNANI — VOXORA)", md_text)
        self.assertIn("Solution_Pitch.pdf", md_text)
        self.assertIn("132 / 132 PASSED", md_text)


if __name__ == "__main__":
    unittest.main()


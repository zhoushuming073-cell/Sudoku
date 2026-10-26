import shutil
import unittest
from pathlib import Path

from PIL import Image

from sudoku_ocr import recognize_image, recognize_pil_image
from sudoku_solver import solve_board, verify_solution


class SudokuOCRTests(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("tesseract") or Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists(),
        "Tesseract not installed",
    )
    def test_bundled_example_recognition(self):
        example = Path(__file__).resolve().parents[1] / "example_sudoku.png"
        if not example.exists():
            self.skipTest("Example not bundled")
        observed = recognize_image(str(example))
        expected = [
            "000000100", "081093045", "400050032",
            "900504078", "058300009", "000820000",
            "500270084", "604138207", "802900600",
        ]
        self.assertEqual("".join(map(str, observed.board)), "".join(expected))
        self.assertEqual(observed.corners.shape, (4, 2))
        result = solve_board(observed.board)
        self.assertTrue(verify_solution(observed.board, result.solution))

    @unittest.skipUnless(
        shutil.which("tesseract") or Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe").exists(),
        "Tesseract not installed",
    )
    def test_clipboard_image_recognition(self):
        example = Path(__file__).resolve().parents[1] / "example_sudoku.png"
        with Image.open(example) as screenshot:
            observed = recognize_pil_image(screenshot)
        self.assertEqual(sum(bool(value) for value in observed.board), 38)
        self.assertTrue(verify_solution(observed.board, solve_board(observed.board).solution))


if __name__ == "__main__":
    unittest.main()


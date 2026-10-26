import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from sudoku_ocr import _read_digit, recognize_image, recognize_pil_image
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

    def test_small_printed_digits_keep_one_seven_five_six_distinct(self):
        example = Path(__file__).resolve().parents[1] / "example_sudoku.png"
        with Image.open(example) as image:
            observed = recognize_pil_image(image.resize((420, 420)))
        expected = (
            "000000100081093045400050032900504078058300009000820000"
            "500270084604138207802900600"
        )
        self.assertEqual("".join(map(str, observed.board)), expected)
        self.assertFalse(observed.uncertain)

    def test_reader_disagreement_requires_review(self):
        patch_image = np.full((144, 144), 255, dtype=np.uint8)
        with (patch("sudoku_ocr._rapid_digit", return_value=(7, .999)),
              patch("sudoku_ocr._match_printed_digit", return_value=(1, .70)),
              patch("sudoku_ocr.pytesseract.image_to_data",
                    return_value={"text": ["1"], "conf": [95.0]})):
            digit, confidence = _read_digit(patch_image)
        self.assertEqual(digit, 7)
        self.assertLess(confidence, 55)


if __name__ == "__main__":
    unittest.main()


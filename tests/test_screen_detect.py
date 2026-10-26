import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from sudoku_screen_detect import detect_grid


PROJECT = Path(__file__).resolve().parents[1]


class ScreenDetectionTests(unittest.TestCase):
    def test_finds_board_in_full_screen_at_different_sizes(self):
        original = Image.open(PROJECT / "example_sudoku.png").convert("RGB")
        for side, left, top in ((850, 170, 220), (590, 800, 150),
                                (400, 1350, 650)):
            with self.subTest(side=side):
                screen = Image.new("RGB", (2560, 1600), "#e8edf3")
                screen.paste(original.resize((side, side)), (left, top))
                detected = detect_grid(screen)
                self.assertIsNotNone(detected)
                self.assertGreater(detected.score, .80)
                for actual, expected in zip(detected.box,
                                            (left, top, left + side, top + side)):
                    self.assertAlmostEqual(actual, expected, delta=20)

    def test_rejects_plain_square_and_three_by_three_grid(self):
        screen = Image.new("RGB", (1600, 1000), "white")
        draw = ImageDraw.Draw(screen)
        for index in range(4):
            pos = 250 + index * 150
            draw.line((250, pos, 700, pos), fill="black", width=3)
            draw.line((pos, 250, pos, 700), fill="black", width=3)
        self.assertIsNone(detect_grid(screen))

    def test_two_equally_plausible_boards_need_manual_choice(self):
        board = Image.open(PROJECT / "example_sudoku.png").convert("RGB")
        screen = Image.new("RGB", (2560, 1600), "#e8edf3")
        tile = board.resize((600, 600))
        screen.paste(tile, (100, 400))
        screen.paste(tile, (1550, 400))
        self.assertIsNone(detect_grid(screen))


if __name__ == "__main__":
    unittest.main()


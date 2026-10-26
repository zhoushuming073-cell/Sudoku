import unittest

import numpy as np

from screen_automation import ScreenRegion, make_fill_plan, selection_to_region
from sudoku_solver import parse_board, solve_board


class ScreenAutomationTests(unittest.TestCase):
    def test_selection_uses_physical_screenshot_pixels(self):
        region = selection_to_region((500, 450), (100, 50),
                                     (2560, 1600), (1280, 800), 123)
        self.assertEqual(region, ScreenRegion(200, 100, 1000, 900, 123))

    def test_fill_plan_skips_clues_and_uses_detected_grid(self):
        givens = parse_board([
            "004090067", "000030000", "619870005",
            "307064800", "090000030", "001520706",
            "100059673", "000080000", "570040900",
        ])
        solution = solve_board(givens).solution
        region = ScreenRegion(100, 200, 1000, 1100, 123)
        corners = np.array([[10, 20], [890, 20], [890, 890], [10, 890]],
                           dtype=np.float32)
        plan = make_fill_plan(givens, solution, region, corners)
        self.assertEqual(len(plan), givens.count(0))
        self.assertEqual({action.index for action in plan},
                         {index for index, value in enumerate(givens) if value == 0})
        first = plan[0]
        self.assertEqual(first.index, 0)
        self.assertEqual(first.digit, solution[0])
        self.assertAlmostEqual(first.x, 159, delta=1)
        self.assertAlmostEqual(first.y, 268, delta=1)

    def test_conflicting_solution_never_creates_actions(self):
        givens = [0] * 81
        solution = [1] * 81
        region = ScreenRegion(0, 0, 900, 900, 123)
        corners = np.array([[0, 0], [899, 0], [899, 899], [0, 899]],
                           dtype=np.float32)
        with self.assertRaises(ValueError):
            make_fill_plan(givens, solution, region, corners)


if __name__ == "__main__":
    unittest.main()


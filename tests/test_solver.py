import unittest

from sudoku_solver import parse_board, solve_board, validate_board, verify_solution


class SudokuSolverTests(unittest.TestCase):
    def test_textbook_puzzle_without_guesses(self):
        puzzle = parse_board([
            "004090067", "000030000", "619870005",
            "307064800", "090000030", "001520706",
            "100059673", "000080000", "570040900",
        ])
        result = solve_board(puzzle)
        self.assertTrue(verify_solution(puzzle, result.solution))
        self.assertEqual(result.guesses, 0)
        self.assertEqual(result.solution[:9], [8, 3, 4, 1, 9, 5, 2, 6, 7])

    def test_invalid_givens(self):
        puzzle = [0] * 81
        puzzle[0] = puzzle[1] = 7
        with self.assertRaises(ValueError):
            validate_board(puzzle)

    def test_search_finds_hard_puzzle(self):
        puzzle = parse_board([
            "800000000", "003600000", "070090200",
            "050007000", "000045700", "000100030",
            "001000068", "008500010", "090000400",
        ])
        result = solve_board(puzzle)
        self.assertTrue(verify_solution(puzzle, result.solution))
        self.assertGreater(result.guesses, 0)
        self.assertTrue(any(step.kind == "guess" for step in result.steps))


if __name__ == "__main__":
    unittest.main()

"""A traceable, complete backtracking solver for standard 9x9 Sudoku."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DIGITS = frozenset(range(1, 10))
ROWS = [tuple(r * 9 + c for c in range(9)) for r in range(9)]
COLS = [tuple(r * 9 + c for r in range(9)) for c in range(9)]
BOXES = [
    tuple((br * 3 + dr) * 9 + bc * 3 + dc for dr in range(3) for dc in range(3))
    for br in range(3) for bc in range(3)
]
UNITS = ROWS + COLS + BOXES
CELL_UNITS = [tuple(unit for unit in UNITS if i in unit) for i in range(81)]
PEERS = [frozenset(j for unit in CELL_UNITS[i] for j in unit if j != i) for i in range(81)]


@dataclass(frozen=True)
class Step:
    board: tuple[int, ...]
    kind: str
    message: str
    cell: Optional[int] = None
    digit: Optional[int] = None


@dataclass
class SolveResult:
    solution: list[int]
    steps: list[Step]
    nodes: int
    guesses: int
    backtracks: int


def parse_board(rows: list[str]) -> list[int]:
    if len(rows) != 9 or any(len(row) != 9 for row in rows):
        raise ValueError("数独必须是9行、每行9个字符。")
    values = []
    for row in rows:
        for char in row:
            if char in ".0":
                values.append(0)
            elif char in "123456789":
                values.append(int(char))
            else:
                raise ValueError(f"数独中存在非法字符：{char!r}")
    return values


def validate_board(board: list[int]) -> None:
    if len(board) != 81 or any(type(v) is not int or not 0 <= v <= 9 for v in board):
        raise ValueError("请输入81个0到9之间的整数（0表示空格）。")
    for index, unit in enumerate(UNITS):
        filled = [board[i] for i in unit if board[i]]
        if len(filled) != len(set(filled)):
            group = (f"第{index+1}行" if index < 9 else
                     f"第{index-8}列" if index < 18 else f"第{index-17}宫")
            raise ValueError(f"已知数字冲突：{group}中存在重复数字。请修正图片识别结果。")


def candidates(board: list[int], index: int) -> set[int]:
    if board[index]:
        return set()
    used = {board[peer] for peer in PEERS[index]}
    return set(DIGITS - used)


def _single(board: list[int]) -> tuple[int, int, str] | None:
    """Naked and hidden singles; raises on a contradiction."""
    available = {}
    for i, value in enumerate(board):
        if not value:
            choices = candidates(board, i)
            if not choices:
                raise ValueError(f"第{i//9+1}行第{i%9+1}列没有合法候选数")
            if len(choices) == 1:
                return i, next(iter(choices)), "唯一候选"
            available[i] = choices

    for unit_idx, unit in enumerate(UNITS):
        for digit in range(1, 10):
            if digit in (board[i] for i in unit):
                continue
            places = [i for i in unit if i in available and digit in available[i]]
            if not places:
                raise ValueError("某一行、列或宫已无法容纳必需的数字")
            if len(places) == 1:
                label = "行内唯一" if unit_idx < 9 else "列内唯一" if unit_idx < 18 else "宫内唯一"
                return places[0], digit, label
    return None


def solve_board(initial: list[int], max_steps: int = 60000) -> SolveResult:
    """Find a solution using propagation + MRV DFS, recording every visible change.

    A cap protects the GUI from extremely under-constrained pathological inputs.
    A hit cap produces an explicit error; it is never mislabeled as 'no solution'.
    """
    validate_board(initial)
    steps = [Step(tuple(initial), "initial", "已载入题目，准备约束传播")]
    nodes = guesses = backtracks = 0

    def record(board: list[int], kind: str, message: str, cell: int | None = None,
               digit: int | None = None) -> None:
        if len(steps) >= max_steps:
            raise RuntimeError("搜索步骤超过安全上限。可以增加max_steps后再试。")
        steps.append(Step(tuple(board), kind, message, cell, digit))

    def dfs(board: list[int]) -> list[int] | None:
        nonlocal nodes, guesses, backtracks
        nodes += 1
        current = board.copy()
        try:
            while True:
                forced = _single(current)
                if forced is None:
                    break
                cell, digit, reason = forced
                current[cell] = digit
                record(current, "deduction", f"{reason}：第{cell//9+1}行第{cell%9+1}列 = {digit}", cell, digit)
        except ValueError:
            record(current, "conflict", "约束发生冲突，当前分支不可行")
            return None

        if all(current):
            record(current, "solved", "所有格子均满足行、列、宫约束。求解完成！")
            return current

        unfilled = [i for i in range(81) if not current[i]]
        # MRV; tie-break by the number of still-unfilled peers (degree heuristic).
        cell = min(unfilled, key=lambda i: (len(candidates(current, i)),
                                             -sum(not current[j] for j in PEERS[i]), i))
        for digit in sorted(candidates(current, cell)):
            branch = current.copy()
            branch[cell] = digit
            guesses += 1
            record(branch, "guess", f"MRV试探：第{cell//9+1}行第{cell%9+1}列 = {digit}", cell, digit)
            result = dfs(branch)
            if result is not None:
                return result
            backtracks += 1
            record(current, "backtrack", f"撤销试探 {digit}，恢复到上一分支", cell, digit)
        return None

    solution = dfs(initial)
    if solution is None:
        raise ValueError("该数独没有符合全部规则的解。请检查已知数字。")
    return SolveResult(solution, steps, nodes, guesses, backtracks)


def verify_solution(original: list[int], solution: list[int]) -> bool:
    return (len(original) == len(solution) == 81
            and all(s == o for s, o in zip(solution, original) if o)
            and all({solution[i] for i in unit} == DIGITS for unit in UNITS))

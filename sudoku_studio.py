"""Sudoku Studio: image OCR, editable puzzle, and animated CSP search.

Run with ``python sudoku_studio.py`` after installing requirements and Tesseract.
"""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
import ctypes
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

from sudoku_ocr import OCRResult, recognize_image, recognize_pil_image
from sudoku_solver import SolveResult, Step, solve_board, validate_board, verify_solution

BASE = Path(__file__).resolve().parent
BG = "#f3f6fb"
CARD = "#ffffff"
INK = "#26384f"
MUTED = "#64748b"
BLUE = "#2479b7"
TEAL = "#148c80"
ORANGE = "#c07720"
RED = "#c74848"


def _font_path() -> str | None:
    paths = [
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    return next((path for path in paths if Path(path).exists()), None)


def export_board(path: str, board: list[int], givens: list[int]) -> None:
    """Export the solved grid as a high-resolution PNG."""
    image = Image.new("RGB", (930, 930), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(_font_path(), 65) if _font_path() else ImageFont.load_default()
    outer = 15
    cell = 100
    for r in range(9):
        for c in range(9):
            value = board[r*9+c]
            left, top = outer+c*cell, outer+r*cell
            if givens[r*9+c]:
                draw.rectangle([left, top, left+cell, top+cell], fill="#eef3fa")
            if value:
                color = INK if givens[r*9+c] else BLUE
                text = str(value)
                box = draw.textbbox((0, 0), text, font=font)
                tw, th = box[2]-box[0], box[3]-box[1]
                draw.text((left+(cell-tw)/2, top+(cell-th)/2-box[1]), text, fill=color, font=font)
    for i in range(10):
        width = 5 if i % 3 == 0 else 2
        x = outer+i*cell
        draw.line([(x, outer), (x, outer+900)], fill=INK if width == 5 else "#cbd5e1", width=width)
        draw.line([(outer, x), (outer+900, x)], fill=INK if width == 5 else "#cbd5e1", width=width)
    image.save(path)


class SudokuStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Sudoku Studio · 图片识别与动态求解")
        work_width, work_height = self._working_size()
        self.window_width = min(1100, max(900, work_width - 40))
        self.window_height = min(710, max(620, work_height - 36))
        self.geometry(f"{self.window_width}x{self.window_height}+{max(0, (work_width-self.window_width)//2)}+0")
        self.minsize(min(900, self.window_width), min(620, self.window_height))
        self.board_pad = 10
        self.cell = min(55, max(42, (self.window_height - 210) // 9))
        self.board_size = self.cell * 9 + self.board_pad * 2
        self.preview_height = min(195, max(150, self.window_height - 520))
        self.configure(bg=BG)

        self.board = [0]*81
        self.givens = self.board.copy()
        self.steps: list[Step] = []
        self.result: SolveResult | None = None
        self.index = 0
        self.selected: int | None = None
        self.playing = False
        self.timer: str | None = None
        self.busy = False
        self.auto_play_on_solve = False
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.original_image: ImageTk.PhotoImage | None = None

        self._style()
        self._build()
        self.after(100, self._poll_events)

    def _working_size(self) -> tuple[int, int]:
        width, height = self.winfo_screenwidth(), self.winfo_screenheight()
        if sys.platform == "win32":
            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            area = RECT()
            if ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(area), 0):
                width = min(width, area.right - area.left)
                height = min(height, area.bottom - area.top)
        return width, height

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TButton", font=("Microsoft YaHei", 10), padding=(12, 9),
                        background="#e6edf5", foreground=INK, borderwidth=0)
        style.map("TButton", background=[("active", "#d4e4f4")])
        style.configure("Accent.TButton", background=BLUE, foreground="white", padding=(12, 10))
        style.map("Accent.TButton", background=[("active", "#175d91")])
        style.configure("TLabel", background=BG, foreground=INK, font=("Microsoft YaHei", 10))

    def _build(self) -> None:
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=20, pady=(12, 8))
        tk.Label(head, text="SUDOKU  STUDIO", bg=BG, fg=INK,
                 font=("Arial", 19, "bold")).pack(side="left")
        tk.Label(head, text="图片识别  ·  可编辑  ·  推理动画  ·  回溯可视化",
                 bg=BG, fg=MUTED, font=("Microsoft YaHei", 10)).pack(side="left", padx=22, pady=8)

        main = tk.Frame(self, bg=BG)
        main.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        left = tk.Frame(main, bg=CARD, highlightbackground="#e1e9f1", highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.configure(width=270)
        left.pack_propagate(False)

        tk.Label(left, text="01 / 图片输入", bg=CARD, fg=INK,
                 font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 8))
        self.preview = tk.Label(left, bg="#edf2f8", fg=MUTED, width=24, height=9,
                                text="选择数独图片\n支持PNG、JPG、BMP")
        self.preview.pack(padx=14, fill="x")
        ttk.Button(left, text="读取剪贴板截图并求解", style="Accent.TButton",
                   command=self.read_clipboard).pack(fill="x", padx=14, pady=(10, 5))
        ttk.Button(left, text="打开图片并识别", style="Accent.TButton",
                   command=self.open_image).pack(fill="x", padx=14, pady=(0, 5))
        ttk.Button(left, text="清空棋盘，手动输入", command=self.clear_board).pack(fill="x", padx=14)

        tk.Label(left, text="02 / 识别说明", bg=CARD, fg=INK,
                 font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        explanation = ("点击右侧格子后按 1–9 修改；\n"
                       "按 0 / Delete / Backspace 清空。\n"
                       "已知数字若有识别错误，请先修正。\n"
                       "蓝色为算法填数，橙色为试探分支。")
        tk.Label(left, text=explanation, justify="left", bg=CARD, fg=MUTED,
                 font=("Microsoft YaHei", 9), wraplength=240).pack(anchor="w", padx=14)

        tk.Label(left, text="03 / 算法日志", bg=CARD, fg=INK,
                 font=("Microsoft YaHei", 12, "bold")).pack(anchor="w", padx=14, pady=(14, 6))
        self.log = tk.Text(left, height=5, wrap="word", state="disabled",
                           bg="#f7f9fc", fg="#475569", relief="flat", padx=9, pady=8,
                           font=("Microsoft YaHei", 9))
        self.log.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        right = tk.Frame(main, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        toolbar = tk.Frame(right, bg=BG)
        toolbar.pack(fill="x")
        self.status = tk.StringVar(value="先截图，再点击左侧按钮读取剪贴板")
        tk.Label(toolbar, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Microsoft YaHei", 10)).pack(side="left", pady=(0, 8))

        self.canvas = tk.Canvas(right, width=self.board_size, height=self.board_size, bg=CARD,
                                highlightthickness=0, cursor="hand2")
        self.canvas.pack(anchor="center", pady=(3, 6))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Key>", self._on_key)
        self.bind_all("<Control-v>", lambda event: self.read_clipboard())
        self._draw_board()

        controls = tk.Frame(right, bg=BG)
        controls.pack(fill="x", pady=(4, 4))
        ttk.Button(controls, text="生成求解步骤", style="Accent.TButton",
                   command=self.start_solve).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="◀ 上一步", command=self.previous).pack(side="left", padx=4)
        self.play_button = ttk.Button(controls, text="▶ 播放", command=self.toggle_play)
        self.play_button.pack(side="left", padx=4)
        ttk.Button(controls, text="下一步 ▶", command=self.next_step).pack(side="left", padx=4)
        ttk.Button(controls, text="导出答案", command=self.save_solution).pack(side="left", padx=4)

        footer = tk.Frame(right, bg=BG)
        self.footer = footer
        footer.pack(fill="x", pady=(4, 0))
        self.progress = tk.StringVar(value="步骤 0 / 0")
        tk.Label(footer, textvariable=self.progress, bg=BG, fg=INK,
                 font=("Microsoft YaHei", 10)).pack(side="left")
        tk.Label(footer, text="播放间隔(ms)", bg=BG, fg=MUTED).pack(side="left", padx=(25, 8))
        self.speed = tk.DoubleVar(value=320)
        ttk.Scale(footer, from_=70, to=1200, orient="horizontal", variable=self.speed,
                  length=175).pack(side="left")

    def _draw_board(self) -> None:
        self.canvas.delete("all")
        start, cell = self.board_pad, self.cell
        current = list(self.steps[self.index].board) if self.steps else self.board
        special = self.steps[self.index] if self.steps else None
        for row in range(9):
            for col in range(9):
                i = row*9+col
                x0, y0 = start+col*cell, start+row*cell
                bg = "#edf3fa" if self.givens[i] else "#ffffff"
                if i == self.selected and not self.steps:
                    bg = "#d7eaff"
                if special and special.cell == i:
                    colors = {"deduction": "#d7f3ec", "guess": "#fff0d1",
                              "backtrack": "#ffdfdd", "conflict": "#ffdfdd"}
                    bg = colors.get(special.kind, bg)
                self.canvas.create_rectangle(x0, y0, x0+cell, y0+cell,
                                             fill=bg, outline="")
                value = current[i]
                if value:
                    color = INK if self.givens[i] else BLUE
                    if special and special.cell == i and special.kind == "guess":
                        color = ORANGE
                    self.canvas.create_text(x0+cell/2, y0+cell/2, text=str(value),
                                            font=("Arial", max(20, int(cell * 0.48)),
                                                  "bold" if self.givens[i] else "normal"),
                                            fill=color)
        for line in range(10):
            width = 4 if line % 3 == 0 else 1
            pos = start+line*cell
            color = INK if width == 4 else "#becbd9"
            self.canvas.create_line(pos, start, pos, start+9*cell, fill=color, width=width)
            self.canvas.create_line(start, pos, start+9*cell, pos, fill=color, width=width)

    def _log(self, lines: list[str]) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.insert("end", "\n".join(lines))
        self.log.configure(state="disabled")
        self.log.see("end")

    def _stop_play(self) -> None:
        self.playing = False
        self.play_button.configure(text="▶ 播放")
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None

    def _invalidate(self) -> None:
        self._stop_play()
        self.steps = []
        self.result = None
        self.index = 0
        self.progress.set("步骤 0 / 0")
        self._draw_board()

    def _on_click(self, event: tk.Event) -> None:
        col = int((event.x-self.board_pad)//self.cell)
        row = int((event.y-self.board_pad)//self.cell)
        if 0 <= row < 9 and 0 <= col < 9:
            if self.steps:
                self._stop_play()
                self.board = self.givens.copy()
                self._invalidate()
            self.selected = row*9+col
            self.canvas.focus_set()
            self._draw_board()

    def _on_key(self, event: tk.Event) -> None:
        if self.selected is None:
            return
        if event.char in "123456789" and len(event.char) == 1:
            number = int(event.char)
        elif event.keysym in ("BackSpace", "Delete") or event.char == "0":
            number = 0
        else:
            return
        self.givens[self.selected] = number
        self.board = self.givens.copy()
        self._invalidate()
        self.status.set("已手动编辑格子。完成后点击『生成求解步骤』")

    def clear_board(self) -> None:
        self.givens = [0]*81
        self.board = self.givens.copy()
        self.selected = None
        self._invalidate()
        self.status.set("棋盘已清空，可以逐格输入数字")
        self._log(["已清空棋盘，等待手动输入。"])

    def open_image(self) -> None:
        path = filedialog.askopenfilename(title="选择数独图片",
                                          filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp"),
                                                     ("全部文件", "*.*")])
        if path:
            self.load_image(path)

    def read_clipboard(self) -> None:
        try:
            content = ImageGrab.grabclipboard()
        except Exception as exc:
            messagebox.showerror("剪贴板读取失败", str(exc))
            return
        if isinstance(content, Image.Image):
            self._begin_recognition(content.copy(), "剪贴板截图", auto_solve=True)
        elif isinstance(content, list) and content and Path(content[0]).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp"}:
            self.load_image(content[0], auto_solve=True)
        else:
            messagebox.showinfo("剪贴板没有图片", "先用 Win+Shift+S 截取数独，再返回这里点击读取剪贴板。")

    def load_image(self, path: str, auto_solve: bool = False) -> None:
        self._begin_recognition(path, Path(path).name, auto_solve)

    def _begin_recognition(self, source: str | Image.Image, label: str, auto_solve: bool) -> None:
        if self.busy:
            messagebox.showinfo("稍等", "正在处理上一项任务。")
            return
        self._stop_play()
        self.busy = True
        self.status.set("正在定位九宫格并识别81个格子，请稍等…")
        self._log([f"正在识别：{label}", "OCR过程可能持续数秒。"])

        def worker() -> None:
            try:
                result = (recognize_image(source) if isinstance(source, str)
                          else recognize_pil_image(source))
                self.events.put(("ocr_ok", (result, auto_solve)))
            except Exception as exc:
                self.events.put(("error", f"图片识别失败：{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def start_solve(self, auto_play: bool = False) -> None:
        if self.busy:
            return
        self._stop_play()
        try:
            validate_board(self.givens)
        except ValueError as exc:
            messagebox.showerror("数独冲突", str(exc))
            return
        if not any(self.givens):
            messagebox.showinfo("提示", "请先识别图片或输入一些已知数字。")
            return
        self.busy = True
        self.auto_play_on_solve = auto_play
        self.status.set("约束传播 + MRV回溯搜索中…")
        starting = self.givens.copy()

        def worker() -> None:
            try:
                answer = solve_board(starting)
                self.events.put(("solve_ok", answer))
            except Exception as exc:
                self.events.put(("error", f"求解失败：{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                self.busy = False
                if kind == "ocr_ok":
                    result, auto_solve = payload
                    self.givens = result.board.copy()
                    self.board = self.givens.copy()
                    self.selected = None
                    self._invalidate()
                    preview = Image.fromarray(result.warped[:, :, ::-1])
                    preview.thumbnail((240, self.preview_height))
                    self.original_image = ImageTk.PhotoImage(preview)
                    self.preview.configure(image=self.original_image, text="", height=self.preview_height)
                    count = sum(bool(v) for v in result.board)
                    self.status.set(f"已识别 {count} 个数字；建议核对棋盘后求解")
                    lines = [f"识别得到 {count} 个数字，空格 {81-count} 个。"]
                    if result.uncertain:
                        locations = ", ".join(f"R{i//9+1}C{i%9+1}" for i in result.uncertain[:16])
                        lines.append(f"低置信度区域：{locations}")
                    lines.append("识别完成。点击某格即可纠正数字。")
                    self._log(lines)
                    if auto_solve:
                        try:
                            validate_board(self.givens)
                        except ValueError as exc:
                            self.status.set("识别结果有冲突，请修正数字后点击生成求解步骤")
                            self._log([str(exc), "修正棋盘后点击『生成求解步骤』。"])
                        else:
                            self.start_solve(auto_play=True)
                elif kind == "solve_ok":
                    self.result = payload
                    self.steps = self.result.steps
                    self.index = 0
                    self._update_step()
                    self.status.set(f"找到解：{len(self.steps)-1}个动画事件；"
                                    f"搜索节点{self.result.nodes}，回溯{self.result.backtracks}次")
                    self._log(["成功求解！点击播放或逐步查看。",
                               f"搜索节点数：{self.result.nodes}",
                               f"试探次数：{self.result.guesses}",
                               f"回溯次数：{self.result.backtracks}"])
                    if self.auto_play_on_solve:
                        self.auto_play_on_solve = False
                        self.toggle_play()
                else:
                    self.status.set(str(payload))
                    messagebox.showerror("提示", str(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _update_step(self) -> None:
        self._draw_board()
        self.progress.set(f"步骤 {self.index} / {max(0, len(self.steps)-1)}")
        if self.steps:
            excerpt = [f"{i:04d}  {self.steps[i].message}"
                       for i in range(max(0, self.index-7), self.index+1)]
            self._log(excerpt)

    def previous(self) -> None:
        self._stop_play()
        if self.steps and self.index > 0:
            self.index -= 1
            self._update_step()

    def next_step(self) -> None:
        self._stop_play()
        if self.steps and self.index < len(self.steps)-1:
            self.index += 1
            self._update_step()

    def toggle_play(self) -> None:
        if not self.steps:
            messagebox.showinfo("提示", "请先点击『生成求解步骤』。")
            return
        if self.playing:
            self._stop_play()
            return
        if self.index == len(self.steps)-1:
            self.index = 0
        self.playing = True
        self.play_button.configure(text="Ⅱ 暂停")
        self._animate()

    def _animate(self) -> None:
        self.timer = None
        if not self.playing:
            return
        if self.index >= len(self.steps)-1:
            self._stop_play()
            return
        self.index += 1
        self._update_step()
        self.timer = self.after(max(50, int(self.speed.get())), self._animate)

    def save_solution(self) -> None:
        if self.result is None:
            messagebox.showinfo("提示", "请先生成完整答案。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png",
                                            initialfile="sudoku_solution.png",
                                            filetypes=[("PNG", "*.png")])
        if path:
            export_board(path, self.result.solution, self.givens)
            self.status.set(f"答案图片已保存：{Path(path).name}")


def main() -> None:
    if "--self-test" in sys.argv:
        result = recognize_image(str(BASE / "example_sudoku.png"))
        solution = solve_board(result.board).solution
        raise SystemExit(0 if verify_solution(result.board, solution) else 1)
    try:
        app = SudokuStudio()
        app.mainloop()
    except tk.TclError as exc:
        print(f"GUI启动失败：{exc}。请在带桌面环境的电脑上运行。", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

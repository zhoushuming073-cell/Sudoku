"""Sudoku Studio: image OCR, editable puzzle, and animated CSP search.

Run with ``python sudoku_studio.py`` after installing requirements and Tesseract.
"""

from __future__ import annotations

import queue
import os
import sys
import threading
import tkinter as tk
import ctypes
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFont, ImageGrab, ImageTk

from screen_automation import (FillCancelled, SavedSelection, ScreenRegion,
                               fill_on_screen, load_selection,
                               make_fill_plan, resolve_saved_region,
                               save_selection, selection_to_region,
                               target_at_region, window_title)
from sudoku_screen_detect import detect_grid
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
MIN_AUTO_FILL_GIVENS = 17


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
        self.window_width = min(420, max(340, work_width - 40))
        self.window_height = min(710, max(620, work_height - 36))
        self.geometry(f"{self.window_width}x{self.window_height}+{max(0, work_width-self.window_width-16)}+0")
        self.minsize(min(340, self.window_width), min(560, self.window_height))
        self.board_pad = 8
        self.cell = min(40, max(30, (self.window_width - 44) // 9))
        self.board_size = self.cell * 9 + self.board_pad * 2
        self.preview_height = 150
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
        self.auto_fill_after_solve = False
        self.screen_needs_review = False
        self.screen_region: ScreenRegion | None = None
        self.screen_corners = None
        self.screen_reference: Image.Image | None = None
        local_data = os.environ.get("LOCALAPPDATA") if sys.platform == "win32" else None
        self.selection_path = (Path(local_data) / "SudokuStudio" / "last_selection.json"
                               if local_data else None)
        self.saved_selection = (load_selection(self.selection_path)
                                if self.selection_path else None)
        self.pending_selection: SavedSelection | None = None
        self.fill_stopped = threading.Event()
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
        scroll = tk.Canvas(self, bg=BG, highlightthickness=0)
        scroll.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=scroll.yview)
        scrollbar.pack(side="right", fill="y")
        scroll.configure(yscrollcommand=scrollbar.set)
        body = tk.Frame(scroll, bg=BG)
        body_id = scroll.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(body_id, width=event.width))
        self.bind_all("<MouseWheel>",
                      lambda event: scroll.yview_scroll(-int(event.delta / 120), "units"))

        head = tk.Frame(body, bg=BG)
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(head, text="SUDOKU STUDIO", bg=BG, fg=INK,
                 font=("Arial", 18, "bold")).pack(anchor="w")
        tk.Label(head, text="自动定位 · 识别 · 求解 · 填写", bg=BG, fg=MUTED,
                 font=("Microsoft YaHei", 9)).pack(anchor="w")

        actions = tk.Frame(body, bg=BG)
        actions.pack(fill="x", padx=14, pady=(4, 3))
        self.select_button = ttk.Button(actions, text="开始填写",
                                        style="Accent.TButton", command=self.start_fill)
        self.select_button.pack(fill="x", pady=(0, 5))
        other = tk.Frame(actions, bg=BG)
        other.pack(fill="x")
        ttk.Button(other, text="重新框选", command=self.select_screen).pack(
            side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(other, text="读取剪贴板", command=self.read_clipboard).pack(
            side="left", fill="x", expand=True, padx=3)
        ttk.Button(other, text="打开图片", command=self.open_image).pack(
            side="left", fill="x", expand=True, padx=(3, 0))

        self.status = tk.StringVar(value="点击『开始填写』自动寻找屏幕上的数独棋盘")
        tk.Label(body, textvariable=self.status, bg=BG, fg=MUTED,
                 font=("Microsoft YaHei", 9), justify="left",
                 wraplength=self.window_width - 38).pack(fill="x", padx=14, pady=(2, 3))

        self.canvas = tk.Canvas(body, width=self.board_size, height=self.board_size,
                                bg=CARD, highlightthickness=0, cursor="hand2")
        self.canvas.pack(anchor="center", pady=(2, 5))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Key>", self._on_key)
        self.bind_all("<Control-v>", lambda event: self.read_clipboard())
        self._draw_board()

        solve_row = tk.Frame(body, bg=BG)
        solve_row.pack(fill="x", padx=14, pady=(2, 4))
        ttk.Button(solve_row, text="生成求解步骤", style="Accent.TButton",
                   command=self.start_solve).pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.fill_button = ttk.Button(solve_row, text="填写到屏幕",
                                      command=self.start_screen_fill)
        self.fill_button.pack(side="left", fill="x", expand=True, padx=(3, 0))
        self.fill_button.state(["disabled"])

        playback = tk.Frame(body, bg=BG)
        playback.pack(fill="x", padx=14, pady=(0, 4))
        ttk.Button(playback, text="◀ 上一步", command=self.previous).pack(
            side="left", fill="x", expand=True, padx=(0, 3))
        self.play_button = ttk.Button(playback, text="▶ 播放", command=self.toggle_play)
        self.play_button.pack(side="left", fill="x", expand=True, padx=3)
        ttk.Button(playback, text="下一步 ▶", command=self.next_step).pack(
            side="left", fill="x", expand=True, padx=(3, 0))

        tools = tk.Frame(body, bg=BG)
        tools.pack(fill="x", padx=14, pady=(0, 5))
        ttk.Button(tools, text="清空棋盘", command=self.clear_board).pack(side="left")
        ttk.Button(tools, text="导出答案", command=self.save_solution).pack(
            side="left", padx=(5, 0))
        self.progress = tk.StringVar(value="步骤 0 / 0")
        tk.Label(tools, textvariable=self.progress, bg=BG, fg=INK,
                 font=("Microsoft YaHei", 9)).pack(side="right")

        speed_row = tk.Frame(body, bg=BG)
        speed_row.pack(fill="x", padx=14, pady=(0, 9))
        tk.Label(speed_row, text="播放间隔", bg=BG, fg=MUTED).pack(side="left")
        self.speed = tk.DoubleVar(value=320)
        ttk.Scale(speed_row, from_=70, to=1200, orient="horizontal",
                  variable=self.speed).pack(side="left", fill="x", expand=True, padx=(8, 0))

        tk.Label(body, text="识别预览", bg=BG, fg=INK,
                 font=("Microsoft YaHei", 11, "bold")).pack(anchor="w", padx=14)
        self.preview = tk.Label(body, bg="#edf2f8", fg=MUTED, width=24, height=7,
                                text="图片识别后显示在这里")
        self.preview.pack(fill="x", padx=14, pady=(5, 11))

        tk.Label(body, text="算法日志", bg=BG, fg=INK,
                 font=("Microsoft YaHei", 11, "bold")).pack(anchor="w", padx=14)
        self.log = tk.Text(body, height=6, wrap="word", state="disabled",
                           bg="#f7f9fc", fg="#475569", relief="flat", padx=9, pady=8,
                           font=("Microsoft YaHei", 9))
        self.log.pack(fill="x", padx=14, pady=(5, 14))

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
        self.fill_button.state(["disabled"])
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
        self.screen_needs_review = False
        self._invalidate()
        self.status.set("已手动编辑格子。完成后点击『生成求解步骤』")

    def clear_board(self) -> None:
        self.screen_region = None
        self.screen_corners = None
        self.screen_reference = None
        self.screen_needs_review = False
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

    def start_fill(self) -> None:
        if sys.platform != "win32":
            messagebox.showinfo("提示", "屏幕自动填写目前只支持 Windows。")
            return
        if self.busy:
            messagebox.showinfo("稍等", "正在处理上一项任务。")
            return
        self._stop_play()
        self.withdraw()
        self.status.set("正在扫描屏幕上的数独棋盘…")
        self.after(250, self._scan_screen)

    def _scan_screen(self) -> None:
        try:
            screenshot = ImageGrab.grab()
            preferred = ((self.saved_selection.left, self.saved_selection.top,
                          self.saved_selection.right, self.saved_selection.bottom)
                         if self.saved_selection else None)
            detected = detect_grid(screenshot, preferred)
            candidate = None
            if detected:
                try:
                    region = target_at_region(ScreenRegion(*detected.box, 0))
                except ValueError:
                    detected = None
                else:
                    title = window_title(region.target_hwnd)
                    if title:
                        candidate = SavedSelection.from_region(region, screenshot.size, title)
                    label = "屏幕自动定位"
            if not detected and self.saved_selection:
                region = resolve_saved_region(self.saved_selection, screenshot.size)
                label = "上次框选区域"
            elif not detected:
                raise ValueError("没有找到清晰的数独方格，请点击『重新框选』。")
            cropped = screenshot.crop((region.left, region.top, region.right, region.bottom))
            self.deiconify()
            self.lift()
            self._begin_recognition(cropped, label, auto_solve=True,
                                    auto_fill=True, screen_region=region,
                                    saved_candidate=candidate)
        except Exception as exc:
            self.deiconify()
            self.lift()
            self.status.set(str(exc))
            messagebox.showinfo("未找到数独棋盘", str(exc))

    def select_screen(self) -> None:
        if sys.platform != "win32":
            messagebox.showinfo("提示", "屏幕自动填写目前只支持 Windows。")
            return
        if self.busy:
            messagebox.showinfo("稍等", "正在处理上一项任务。")
            return
        self._stop_play()
        self.withdraw()
        self.after(250, self._show_screen_selector)

    def _show_screen_selector(self) -> None:
        try:
            screenshot = ImageGrab.grab()
            logical_width, logical_height = self.winfo_screenwidth(), self.winfo_screenheight()
            overlay = tk.Toplevel(self)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            overlay.geometry(f"{logical_width}x{logical_height}+0+0")
            canvas = tk.Canvas(overlay, width=logical_width, height=logical_height,
                               highlightthickness=0, cursor="crosshair")
            canvas.pack(fill="both", expand=True)
            backdrop = screenshot.resize((logical_width, logical_height), Image.Resampling.BILINEAR)
            overlay.backdrop = ImageTk.PhotoImage(backdrop, master=overlay)
            canvas.create_image(0, 0, anchor="nw", image=overlay.backdrop)
            canvas.create_rectangle(0, 0, logical_width, 37, fill="#172437", outline="")
            canvas.create_text(14, 19, anchor="w", fill="white",
                               text="拖动框选完整数独外边框 · 按 Esc 取消",
                               font=("Microsoft YaHei", 11))
            selection = {"start": None, "rectangle": None}

            def cancel(event=None) -> None:
                overlay.destroy()
                self.deiconify()
                self.lift()
                self.status.set("已取消屏幕框选")

            def press(event) -> None:
                selection["start"] = (event.x, event.y)
                if selection["rectangle"] is not None:
                    canvas.delete(selection["rectangle"])
                selection["rectangle"] = canvas.create_rectangle(
                    event.x, event.y, event.x, event.y, outline="#f15a45", width=3)

            def drag(event) -> None:
                if selection["start"] is not None:
                    x, y = selection["start"]
                    canvas.coords(selection["rectangle"], x, y, event.x, event.y)

            def release(event) -> None:
                if selection["start"] is None:
                    return
                overlay.destroy()
                try:
                    region = selection_to_region(selection["start"], (event.x, event.y),
                                                 screenshot.size,
                                                 (logical_width, logical_height), 0)
                    region = target_at_region(region)
                except ValueError as exc:
                    self.deiconify()
                    self.lift()
                    messagebox.showinfo("框选范围不合适", str(exc))
                    return
                cropped = screenshot.crop((region.left, region.top,
                                           region.right, region.bottom))
                self.deiconify()
                self.lift()
                title = window_title(region.target_hwnd)
                if title:
                    self.saved_selection = SavedSelection.from_region(
                        region, screenshot.size, title)
                    if self.selection_path:
                        try:
                            save_selection(self.selection_path, self.saved_selection)
                        except OSError:
                            pass
                self._begin_recognition(cropped, "屏幕框选", auto_solve=True,
                                        auto_fill=True, screen_region=region)

            canvas.bind("<ButtonPress-1>", press)
            canvas.bind("<B1-Motion>", drag)
            canvas.bind("<ButtonRelease-1>", release)
            overlay.bind("<Escape>", cancel)
            overlay.focus_force()
        except Exception as exc:
            self.deiconify()
            self.lift()
            messagebox.showerror("无法框选屏幕", str(exc))

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

    def _begin_recognition(self, source: str | Image.Image, label: str, auto_solve: bool,
                           auto_fill: bool = False,
                           screen_region: ScreenRegion | None = None,
                           saved_candidate: SavedSelection | None = None) -> None:
        if self.busy:
            messagebox.showinfo("稍等", "正在处理上一项任务。")
            return
        self._stop_play()
        self.busy = True
        self.screen_needs_review = False
        self.pending_selection = saved_candidate
        self.screen_region = screen_region
        self.screen_corners = None
        self.screen_reference = source.copy() if screen_region and isinstance(source, Image.Image) else None
        self.status.set("正在定位九宫格并识别81个格子，请稍等…")
        lines = [f"正在识别：{label}", "OCR过程可能持续数秒。"]
        if screen_region:
            lines.append(f"目标窗口：{window_title(screen_region.target_hwnd) or '未命名窗口'}")
        self._log(lines)

        def worker() -> None:
            try:
                result = (recognize_image(source) if isinstance(source, str)
                          else recognize_pil_image(source))
                self.events.put(("ocr_ok", (result, auto_solve, auto_fill)))
            except Exception as exc:
                self.events.put(("error", f"图片识别失败：{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def start_solve(self, auto_play: bool = False, auto_fill: bool = False) -> None:
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
        self.auto_fill_after_solve = auto_fill
        self.status.set("约束传播 + MRV回溯搜索中…")
        starting = self.givens.copy()

        def worker() -> None:
            try:
                answer = solve_board(starting)
                self.events.put(("solve_ok", answer))
            except Exception as exc:
                self.events.put(("error", f"求解失败：{exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def start_screen_fill(self) -> None:
        if self.busy or self.result is None or self.screen_region is None or self.screen_corners is None:
            return
        try:
            actions = make_fill_plan(self.givens, self.result.solution,
                                     self.screen_region, self.screen_corners)
        except ValueError as exc:
            messagebox.showerror("无法自动填写", str(exc))
            return
        if not actions:
            self.status.set("棋盘已填满，无需自动填写")
            return
        self._stop_play()
        self.busy = True
        self.fill_stopped.clear()
        self.status.set(f"准备填写 {len(actions)} 格；切换窗口或按住 Esc 可停止")
        self.withdraw()

        def worker() -> None:
            try:
                fill_on_screen(actions, self.screen_region.target_hwnd,
                               self.fill_stopped,
                               lambda count, total: self.events.put(("fill_progress", (count, total))),
                               region=self.screen_region, reference=self.screen_reference,
                               corners=self.screen_corners)
                self.events.put(("fill_done", len(actions)))
            except FillCancelled as exc:
                self.events.put(("fill_cancelled", str(exc)))
            except Exception as exc:
                self.events.put(("fill_error", str(exc)))

        self.after(250, lambda: threading.Thread(target=worker, daemon=True).start())

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "fill_progress":
                    count, total = payload
                    self.status.set(f"正在填写屏幕数独：{count}/{total} 格；按住 Esc 可停止")
                    continue
                self.busy = False
                if kind == "ocr_ok":
                    result, auto_solve, auto_fill = payload
                    self.givens = result.board.copy()
                    self.board = self.givens.copy()
                    self.selected = None
                    self._invalidate()
                    self.screen_corners = result.corners if self.screen_region else None
                    self.screen_needs_review = auto_fill and bool(result.uncertain)
                    preview = Image.fromarray(result.warped[:, :, ::-1])
                    preview.thumbnail((240, self.preview_height))
                    self.original_image = ImageTk.PhotoImage(preview, master=self)
                    self.preview.configure(image=self.original_image, text="", height=self.preview_height)
                    count = sum(bool(v) for v in result.board)
                    self.status.set(f"已识别 {count} 个数字；" +
                                    ("正在自动求解并填写" if auto_fill else "建议核对棋盘后求解"))
                    lines = [f"识别得到 {count} 个数字，空格 {81-count} 个。"]
                    if result.uncertain:
                        locations = ", ".join(f"R{i//9+1}C{i%9+1}" for i in result.uncertain[:16])
                        lines.append(f"低置信度区域：{locations}")
                    lines.append("识别完成，准备自动求解并填写。" if auto_fill
                                 else "识别完成。点击某格即可纠正数字。")
                    self._log(lines)
                    if auto_solve:
                        if auto_fill and count < MIN_AUTO_FILL_GIVENS:
                            self.pending_selection = None
                            self.status.set(f"仅识别到 {count} 个数字，自动填写已停止；请重新框选")
                            self._log([f"仅识别到 {count} 个数字，可能未框住完整棋盘。",
                                       "请点击『重新框选』后再试。"])
                        else:
                            try:
                                validate_board(self.givens)
                            except ValueError as exc:
                                self.pending_selection = None
                                self.status.set("识别结果有冲突，请修正数字后点击生成求解步骤")
                                self._log([str(exc), "修正棋盘后点击『生成求解步骤』。"])
                            else:
                                self.start_solve(auto_play=not auto_fill,
                                                 auto_fill=auto_fill and not self.screen_needs_review)
                                if self.screen_needs_review:
                                    self.status.set("有数字识别意见不一致，请核对后点击『填写到屏幕』")
                elif kind == "solve_ok":
                    self.result = payload
                    if self.pending_selection:
                        self.saved_selection = self.pending_selection
                        if self.selection_path:
                            try:
                                save_selection(self.selection_path, self.saved_selection)
                            except OSError:
                                pass
                        self.pending_selection = None
                    self.steps = self.result.steps
                    self.index = 0
                    self._update_step()
                    self.status.set(f"找到解：{len(self.steps)-1}个动画事件；"
                                    f"搜索节点{self.result.nodes}，回溯{self.result.backtracks}次")
                    self._log(["成功求解！点击播放或逐步查看。",
                               f"搜索节点数：{self.result.nodes}",
                               f"试探次数：{self.result.guesses}",
                               f"回溯次数：{self.result.backtracks}"])
                    if self.screen_region is not None:
                        self.fill_button.state(["!disabled"])
                    if self.screen_needs_review:
                        self.status.set("有数字识别意见不一致，请核对后点击『填写到屏幕』")
                    if self.auto_fill_after_solve:
                        self.auto_fill_after_solve = False
                        self.after(300, self.start_screen_fill)
                    if self.auto_play_on_solve:
                        self.auto_play_on_solve = False
                        self.toggle_play()
                elif kind in ("fill_done", "fill_cancelled", "fill_error"):
                    self.deiconify()
                    self.lift()
                    self.fill_button.state(["disabled"])
                    if kind == "fill_done":
                        self.status.set(f"已自动填写 {payload} 个空格；请核对目标页面")
                        self._log([f"屏幕自动填写完成：{payload} 个空格。"])
                    else:
                        self.status.set(str(payload))
                        self._log([str(payload)])
                        if kind == "fill_error":
                            messagebox.showerror("自动填写失败", str(payload))
                else:
                    self.pending_selection = None
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


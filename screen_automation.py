"""Map recognized cells back to the screen and enter a solution on Windows."""

from __future__ import annotations

import ctypes
import sys
import time
from contextlib import contextmanager
from ctypes import wintypes
from dataclasses import dataclass
from threading import Event
from typing import Callable, Iterator

import cv2
import numpy as np
from PIL import Image, ImageGrab

from sudoku_solver import verify_solution


@dataclass(frozen=True)
class ScreenRegion:
    left: int
    top: int
    right: int
    bottom: int
    target_hwnd: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


@dataclass(frozen=True)
class FillAction:
    index: int
    digit: int
    x: int
    y: int


class FillCancelled(Exception):
    """The user stopped input or the target window changed."""


def selection_to_region(start: tuple[int, int], end: tuple[int, int],
                        image_size: tuple[int, int], logical_size: tuple[int, int],
                        target_hwnd: int) -> ScreenRegion:
    """Convert a Tk drag rectangle into physical screenshot coordinates."""
    logical_width, logical_height = logical_size
    image_width, image_height = image_size
    if min(logical_width, logical_height, image_width, image_height) <= 0:
        raise ValueError("无法读取屏幕尺寸。")
    x0, x1 = sorted((max(0, min(logical_width, start[0])),
                     max(0, min(logical_width, end[0]))))
    y0, y1 = sorted((max(0, min(logical_height, start[1])),
                     max(0, min(logical_height, end[1]))))
    if x1 - x0 < 90 or y1 - y0 < 90 or not .65 < (x1-x0)/(y1-y0) < 1.55:
        raise ValueError("请只框选完整、近似正方形的数独棋盘。")
    return ScreenRegion(round(x0*image_width/logical_width),
                        round(y0*image_height/logical_height),
                        round(x1*image_width/logical_width),
                        round(y1*image_height/logical_height), target_hwnd)


def make_fill_plan(givens: list[int], solution: list[int], region: ScreenRegion,
                   corners: np.ndarray) -> list[FillAction]:
    """Map empty cell centers through the inverse OCR perspective transform."""
    if region.width < 90 or region.height < 90:
        raise ValueError("框选范围太小，无法可靠定位81个格子。")
    if not verify_solution(givens, solution):
        raise ValueError("答案与已知数字不一致，已停止自动填写。")
    source = np.array([[0, 0], [9, 0], [9, 9], [0, 9]], dtype=np.float32)
    transform = cv2.getPerspectiveTransform(source, corners.astype(np.float32))
    centers = np.array([[[col + .5, row + .5]]
                        for row in range(9) for col in range(9)], dtype=np.float32)
    mapped = cv2.perspectiveTransform(centers, transform).reshape(81, 2)
    actions = []
    for index, (x, y) in enumerate(mapped):
        if givens[index]:
            continue
        screen_x, screen_y = round(region.left + float(x)), round(region.top + float(y))
        if not (region.left < screen_x < region.right and
                region.top < screen_y < region.bottom):
            raise ValueError("识别出的棋盘边界超出框选范围，请重新框选。")
        actions.append(FillAction(index, solution[index], screen_x, screen_y))
    return actions


_ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else wintypes.DWORD


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", _ULONG_PTR)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUT_VALUE(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("value",)
    _fields_ = [("type", wintypes.DWORD), ("value", _INPUT_VALUE)]


def _events_sent(user32: object, first: _INPUT, second: _INPUT) -> None:
    events = (_INPUT * 2)(first, second)
    sent = user32.SendInput(2, events, ctypes.sizeof(_INPUT))
    if sent != 2:
        raise RuntimeError("Windows 未接受模拟输入。目标程序可能以管理员权限运行。")


def _click(user32: object) -> None:
    down, up = _INPUT(), _INPUT()
    down.type = up.type = 0
    down.mi.dwFlags = 0x0002  # MOUSEEVENTF_LEFTDOWN
    up.mi.dwFlags = 0x0004    # MOUSEEVENTF_LEFTUP
    _events_sent(user32, down, up)


def _press_digit(user32: object, digit: int) -> None:
    down, up = _INPUT(), _INPUT()
    down.type = up.type = 1  # INPUT_KEYBOARD
    down.ki.wVk = up.ki.wVk = ord(str(digit))
    up.ki.dwFlags = 0x0002  # KEYEVENTF_KEYUP
    _events_sent(user32, down, up)


@contextmanager
def _physical_dpi() -> Iterator[object]:
    user32 = ctypes.windll.user32
    switch = user32.SetThreadDpiAwarenessContext
    switch.argtypes = [ctypes.c_void_p]
    switch.restype = ctypes.c_void_p
    previous = switch(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    if not previous:
        raise RuntimeError("无法切换到物理屏幕坐标，自动填写已停止。")
    try:
        yield user32
    finally:
        switch(previous)


def foreground_window() -> int:
    if sys.platform != "win32":
        return 0
    user32 = ctypes.windll.user32
    user32.GetForegroundWindow.restype = wintypes.HWND
    return int(user32.GetForegroundWindow() or 0)


def window_title(hwnd: int) -> str:
    if sys.platform != "win32" or not hwnd:
        return ""
    title = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetWindowTextW(hwnd, title, len(title))
    return title.value


def fill_on_screen(actions: list[FillAction], target_hwnd: int,
                   stopped: Event, progress: Callable[[int, int], None],
                   region: ScreenRegion | None = None,
                   reference: Image.Image | None = None) -> None:
    if sys.platform != "win32":
        raise RuntimeError("自动填写目前只支持 Windows。")
    if not target_hwnd or not actions:
        raise ValueError("没有可填写的格子或目标窗口。")
    with _physical_dpi() as user32:
        user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
        user32.SendInput.restype = wintypes.UINT
        user32.SetPhysicalCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        user32.GetPhysicalCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        user32.WindowFromPoint.argtypes = [wintypes.POINT]
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        bounds = wintypes.RECT()
        if not user32.GetWindowRect(target_hwnd, ctypes.byref(bounds)):
            raise FillCancelled("目标窗口已经关闭，未发送数字。")
        if any(not (bounds.left <= action.x < bounds.right and
                    bounds.top <= action.y < bounds.bottom) for action in actions):
            raise FillCancelled("目标窗口位置发生变化，请重新框选数独。")
        for _ in range(30):  # Allow the target window to regain focus.
            if stopped.is_set() or user32.GetAsyncKeyState(0x1B) & 0x8000:
                raise FillCancelled("已按 Esc 停止自动填写。")
            if foreground_window() == target_hwnd:
                break
            user32.SetForegroundWindow(target_hwnd)
            time.sleep(.1)
        else:
            raise FillCancelled("目标窗口未获得焦点，未发送任何数字。")
        if region is not None and reference is not None:
            current = ImageGrab.grab(bbox=(region.left, region.top,
                                            region.right, region.bottom))
            before = np.asarray(reference.convert("L").resize((120, 120)), dtype=np.int16)
            after = np.asarray(current.convert("L").resize((120, 120)), dtype=np.int16)
            if float(np.abs(before - after).mean()) > 18:
                raise FillCancelled("屏幕数独与框选时不同，请重新框选后再试。")

        for count, action in enumerate(actions, 1):
            if stopped.is_set() or user32.GetAsyncKeyState(0x1B) & 0x8000:
                raise FillCancelled(f"已停止自动填写，已填 {count-1} 格。")
            if any(user32.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x01)):
                raise FillCancelled(f"检测到用户正在操作键盘或鼠标，已填 {count-1} 格。")
            if foreground_window() != target_hwnd:
                raise FillCancelled(f"目标窗口已切换，已填 {count-1} 格。")
            at_point = user32.WindowFromPoint(wintypes.POINT(action.x, action.y))
            if user32.GetAncestor(at_point, 2) != target_hwnd:
                raise FillCancelled(f"目标格子被其他窗口遮挡，已填 {count-1} 格。")
            if not user32.SetPhysicalCursorPos(action.x, action.y):
                raise RuntimeError("无法移动鼠标到目标格子。")
            point = wintypes.POINT()
            user32.GetPhysicalCursorPos(ctypes.byref(point))
            if abs(point.x - action.x) > 2 or abs(point.y - action.y) > 2:
                raise RuntimeError("屏幕坐标与鼠标位置不一致，自动填写已停止。")
            _click(user32)
            time.sleep(.06)
            _press_digit(user32, action.digit)
            progress(count, len(actions))
            time.sleep(.09)


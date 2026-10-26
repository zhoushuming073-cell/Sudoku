# Sudoku Studio — 数独图片识别与动态求解

一个离线桌面程序：从剪贴板截图或 PNG/JPG 图片读取 9×9 数独，手动修正 OCR 结果，用约束传播和 MRV 回溯搜索求解，并逐步播放推导、试探和撤销过程。可导出解答 PNG。

## 文件

- `sudoku_studio.py` — 启动程序和 Tkinter 图形界面。
- `sudoku_ocr.py` — OpenCV 透视校正 + Tesseract 数字识别。
- `sudoku_solver.py` — 约束传播、隐藏唯一数、MRV、回溯，以及逐步记录。
- `example_sudoku.png` — 随包附带的原始示例。
- `example_solution.png` — 用程序求出的示例答案图。
- `tests/test_solver.py` — 可独立运行的求解器测试。
- `SudokuStudio.spec` — Windows 可执行程序的打包配置，包含 Tesseract OCR 引擎。

## Windows 可执行版

在 [Releases](https://github.com/zhoushuming073-cell/Sudoku/releases/latest) 下载 `SudokuStudio_Windows.zip` 并解压。

在打包输出的 `SudokuStudio` 文件夹中双击 `SudokuStudio.exe`。整个文件夹需要一起保留，不能只移动 exe；可执行版已包含 Python 依赖和 OCR 引擎。

如果需要从源码重新打包，在装有 Tesseract 的 Windows 电脑上执行：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm SudokuStudio.spec
```

## 安装（Windows / macOS / Linux）

需要 Python 3.10 或更高版本。

1. 安装 [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)（数字OCR引擎）。Windows 可安装 Tesseract，并确保 `tesseract.exe` 存在于 PATH；程序也会检测默认的 `C:\Program Files\Tesseract-OCR\tesseract.exe`。如果安装在其他位置，可设置 `TESSERACT_CMD` 环境变量指向其完整路径。macOS 通常使用 `brew install tesseract`；Ubuntu/Debian 通常使用 `sudo apt install tesseract-ocr`。
2. 解压 ZIP，在解压文件夹中打开命令行，执行：

   ```bash
   python -m pip install -r requirements.txt
   python sudoku_studio.py
   ```

   Windows 系统建议在项目内建立独立环境：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe sudoku_studio.py
   ```

3. 程序启动后可直接读取剪贴板截图；也可以点击“打开图片并识别”选择图片。随包附带的 `example_sudoku.png` 可用来试运行。

Windows 用户完成依赖安装后，也可以直接双击 `start_windows.bat` 启动；脚本会优先使用项目内的 `.venv`，没有 `.venv` 时使用系统 `python`。Tesseract 若安装在 `C:\Program Files\Tesseract-OCR\tesseract.exe`，程序会自动找到它，无需手动修改 PATH。

注意：Linux 如提示 `No module named tkinter`，还需要安装系统的 Python Tkinter 包，例如 `sudo apt install python3-tk`。

## 使用

1. **截图识别并求解**：按 `Win+Shift+S` 框选完整数独，返回程序点击“读取剪贴板截图并求解”，或按 `Ctrl+V`。识别成功且没有明显数字冲突时，会自动生成并播放求解过程。
2. **核对**：将右侧识别盘面与图片核对。鼠标点击格子后按 `1`–`9` 修改，按 `0`、`Delete`、`Backspace` 清空。如果识别数字有冲突，修正后点击“生成求解步骤”。
3. **文件识别**：点击“打开图片并识别”可选择 PNG/JPG 等图片；核对后点击“生成求解步骤”。
4. **展示**：点击播放/暂停、上一步/下一步，拖动滑块调整播放速度。
5. **保存**：点击“导出答案”，保存高分辨率 PNG。

## 界面颜色

- 深色数字：图片识别或手动输入的已知数字。
- 蓝色数字：算法推导出的数字。
- 绿色背景：确定性推导。
- 橙色背景：搜索试探。
- 红色背景：冲突或撤销试探。

## 搜索算法

求解器先迭代寻找“格子只有一个候选值”和“某行/列/宫中的一个数字只能放在一个位置”两类确定性推导。若卡住，采用最少剩余值 MRV 选择候选数字最少的格子，并以未填充关联格数量作为并列破局规则。枚举候选值，遇到冲突回溯。搜索过程保存每一步完整棋盘快照，UI可以前后跳步与播放。

**边界说明**：程序求出一个满足全部规则的解，不会声称所有题目都有唯一解。对于严重模糊、歪斜、手写数字或部分遮挡的图片，OCR可能出错，必须手工核对。程序有动画步骤数安全上限，极端欠约束的题目可能触发此上限；触发时会明确报错，不会误报无解。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

建议优先使用清晰截图，确保整个9×9边框完整显示。程序完全在本机处理图片，不会上传用户图片。

# Sudoku Studio — 数独图片识别与动态求解

一个离线桌面程序：自动定位屏幕上的数独方格，也可手动框选、读取剪贴板截图或 PNG/JPG 图片。识别 9×9 棋盘后，用约束传播和 MRV 回溯搜索求解。Windows 上可以将答案自动填写回原窗口，也可以逐步播放推导过程和导出解答 PNG。界面采用靠屏幕右侧的窄竖版布局，较小的屏幕可向下滚动查看预览和日志。

## 文件

- `sudoku_studio.py` — 启动程序和 Tkinter 图形界面。
- `sudoku_ocr.py` — OpenCV 透视校正 + RapidOCR PP-OCRv6 数字识别，并用 Tesseract 和字体模板交叉核对。
- `sudoku_solver.py` — 约束传播、隐藏唯一数、MRV、回溯，以及逐步记录。
- `screen_automation.py` — 屏幕框选坐标转换、格子定位与 Windows 模拟输入。
- `sudoku_screen_detect.py` — 从整张屏幕截图中自动定位 9×9 数独网格。
- `example_sudoku.png` — 随包附带的原始示例。
- `example_solution.png` — 用程序求出的示例答案图。
- `tests/` — 求解、OCR 和屏幕格子定位测试。
- `SudokuStudio.spec` — Windows 可执行程序的打包配置，包含 Tesseract OCR 引擎。
- `SudokuStudio_Portable.spec` — 单文件 Windows 程序打包配置。

## Windows 可执行版

在 [Releases](https://github.com/zhoushuming073-cell/Sudoku/releases/latest) 下载 `SudokuStudio_Portable.exe` 单文件版，或下载 `SudokuStudio_Windows.zip` 文件夹版并解压。单文件版首次启动会释放临时文件，启动稍慢。

在打包输出的 `SudokuStudio` 文件夹中双击 `SudokuStudio.exe`。整个文件夹需要一起保留，不能只移动 exe；可执行版已包含 Python 依赖和 OCR 引擎。

如果需要从源码重新打包，在装有 Tesseract 的 Windows 电脑上执行：

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm SudokuStudio.spec
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm SudokuStudio_Portable.spec
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

1. **屏幕自动填写（Windows）**：让完整数独棋盘显示在屏幕上，点击一次“开始填写”。程序会从整张屏幕自动定位方格、识别、求解，并在目标窗口逐格输入答案。找不到可靠方格时会尝试上次保存的区域；如果仍找不到，点击“重新框选”指定位置。目标窗口位置或屏幕尺寸改变时也可重新框选。已知数字不会被覆盖；识别到的数字不足 17 个、数字有冲突或无法求解时会停止。RapidOCR 与原识别器意见不同的格子会暂停自动填写，供手动核对。每个计划格子只输入一次；完成后请查看目标页面。如果确实有漏填，重新点击“开始填写”会重新识别屏幕并生成新的填写计划。填写期间按住 `Esc`，或切换窗口，即可停止。目标游戏需要支持“点击格子后按数字键输入”。
2. **剪贴板截图**：按 `Win+Shift+S` 截取完整数独，返回程序点击“读取剪贴板”，或按 `Ctrl+V`。程序会识别并播放求解过程。
3. **核对**：将识别盘面与原图核对。鼠标点击格子后按 `1`–`9` 修改，按 `0`、`Delete`、`Backspace` 清空。如果识别数字有冲突，修正后点击“生成求解步骤”。
4. **文件识别**：点击“打开图片”可选择 PNG/JPG 等图片；核对后点击“生成求解步骤”。
5. **展示与保存**：点击播放/暂停、上一步/下一步，拖动滑块调整播放速度。点击“导出答案”保存高分辨率 PNG。

## 界面颜色

- 深色数字：图片识别或手动输入的已知数字。
- 蓝色数字：算法推导出的数字。
- 绿色背景：确定性推导。
- 橙色背景：搜索试探。
- 红色背景：冲突或撤销试探。

## 搜索算法

求解器先迭代寻找“格子只有一个候选值”和“某行/列/宫中的一个数字只能放在一个位置”两类确定性推导。若卡住，采用最少剩余值 MRV 选择候选数字最少的格子，并以未填充关联格数量作为并列破局规则。枚举候选值，遇到冲突回溯。搜索过程保存每一步完整棋盘快照，UI可以前后跳步与播放。

### 运筹学视角：把规则转化为约束，再减少无效搜索

数独可以建模为一个**约束满足问题（Constraint Satisfaction Problem, CSP）**。目标不是最大化某个分数，而是找到一个同时满足全部规则的可行解。这也是运筹学建模的基本思路：明确决策变量、写出约束，再选择合适的求解方法。

#### 1. 0-1 整数规划表述

定义二元决策变量：

`x_{r,c,d} \in \{0,1\}`

当且仅当第 (r) 行、第 (c) 列填入数字 (d) 时，(x_{r,c,d}=1)，其中 (r,c,d\in\{1,\ldots,9\})。共计 (9^3=729) 个二元变量。规则可以写成：

- **每个格子恰好填一个数字：** 对任意 (r,c)，(sum_{d=1}^{9}x_{r,c,d}=1)。
- **每行的每个数字恰好出现一次：** 对任意 (r,d)，(sum_{c=1}^{9}x_{r,c,d}=1)。
- **每列的每个数字恰好出现一次：** 对任意 (c,d)，(sum_{r=1}^{9}x_{r,c,d}=1)。
- **每个 3×3 宫的每个数字恰好出现一次：** 对每个宫 (b) 和数字 (d)，该宫内所有对应 (x_{r,c,d}) 之和等于 1。
- **已知数字固定：** 对题面给定的每个数字，固定对应变量为 1。

这是数独的 0-1 整数规划数学表述；因为只需找可行解，目标函数可写为 (min 0)。**本项目没有调用 MILP 求解器**，实际采用的是下述 CSP 约束传播与回溯搜索。

#### 2. 约束传播：先做确定性推导

对空格 ((r,c))，设 (R_r)、(L_c)、(B_{r,c}) 分别表示其所在行、列、宫中已经出现的数字，则候选集为：

`C_{r,c}=\{1,\ldots,9\}\setminus(R_r\cup L_c\cup B_{r,c})`

程序反复应用两类规则：

- **唯一候选（Naked Single）：** 若一个空格的候选集只有一个数字，该数字就是此格的必填值。
- **隐藏唯一（Hidden Single）：** 若某个数字在一行、一列或一宫的所有空格中只能放在一个位置，则该位置必须填入这个数字。

每次填数都会进一步缩小其他格子的候选集，形成连锁推导。若某个空格没有候选值，或某行、列、宫再也无法容纳某个必需数字，则当前分支发生矛盾。

#### 3. 搜索排序：MRV 与 Degree Heuristic

按固定行序逐格尝试很简单，但没有利用不同空格之间的约束强弱。确定性推导无法继续时，程序使用 **MRV（Minimum Remaining Values，最少剩余值）**，优先选择候选集最小的未填格：

`i^*=\arg\min_{i\in U}|C_i|`

其中 (U) 是尚未填写的格子集合。候选数越少，越容易尽早暴露矛盾，从而避免在明显受限的地方做大量无效尝试。

若多个格子的候选数相同，则使用 **Degree Heuristic（关联度启发式）** 打破平局：优先选择与更多未填格共享约束的格子。当前代码使用未填充关联格数量作为这一规则的评分。

这两种启发式只改变搜索顺序，不会删除任何合法候选值，因此不会因为排序本身破坏搜索完备性。它们是经典启发式方法，并非本项目原创算法。

#### 4. 回溯搜索：试探、检测、撤销

算法的基本流程如下：

```text
solve(board):
    重复应用约束传播，直到没有新的确定性填数
    如果出现矛盾：返回失败
    如果所有格子都已填满：返回一个合法解

    用 MRV 选择候选数最少的空格
    对该格的每个候选数字：
        在当前棋盘副本中试填该数字
        递归求解
        如果成功：返回解
        如果失败：撤销本次试探，尝试下一个候选值

    所有候选值都失败：返回失败
```

**约束传播负责缩小搜索空间，回溯负责系统地检查剩余可能性。** 前者尽可能少猜，后者避免因为一次错误试探就错过其他合法解。最坏情况下，组合搜索仍可能随空格数量快速增长，启发式排序是减少实际搜索量的方法，而不是消除最坏情况复杂度的保证。

#### 5. 从求解器到可解释的动态过程

求解器把每一步棋盘状态及原因记录为事件，包括确定性推导、试探、冲突、回溯和求解完成。因此，界面可以播放算法的决策轨迹，而不只是显示最终答案。

更一般地，这个思路可以迁移到其他约束问题：把问题表达为“变量—候选域—约束”，先传播确定性信息，再动态选择最受约束的变量进行搜索。图着色、课程排课和部分资源分配问题都能使用类似框架，但具体约束、目标函数与求解策略需要按问题重新设计。

**边界说明**：程序求出一个满足全部规则的解，不会声称所有题目都有唯一解。对于严重模糊、歪斜、手写数字或部分遮挡的图片，OCR 可能出错，自动填写前应核对识别盘面。目标窗口移动、被遮挡、切换焦点或棋盘画面变化时，程序会停止填写。程序有动画步骤数安全上限，极端欠约束的题目可能触发此上限；触发时会明确报错，不会误报无解。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

建议优先使用清晰截图，确保整个9×9边框完整显示。程序完全在本机处理图片，不会上传用户图片。

## 第三方模型与许可

印刷数字识别使用 [RapidOCR](https://github.com/RapidAI/RapidOCR) 集成的 PP-OCRv6 小型识别模型，通过 ONNX Runtime 在本机运行。相关许可文本见 `licenses/RapidOCR_LICENSE.txt`、`licenses/PaddleOCR_LICENSE.txt` 和 `licenses/ONNXRuntime_LICENSE.txt`。


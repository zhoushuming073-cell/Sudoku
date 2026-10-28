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

在 [Releases](https://github.com/zhoushuming073-cell/Sudoku-Solver/releases/latest) 下载 `SudokuStudio_Portable.exe` 单文件版，或下载 `SudokuStudio_Windows.zip` 文件夹版并解压。单文件版首次启动会释放临时文件，启动稍慢。

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

## 数独求解的运筹学原理

数独本质上是**约束满足问题**（Constraint Satisfaction Problem, CSP）：找到一个满足所有规则的可行解，而不是优化某个分数。项目中的实际求解流程为**确定性约束传播 → MRV 选格 → 深度优先回溯**。下面先给出等价的整数规划模型，再说明代码真正执行的算法；两者不要混为一谈。

### 1. 0-1 整数规划模型

设数字集合为 $D=\{1,2,\ldots,9\}$，行、列编号为 $r,c\in D$。定义二元变量：

$$
x_{r,c,d}=\begin{cases}
1, & \text{if cell }(r,c)\text{ contains }d,\\
0, & \text{otherwise},
\end{cases}
\qquad r,c,d\in D.
$$

共有 $9^3=729$ 个二元变量。对每一种数独规则分别施加约束：

**每格恰好一个数字**（81 条）：

$$
\sum_{d=1}^{9}x_{r,c,d}=1,
\qquad \forall r,c\in D.
$$

**每行的每个数字恰好出现一次**（81 条）：

$$
\sum_{c=1}^{9}x_{r,c,d}=1,
\qquad \forall r,d\in D.
$$

**每列的每个数字恰好出现一次**（81 条）：

$$
\sum_{r=1}^{9}x_{r,c,d}=1,
\qquad \forall c,d\in D.
$$

用 $p,q\in\{0,1,2\}$ 标记九个 $3\times3$ 宫，定义宫内格子集合：

$$
B_{p,q}=\{(r,c):3p+1\le r\le3p+3,\;3q+1\le c\le3q+3\}.
$$

**每宫的每个数字恰好出现一次**（81 条）：

$$
\sum_{(r,c)\in B_{p,q}}x_{r,c,d}=1,
\qquad \forall p,q\in\{0,1,2\},\;d\in D.
$$

若题面已知格子集合为 $G$，且格子 $(r,c)\in G$ 的给定数字为 $g_{r,c}$，则再加入固定条件：

$$
x_{r,c,g_{r,c}}=1,
\qquad \forall(r,c)\in G.
$$

这样就得到 **729 个二元变量、324 条基础等式约束，外加已知数字固定条件**。目标只要求可行性，可以形式化为：

$$
\min 0,\qquad x_{r,c,d}\in\{0,1\},
$$

这是一种用于理解和验证规则的数学表述。**本项目没有调用 MILP（混合整数线性规划）求解器**，而是直接实现 CSP 搜索。

### 2. CSP 表述与候选集

给 81 个格子按行优先编号 $i\in\{0,1,\ldots,80\}$，以 $v_i\in D\cup\{0\}$ 表示格内数字（$0$ 为空格）。27 个约束单元分别是 9 行、9 列和 9 宫，要求每个单元内的非零数字互不重复，最终恰好包含整个 $D$。

记 $P(i)$ 为与格子 $i$ **同行、同列或同宫**的其他格子集合，$U$ 为所有未填格的集合。一个未填格的当前合法候选集定义为：

$$
C_i=D\setminus\{v_j:j\in P(i),\;v_j\ne0\},
\qquad i\in U.
$$

代码中的 `PEERS[i]` 对应 $P(i)$，`candidates(board, i)` 计算 $C_i$。对于标准 $9\times9$ 数独，每个格子恰有 20 个不同的关联格（同行 8 个、同列 8 个，同宫新增 4 个）。

### 3. 约束传播：不猜测的两种推导

`_single()` 反复寻找可以确定的填数，一旦找到一个就写入棋盘并重新计算候选集，直到没有新的确定性结论。

**唯一候选（Naked Single）**：如果某格只剩一个合法数字，必须填它：

$$
C_i=\{d\}\quad\Longrightarrow\quad v_i=d.
$$

**隐藏唯一（Hidden Single）**：令 $u$ 表示某一行、列或宫，若数字 $d$ 尚未在 $u$ 中出现，并且只存在一个未填格可以容纳它，则该格必须填 $d$：

$$
\left|\{i\in u\cap U:d\in C_i\}\right|=1
\quad\Longrightarrow\quad v_{i^*}=d,
$$

其中 $i^*$ 是上述集合的唯一元素。即便 $|C_{i^*}|>1$，这一结论依然成立。

出现以下任一种情况时，当前搜索分支不可行：

- 存在未填格 $i$，满足 $C_i=\varnothing$；
- 某个单元 $u$ 尚缺数字 $d$，却没有任何空格可以填它，即 $\{i\in u\cap U:d\in C_i\}=\varnothing$。

上述规则只做**必然成立的推导**，不会排除任何合法解。请注意：这里只实现唯一候选和隐藏唯一，没有实现裸对、X-Wing 等更高级的人类数独技巧。

### 4. MRV 与动态关联度：决定先试哪里

当传播已经无法继续时，搜索器采用 **MRV（Minimum Remaining Values）**：选择候选数最少的未填格，优先处理约束最紧的变量。

$$
|C_{i^*}|=\min_{i\in U}|C_i|.
$$

若出现平局，则比较与该格共享约束的**其他未填格数**，也就是动态关联度：

$$
\deg_U(i)=|P(i)\cap U|.
$$

定义三元组评分：

$$
s(i)=\bigl(|C_i|,\;-\deg_U(i),\;i\bigr).
$$

选择评分 $s(i)$ 按**字典序最小**的格子 $i^*$，即依次优先：①候选数少；②未填关联格多；③行优先编号小。确定格子后，代码按数字从小到大的顺序试探候选。MRV 和 Degree Heuristic 都只影响**分支遍历顺序**，并不改变合法解集合，也不保证对所有题目都能加速。

### 5. 深度优先回溯与正确性

`solve_board()` 的核心逻辑可概括为：

```text
dfs(board):
    复制当前棋盘
    重复应用唯一候选 / 隐藏唯一，直到无法继续
    若发现矛盾：返回失败
    若所有格子已填满：返回当前解

    按 (候选数升序, 动态关联度降序, 格子编号升序) 选格
    按数字升序枚举该格的每个合法候选值：
        复制棋盘，试填候选数字
        若递归 dfs 成功：返回找到的解
        否则记录回溯，尝试下一数字

    所有候选都失败：返回失败
```

其正确性依赖两个性质：

1. **可靠性（Soundness）**：每一步传播填入的是约束强制的数字，试探只使用当前合法候选值；一旦 81 格全部填满，行、列、宫都没有重复，因而每个单元恰好包含 $1$ 至 $9$。
2. **完备性（Completeness）**：若不受资源上限中断，失败分支只会因真正的约束矛盾被剪除，回溯会枚举选中格子的全部候选。因此，若至少存在一个合法解，最终能找到其中一个；否则搜索穷尽后报告无解。

若初始有重复的已知数字，`validate_board()` 会直接拒绝题面；若搜索中发生不可行分支，记录冲突后继续搜索其他分支。**算法只返回找到的第一个解，并不检测解是否唯一**。

若初始空格数为 $k$，无剪枝时可以用 $9^k$ 作为赋值路径数量的粗略上界；传播和排序通常减少实际搜索，但没有消除指数级最坏情况。为避免 GUI 被异常大的步骤日志占满，`solve_board()` 默认限制为 `max_steps=60000`：达到上限会抛出明确的 `RuntimeError`，**不能将其解释成“无解”**。

### 6. 为什么能播放完整求解过程

每一步都记录 `Step(board, kind, message, cell, digit)`，其中 `board` 是长度为 81 的棋盘快照。事件包括推导、试探、冲突、回溯以及求解完成；因此界面可以向前、向后播放，而不必重新运行搜索。

如果总共记录 $T$ 个事件，单就棋盘快照而言，存储量为 $O(81T)$。这是为可解释性和回放功能付出的空间代价。`SolveResult` 中的 `nodes`、`guesses` 和 `backtracks` 分别统计递归节点数、试填次数和失败试填的回退次数，不应将它们误当成不同算法之间的标准化性能指标。

这种“变量—候选域—约束—传播—搜索”的结构也适用于图着色、排课等问题，但需要重新定义约束与选择策略；本项目使用的是经典 CSP 方法，并非原创优化算法。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

建议优先使用清晰截图，确保整个9×9边框完整显示。程序完全在本机处理图片，不会上传用户图片。

## 第三方模型与许可

印刷数字识别使用 [RapidOCR](https://github.com/RapidAI/RapidOCR) 集成的 PP-OCRv6 小型识别模型，通过 ONNX Runtime 在本机运行。相关许可文本见 `licenses/RapidOCR_LICENSE.txt`、`licenses/PaddleOCR_LICENSE.txt` 和 `licenses/ONNXRuntime_LICENSE.txt`。


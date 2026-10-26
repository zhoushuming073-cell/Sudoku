"""Build a self-contained Windows folder with the OCR runtime."""

from pathlib import Path


project = Path(SPECPATH)
tesseract = Path(r"C:\Program Files\Tesseract-OCR")
if not (tesseract / "tesseract.exe").exists():
    raise SystemExit("Install Tesseract OCR before building Sudoku Studio.")

datas = [
    (str(project / "example_sudoku.png"), "."),
    (str(project / "licenses" / "Tesseract_LICENSE.txt"), "licenses"),
    (str(tesseract / "tessdata" / "eng.traineddata"), "tesseract/tessdata"),
    (str(tesseract / "tesseract.exe"), "tesseract"),
]
datas.extend((str(path), "tesseract") for path in tesseract.glob("*.dll"))

analysis = Analysis(
    [str(project / "sudoku_studio.py")],
    pathex=[str(project)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="SudokuStudio",
    console=False,
)
coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="SudokuStudio",
)

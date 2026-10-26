"""Build a single-file Windows executable with the OCR runtime."""

from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files


project = Path(SPECPATH)
tesseract = Path(r"C:\Program Files\Tesseract-OCR")
if not (tesseract / "tesseract.exe").exists():
    raise SystemExit("Install Tesseract OCR before building Sudoku Studio.")

datas = [
    (str(project / "example_sudoku.png"), "."),
    (str(project / "licenses" / "Tesseract_LICENSE.txt"), "licenses"),
    (str(project / "licenses" / "RapidOCR_LICENSE.txt"), "licenses"),
    (str(project / "licenses" / "PaddleOCR_LICENSE.txt"), "licenses"),
    (str(project / "licenses" / "ONNXRuntime_LICENSE.txt"), "licenses"),
    (str(tesseract / "tessdata" / "eng.traineddata"), "tesseract/tessdata"),
    (str(tesseract / "tesseract.exe"), "tesseract"),
]
datas.extend((str(path), "tesseract") for path in tesseract.glob("*.dll"))
datas.extend(collect_data_files("rapidocr"))

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
    analysis.binaries,
    analysis.datas,
    [],
    name="SudokuStudio_Portable",
    console=False,
    upx=False,
)


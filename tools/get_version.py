"""Print __version__ from main.py (used by build.bat and CI - no quoting tricks in cmd)."""
import pathlib
import re

src = (pathlib.Path(__file__).resolve().parent.parent / "main.py").read_text(encoding="utf-8")
print(re.search(r'^__version__\s*=\s*"([^"]+)"', src, re.M).group(1))

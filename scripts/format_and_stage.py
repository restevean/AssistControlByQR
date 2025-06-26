# scripts/format_and_stage.py
import sys
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> int:
    print(f"Running: {' '.join(cmd)}")
    return subprocess.call(cmd)


# Solo archivos .py
files = [f for f in sys.argv[1:] if Path(f).suffix == ".py"]
if not files:
    print("No hay archivos Python que formatear.")
    sys.exit(0)

ret = run(["poetry", "run", "ruff", "check", "--fix", "--line-length", "120"] + files)
run(["poetry", "run", "ruff", "format", "--line-length", "120"] + files)
run(["git", "add"] + files)
sys.exit(ret)

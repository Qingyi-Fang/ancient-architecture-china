"""PyCharm 一键启动脚本：通过当前解释器启动 Streamlit 应用。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parent
    app_path = project_root / "app.py"

    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path)]
    subprocess.run(cmd, cwd=str(project_root), check=True)


if __name__ == "__main__":
    main()

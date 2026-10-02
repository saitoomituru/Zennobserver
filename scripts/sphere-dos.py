#!/usr/bin/env python3
"""埋め込んだSphereDOSの既存CLIへ委譲する。component取得は行わない。"""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
ATLANTIS = ROOT / ".vendor" / "SphereOS-Atlantis"
VENV = ROOT / ".venv" / "sphere-dos"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("bootstrap", "boot", "status", "doctor"))
    args = parser.parse_args()
    if not (ATLANTIS / "atlantis_cli" / "__main__.py").is_file():
        parser.error("SphereOS-Atlantisをgit submodule update --initで配置してください。")
    if args.command == "bootstrap":
        command = [sys.executable, "-B", "scripts/bootstrap_venv.py", "--venv", str(VENV), "--json"]
    else:
        python = VENV / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if not python.is_file():
            parser.error("先にpython3 scripts/sphere-dos.py bootstrapを実行してください。")
        command = [str(python), "-B", "-m", "atlantis_cli"]
        command += ["doctor", "--json"] if args.command == "doctor" else ["sphere-dos", args.command, "--json"]
    return subprocess.run(command, cwd=ATLANTIS, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())

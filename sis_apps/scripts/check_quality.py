#!/usr/bin/env python3
"""Apply blocking lint/format checks to changed SIS code, without hiding legacy debt."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "sis_apps/frontend-app-sis"


def changed_files(base):
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", "-z", "--diff-filter=ACMR", base, "--", "sis_apps"],
        cwd=ROOT,
    )
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "-z", "sis_apps"], cwd=ROOT
    )
    return sorted(
        {
            ROOT / name.decode()
            for name in (tracked + untracked).split(b"\0")
            if name and (ROOT / name.decode()).is_file()
        }
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("--kind", choices=["python", "frontend", "all"], default="all")
    options = parser.parse_args()
    files = changed_files(options.base)
    python_files = [str(path) for path in files if path.suffix == ".py"]
    js_files = [
        str(path.relative_to(FRONTEND))
        for path in files
        if path.is_relative_to(FRONTEND) and path.suffix in (".js", ".jsx") and path.name != "env.config.js"
    ]
    if python_files and options.kind in ("all", "python"):
        for arguments in (
            ["isort", "--check-only"],
            ["black", "--check", "--line-length", "120"],
            ["flake8", "--max-line-length=120", "--extend-ignore=E203,W503"],
        ):
            subprocess.run([sys.executable, "-m", *arguments, *python_files], cwd=ROOT, check=True)
    if js_files and options.kind in ("all", "frontend"):
        subprocess.run(
            ["npx", "--no-install", "fedx-scripts", "eslint", *js_files],
            cwd=FRONTEND,
            check=True,
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
cli.py — порівнює два STEP-файли (.stp/.step) і генерує HTML-звіт
з деревом елементів, обʼємами, центрами ваги і кольоровим підсвічуванням різниць.

Використання:
    python3 cli.py file_a.stp file_b.stp -o report.html
    python3 cli.py file_a.stp file_b.stp --volume-tol 0.5 --com-tol 0.1
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from i18n import normalize_lang, tr
from step_tree import parse_step
from compare import compare_nodes
from report import render_report


def _non_negative_finite_float(value: str) -> float:
    """Parse a finite non-negative float for tolerance CLI options."""
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite non-negative number")
    return parsed


def main():
    """Parse CLI arguments, compare two STEP trees, and write an HTML report."""
    parser = argparse.ArgumentParser(description="STEP tree comparison")
    parser.add_argument("file_a", help="Baseline STEP file (A)")
    parser.add_argument("file_b", help="Comparison STEP file (B)")
    parser.add_argument("-o", "--output", default="report.html", help="Output HTML report path")
    parser.add_argument("--volume-tol", type=_non_negative_finite_float, default=0.5, help="Volume tolerance, %% (default 0.5%%)")
    parser.add_argument("--com-tol", type=_non_negative_finite_float, default=0.1, help="COM tolerance, mm (default 0.1 mm)")
    parser.add_argument("--lang", choices=["uk", "en", "da"], default="uk", help="UI language")
    parser.add_argument("--json", action="store_true", help="Also print diff tree as JSON to stdout")
    args = parser.parse_args()
    lang = normalize_lang(args.lang)
    status_out = sys.stderr if args.json else sys.stdout

    def status(msg: str) -> None:
        print(msg, file=status_out)

    status(f"{tr(lang, 'cli_reading')} {args.file_a} ...")
    tree_a = parse_step(args.file_a)
    status(f"{tr(lang, 'cli_reading')} {args.file_b} ...")
    tree_b = parse_step(args.file_b)

    status(f"{tr(lang, 'cli_comparing')} ...")
    diff = compare_nodes(tree_a, tree_b, volume_tol_pct=args.volume_tol, com_tol_mm=args.com_tol)

    html_report = render_report(diff, Path(args.file_a).name, Path(args.file_b).name,
                                tree_a=tree_a, tree_b=tree_b, lang=lang)
    Path(args.output).write_text(html_report, encoding="utf-8")
    status(f"{tr(lang, 'cli_saved')} {args.output}")

    if args.json:
        import json
        print(json.dumps(diff.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

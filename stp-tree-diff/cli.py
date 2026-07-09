#!/usr/bin/env python3
"""
cli.py — порівнює два STEP-файли (.stp/.step) і генерує HTML-звіт
з деревом елементів, обʼємами, центрами ваги і кольоровим підсвічуванням різниць.

Використання:
    python3 cli.py file_a.stp file_b.stp -o report.html
    python3 cli.py file_a.stp file_b.stp --volume-tol 0.5 --com-tol 0.1
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from step_tree import parse_step
from compare import compare_nodes
from report import render_report


def main():
    parser = argparse.ArgumentParser(description="Порівняння дерев елементів двох STEP-файлів")
    parser.add_argument("file_a", help="Перший STEP-файл (базовий, A)")
    parser.add_argument("file_b", help="Другий STEP-файл (для порівняння, B)")
    parser.add_argument("-o", "--output", default="report.html", help="Шлях до вихідного HTML-звіту")
    parser.add_argument("--volume-tol", type=float, default=0.5, help="Допуск різниці обʼєму, %% (за замовчуванням 0.5%%)")
    parser.add_argument("--com-tol", type=float, default=0.1, help="Допуск зміщення ЦВ, мм (за замовчуванням 0.1 мм)")
    parser.add_argument("--json", action="store_true", help="Також вивести diff у форматі JSON у stdout")
    args = parser.parse_args()

    print(f"Читаю {args.file_a} ...")
    tree_a = parse_step(args.file_a)
    print(f"Читаю {args.file_b} ...")
    tree_b = parse_step(args.file_b)

    print("Порівнюю дерева ...")
    diff = compare_nodes(tree_a, tree_b, volume_tol_pct=args.volume_tol, com_tol_mm=args.com_tol)

    html_report = render_report(diff, Path(args.file_a).name, Path(args.file_b).name)
    Path(args.output).write_text(html_report, encoding="utf-8")
    print(f"Звіт збережено: {args.output}")

    if args.json:
        import json
        print(json.dumps(diff.to_dict(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

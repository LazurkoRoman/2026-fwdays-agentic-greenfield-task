"""
report.py — рендерить DiffNode-дерево у самодостатній HTML-файл
з кольоровим підсвічуванням статусу кожного вузла.

Кольори:
  match   -> зелений
  changed -> жовтий/жовтогарячий
  added   -> синій
  removed -> червоний
"""

from __future__ import annotations

import html
from compare import DiffNode

COLORS = {
    "match": "#2e7d32",
    "changed": "#e65100",
    "added": "#1565c0",
    "removed": "#c62828",
}

LABELS = {
    "match": "OK",
    "changed": "ЗМІНЕНО",
    "added": "ДОДАНО (лише у B)",
    "removed": "ВИДАЛЕНО (лише у A)",
}


def _fmt(v):
    return "—" if v is None else v


def _render_node(node: DiffNode, depth: int = 0) -> str:
    color = COLORS[node.status]
    label = LABELS[node.status]
    indent = depth * 22

    vol_line = f"V(A)={_fmt(node.volume_a)}  V(B)={_fmt(node.volume_b)}"
    if node.volume_delta_pct is not None:
        vol_line += f"  Δ={node.volume_delta_pct}%"

    com_line = f"COM(A)={_fmt(node.com_a)}  COM(B)={_fmt(node.com_b)}"
    if node.com_delta_mm is not None:
        com_line += f"  |Δ|={node.com_delta_mm} мм"

    icon = "▣" if node.is_assembly else "◆"

    row = f"""
    <div class="node" style="margin-left:{indent}px; border-left: 4px solid {color};">
      <div class="node-header">
        <span class="icon">{icon}</span>
        <span class="name">{html.escape(node.name)}</span>
        <span class="badge" style="background:{color}">{label}</span>
      </div>
      <div class="node-details">
        <div>{html.escape(vol_line)}</div>
        <div>{html.escape(com_line)}</div>
      </div>
    </div>
    """
    children_html = "".join(_render_node(c, depth + 1) for c in node.children)
    return row + children_html


def render_report(root: DiffNode, title_a: str, title_b: str) -> str:
    body = _render_node(root)
    total = _count(root)
    summary = (
        f"Порівняння: <b>{html.escape(title_a)}</b> (A) vs "
        f"<b>{html.escape(title_b)}</b> (B)<br>"
        f"Всього вузлів: {total['total']} · "
        f"<span style='color:{COLORS['match']}'>OK: {total['match']}</span> · "
        f"<span style='color:{COLORS['changed']}'>Змінено: {total['changed']}</span> · "
        f"<span style='color:{COLORS['added']}'>Додано: {total['added']}</span> · "
        f"<span style='color:{COLORS['removed']}'>Видалено: {total['removed']}</span>"
    )

    return f"""<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<title>STP Tree Diff Report</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; background:#0f1115; color:#e8e8e8; padding: 24px; }}
  h1 {{ font-size: 20px; }}
  .summary {{ margin-bottom: 20px; padding: 12px 16px; background:#1b1e26; border-radius: 8px; }}
  .node {{ padding: 6px 10px; margin: 2px 0; background:#171a21; border-radius: 4px; }}
  .node-header {{ display:flex; align-items:center; gap:8px; }}
  .icon {{ opacity: 0.6; }}
  .name {{ font-weight:600; }}
  .badge {{ margin-left:auto; font-size: 11px; padding: 2px 8px; border-radius: 10px; color:#fff; }}
  .node-details {{ font-size: 12px; opacity: 0.75; margin-top: 2px; font-family: monospace; }}
</style>
</head>
<body>
  <h1>Порівняння STEP-дерев</h1>
  <div class="summary">{summary}</div>
  {body}
</body>
</html>"""


def _count(node: DiffNode, acc: dict = None) -> dict:
    if acc is None:
        acc = {"total": 0, "match": 0, "changed": 0, "added": 0, "removed": 0}
    acc["total"] += 1
    acc[node.status] += 1
    for c in node.children:
        _count(c, acc)
    return acc

"""
compare.py

Порівнює два дерева елементів (отримані з step_tree.parse_step) за:
  - обʼємом (volume)
  - центром ваги (center of mass)

Співставлення вузлів відбувається за назвою деталі на кожному рівні дерева
(з урахуванням кількості входжень — Box1, Box1 #2, ...). Якщо назва є в
обох деревах — вузли порівнюються; якщо є лише в одному — позначається як
"додано"/"видалено".

Статус вузла:
  - "match"    — обʼєм і ЦВ співпадають в межах допуску
  - "changed"  — вузол є в обох, але обʼєм і/або ЦВ відрізняються
  - "added"    — є лише у файлі B
  - "removed"  — є лише у файлі A
"""

from __future__ import annotations

import dataclasses
import math
from typing import Optional

from step_tree import Node


@dataclasses.dataclass
class DiffNode:
    name: str
    status: str  # match | changed | added | removed
    is_assembly: bool
    volume_a: Optional[float]
    volume_b: Optional[float]
    volume_delta_pct: Optional[float]
    com_a: Optional[tuple]
    com_b: Optional[tuple]
    com_delta_mm: Optional[float]  # евклідова відстань між ЦВ
    children: list = dataclasses.field(default_factory=list)

    def to_dict(self):
        """Convert a diff node (including children) to a JSON-serializable dict."""
        return {
            "name": self.name,
            "status": self.status,
            "is_assembly": self.is_assembly,
            "volume_a": self.volume_a,
            "volume_b": self.volume_b,
            "volume_delta_pct": self.volume_delta_pct,
            "com_a": self.com_a,
            "com_b": self.com_b,
            "com_delta_mm": self.com_delta_mm,
            "children": [c.to_dict() for c in self.children],
        }


def _com_distance(a: Optional[tuple], b: Optional[tuple]) -> Optional[float]:
    """Return Euclidean distance between two COM tuples, or None when missing."""
    if a is None or b is None:
        return None
    return round(math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))), 4)


def _volume_delta_pct(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Return absolute percentage delta between two volumes."""
    if a is None or b is None:
        return None
    if a == 0:
        return None if b == 0 else 100.0
    return round(abs(b - a) / abs(a) * 100.0, 3)


def compare_nodes(
    node_a: Optional[Node],
    node_b: Optional[Node],
    volume_tol_pct: float = 0.5,
    com_tol_mm: float = 0.1,
) -> DiffNode:
    """Рекурсивно порівнює два вузли (може бути None, якщо вузол відсутній)."""
    if node_a is None and node_b is None:
        raise ValueError("Обидва вузли None — нічого порівнювати")

    if node_a is None:
        # вузол додано у файлі B
        return DiffNode(
            name=node_b.name, status="added", is_assembly=node_b.is_assembly,
            volume_a=None, volume_b=node_b.volume, volume_delta_pct=None,
            com_a=None, com_b=node_b.com, com_delta_mm=None,
            children=[compare_nodes(None, c) for c in node_b.children],
        )
    if node_b is None:
        return DiffNode(
            name=node_a.name, status="removed", is_assembly=node_a.is_assembly,
            volume_a=node_a.volume, volume_b=None, volume_delta_pct=None,
            com_a=node_a.com, com_b=None, com_delta_mm=None,
            children=[compare_nodes(c, None) for c in node_a.children],
        )

    vol_delta = _volume_delta_pct(node_a.volume, node_b.volume)
    com_delta = _com_distance(node_a.com, node_b.com)

    # спочатку порівнюємо дітей (за назвою), потім вирішуємо статус поточного вузла
    children_a = {c.name: c for c in node_a.children}
    children_b = {c.name: c for c in node_b.children}
    all_names = list(dict.fromkeys(list(children_a.keys()) + list(children_b.keys())))

    diff_children = [
        compare_nodes(children_a.get(name), children_b.get(name), volume_tol_pct, com_tol_mm)
        for name in all_names
    ]

    same_node_type = node_a.is_assembly == node_b.is_assembly
    has_required_measurements = vol_delta is not None and com_delta is not None
    within_tolerance = (
        vol_delta is not None
        and vol_delta <= volume_tol_pct
        and com_delta is not None
        and com_delta <= com_tol_mm
    )
    any_child_changed = any(c.status != "match" for c in diff_children)
    status = "match" if (same_node_type and has_required_measurements and within_tolerance and not any_child_changed) else "changed"

    return DiffNode(
        name=node_a.name,
        status=status,
        is_assembly=node_a.is_assembly,
        volume_a=node_a.volume,
        volume_b=node_b.volume,
        volume_delta_pct=vol_delta,
        com_a=node_a.com,
        com_b=node_b.com,
        com_delta_mm=com_delta,
        children=diff_children,
    )

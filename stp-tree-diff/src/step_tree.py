"""
step_tree.py

Читає STEP-файл (AP203/AP214/AP242) через OpenCASCADE XCAF framework,
зберігаючи ІЄРАРХІЮ збірки (assembly tree), а не лише плаский список solid-ів.

Для кожного вузла дерева (деталі або підзбірки) обчислює:
  - назву (з STEP-файлу, якщо є; інакше згенеровану)
  - обʼєм (volume)
  - центр ваги (center of mass, x/y/z)
  - bounding box (додатково, для наочності)

Результат — вкладений список/дерево dataclass Node, який можна серіалізувати в JSON.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Optional

from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.IFSelect import IFSelect_RetDone
from OCP.TDocStd import TDocStd_Document
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool
from OCP.TDF import TDF_LabelSequence, TDF_Label
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDataStd import TDataStd_Name
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.Bnd import Bnd_Box
from OCP.BRepBndLib import BRepBndLib
from OCP.TopoDS import TopoDS_Shape


@dataclasses.dataclass
class Node:
    name: str
    is_assembly: bool
    volume: Optional[float] = None          # мм^3 (одиниці STEP-файлу)
    com: Optional[tuple] = None             # (x, y, z) центр ваги
    bbox: Optional[tuple] = None            # (xmin, ymin, zmin, xmax, ymax, zmax)
    children: list = dataclasses.field(default_factory=list)

    def to_dict(self):
        return {
            "name": self.name,
            "is_assembly": self.is_assembly,
            "volume": self.volume,
            "com": self.com,
            "bbox": self.bbox,
            "children": [c.to_dict() for c in self.children],
        }


def _label_name(label: TDF_Label, fallback: str) -> str:
    name_attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), name_attr):
        return name_attr.Get().ToExtString()
    return fallback


def _shape_props(shape: TopoDS_Shape):
    """Обчислює обʼєм, центр ваги і bounding box для форми (може бути composite)."""
    gprops = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, gprops)
    volume = gprops.Mass()  # для VolumeProperties Mass() == обʼєм
    com_pnt = gprops.CentreOfMass()
    com = (round(com_pnt.X(), 4), round(com_pnt.Y(), 4), round(com_pnt.Z(), 4))

    bbox = Bnd_Box()
    BRepBndLib.Add_s(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    bbox_t = tuple(round(v, 4) for v in (xmin, ymin, zmin, xmax, ymax, zmax))

    return round(volume, 6), com, bbox_t


def _get_components(shape_tool, label):
    seq = TDF_LabelSequence()
    shape_tool.GetComponents_s(label, seq)
    return [seq.Value(i) for i in range(1, seq.Length() + 1)]


def _resolve_referred(shape_tool, comp_label):
    """Компонент (інстанс) -> мітка деталі/підзбірки, на яку він посилається."""
    ref_label = TDF_Label()
    is_ref = shape_tool.GetReferredShape_s(comp_label, ref_label)
    return ref_label if is_ref else comp_label


def _walk(shape_tool, label: TDF_Label, seen_names: dict, shape_label_for_geometry: TDF_Label = None) -> Node:
    """
    label: мітка структури (визначає is_assembly / дітей) — це "referred"/part label.
    shape_label_for_geometry: мітка КОМПОНЕНТА (інстанса), з якої треба брати
        форму для обчислення обʼєму/ЦВ, бо саме вона містить накопичену
        трансформацію (розташування) відносно кореня збірки. Для кореневих
        вільних форм (без батьківського компонента) співпадає з `label`.
    """
    geom_label = shape_label_for_geometry if shape_label_for_geometry is not None else label

    name_fallback = f"unnamed_{label.Tag()}"
    name = _label_name(label, name_fallback)
    count = seen_names.get(name, 0)
    seen_names[name] = count + 1
    display_name = name if count == 0 else f"{name} #{count + 1}"

    is_assembly_flag = shape_tool.IsAssembly_s(label)
    node = Node(name=display_name, is_assembly=bool(is_assembly_flag))

    if is_assembly_flag:
        for comp_label in _get_components(shape_tool, label):
            ref_label = _resolve_referred(shape_tool, comp_label)
            child_node = _walk(shape_tool, ref_label, seen_names, shape_label_for_geometry=comp_label)
            node.children.append(child_node)
        total_vol = sum(c.volume for c in node.children if c.volume)
        if total_vol:
            wx = sum((c.com[0] * c.volume) for c in node.children if c.volume) / total_vol
            wy = sum((c.com[1] * c.volume) for c in node.children if c.volume) / total_vol
            wz = sum((c.com[2] * c.volume) for c in node.children if c.volume) / total_vol
            node.volume = round(total_vol, 6)
            node.com = (round(wx, 4), round(wy, 4), round(wz, 4))
    else:
        shape = shape_tool.GetShape_s(geom_label)
        if shape is not None and not shape.IsNull():
            volume, com, bbox = _shape_props(shape)
            node.volume = volume
            node.com = com
            node.bbox = bbox

    return node


def parse_step(path: str) -> Node:
    """Парсить STEP-файл і повертає корінь дерева елементів."""
    path = str(Path(path).resolve())

    app = XCAFApp_Application.GetApplication_s()
    doc = TDocStd_Document(TCollection_ExtendedString("stp-tree-doc"))
    app.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), doc)

    reader = STEPCAFControl_Reader()
    reader.SetNameMode(True)
    status = reader.ReadFile(path)
    if status != IFSelect_RetDone:
        raise RuntimeError(f"Не вдалося прочитати STEP-файл: {path}")
    reader.Transfer(doc)

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())

    free_labels = TDF_LabelSequence()
    getter = shape_tool.GetFreeShapes_s if hasattr(shape_tool, "GetFreeShapes_s") else shape_tool.GetFreeShapes
    getter(free_labels)

    seen_names: dict = {}
    roots = [_walk(shape_tool, free_labels.Value(i), seen_names) for i in range(1, free_labels.Length() + 1)]

    if len(roots) == 1:
        return roots[0]

    # якщо кілька незалежних верхніх тіл — обгортаємо у віртуальний корінь
    root = Node(name=Path(path).stem, is_assembly=True, children=roots)
    total_vol = sum(c.volume for c in roots if c.volume)
    if total_vol:
        wx = sum((c.com[0] * c.volume) for c in roots if c.volume) / total_vol
        wy = sum((c.com[1] * c.volume) for c in roots if c.volume) / total_vol
        wz = sum((c.com[2] * c.volume) for c in roots if c.volume) / total_vol
        root.volume = round(total_vol, 6)
        root.com = (round(wx, 4), round(wy, 4), round(wz, 4))
    return root


if __name__ == "__main__":
    import sys
    tree = parse_step(sys.argv[1])
    print(json.dumps(tree.to_dict(), indent=2, ensure_ascii=False))

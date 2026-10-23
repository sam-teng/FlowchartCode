from __future__ import annotations

import math
import tkinter as tk
from typing import Optional

from flowchart_core import Connection, ConnectionType, Element, ElementType, Flowchart


SHAPE_DEFAULTS = {
    ElementType.PROCESS: ("rectangle", "lightblue"),
    ElementType.DECISION: ("diamond", "lightgreen"),
    ElementType.LOOP: ("oval", "lightyellow"),
    ElementType.START_END: ("oval", "pink"),
    ElementType.INPUT: ("input", "lightgray"),
    ElementType.OUTPUT: ("output", "lightcoral"),
    ElementType.FUNCTION: ("rectangle", "purple"),
    ElementType.CLASS: ("rectangle", "lightcyan"),
    ElementType.COMMENT: ("text", "gray"),
    ElementType.THREAD: ("rectangle", "#B7A6E8"),
    ElementType.SYNC_EVENT: ("oval", "#FFE08A"),
    ElementType.SYNC_LOCK: ("rectangle", "#9CCFE7"),
    ElementType.SYNC_SEMAPHORE: ("rectangle", "#A3BE8C"),
    ElementType.SYNC_BARRIER: ("diamond", "#EBCB8B"),
    ElementType.EXTERNAL: ("input", "#D8B4FE"),
}

SIZE_DEFAULTS = {
    ElementType.PROCESS: (50, 20),
    ElementType.DECISION: (50, 30),
    ElementType.LOOP: (40, 20),
    ElementType.START_END: (40, 20),
    ElementType.INPUT: (50, 20),
    ElementType.OUTPUT: (50, 20),
    ElementType.FUNCTION: (50, 20),
    ElementType.CLASS: (60, 30),
    ElementType.COMMENT: (0, 0),
    ElementType.THREAD: (60, 25),
    ElementType.SYNC_EVENT: (45, 20),
    ElementType.SYNC_LOCK: (50, 20),
    ElementType.SYNC_SEMAPHORE: (50, 20),
    ElementType.SYNC_BARRIER: (45, 25),
    ElementType.EXTERNAL: (55, 20),
}

CONNECTION_COLORS = {
    ConnectionType.BODY: "#5E81AC",
    ConnectionType.EXIT: "#BF616A",
    ConnectionType.CALL: "#A3BE8C",
}


class CanvasView:
    def __init__(self, parent, title: str = "", is_subflowchart: bool = False):
        self.parent = parent
        self.is_subflowchart = is_subflowchart
        self.canvas = tk.Canvas(parent, bg="white", width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        if title and not is_subflowchart:
            self.canvas.create_text(
                10, 10, text=title, anchor="nw", font=("Helvetica", 12, "bold")
            )
        self.flowchart: Optional[Flowchart] = None
        self.element_items: dict[str, dict] = {}
        self.connection_items: dict[tuple, dict] = {}
        self.temp_line = None
        self._fills: dict[str, str] = {}
        self.shape_overrides: dict[str, tuple] = {}
        self._ports_visible = False
        self._port_items: dict[str, list] = {}
        self._selected_id: Optional[str] = None
        self._selection_box = None
        self._temp_color = "#5E81AC"

    def register_shape(self, type_name: str, shape_kind: str, color: str) -> None:
        self.shape_overrides[type_name] = (shape_kind, color)

    def shape_for(self, type_name: str) -> tuple:
        if type_name in self.shape_overrides:
            return self.shape_overrides[type_name]
        return SHAPE_DEFAULTS.get(type_name, ("rectangle", "#dddddd"))

    def size_for(self, type_name: str) -> tuple:
        return SIZE_DEFAULTS.get(type_name, (50, 20))

    def attach(self, flowchart: Flowchart) -> None:
        self.flowchart = flowchart
        self.draw_all()

    def clear(self) -> None:
        self.canvas.delete("all")
        self.element_items.clear()
        self.connection_items.clear()
        self.temp_line = None
        self._fills.clear()
        self._port_items.clear()
        self._selected_id = None
        self._selection_box = None

    def draw_all(self) -> None:
        self.clear()
        if self.flowchart is None:
            return
        for element in self.flowchart.elements:
            self.draw_element(element)
        for conn in self.flowchart.connections:
            self.draw_connection(conn)
        if self._ports_visible:
            for element in self.flowchart.elements:
                self.draw_ports(element)

    def _shape_coords(self, element: Element) -> list:
        kind, _color = self.shape_for(element.type)
        x, y = element.x, element.y
        hw, hh = self.size_for(element.type)
        if kind == "rectangle":
            return [x - hw, y - hh, x + hw, y + hh]
        if kind == "oval":
            return [x - hw, y - hh, x + hw, y + hh]
        if kind == "diamond":
            return [x, y - hh, x + hw, y, x, y + hh, x - hw, y]
        if kind == "input":
            return [x - hw, y - hh, x + hw, y - hh, x + hw - 10, y + hh, x - hw + 10, y + hh]
        if kind == "output":
            return [x - hw + 10, y - hh, x + hw - 10, y - hh, x + hw, y + hh, x - hw, y + hh]
        return [x - hw, y - hh, x + hw, y + hh]

    def draw_element(self, element: Element) -> None:
        kind, color = self.shape_for(element.type)
        coords = self._shape_coords(element)
        if kind == "text":
            shape_id = self.canvas.create_text(
                element.x, element.y, text="// Comment",
                font=("Arial", 8), fill=color,
            )
        else:
            create = {
                "rectangle": self.canvas.create_rectangle,
                "oval": self.canvas.create_oval,
                "diamond": self.canvas.create_polygon,
                "input": self.canvas.create_polygon,
                "output": self.canvas.create_polygon,
            }.get(kind, self.canvas.create_rectangle)
            shape_id = create(*coords, fill=color)
        label = self._truncate(element.label_text())
        label_id = self.canvas.create_text(
            element.x, element.y, text=label, font=("Arial", 8)
        )
        self.element_items[element.id] = {"shape": shape_id, "label": label_id}
        if self._ports_visible:
            self.draw_ports(element)

    def draw_connection(self, conn: Connection) -> None:
        source = self.flowchart.element_by_id(conn.source_id)
        target = self.flowchart.element_by_id(conn.target_id)
        if source is None or target is None:
            return
        color = CONNECTION_COLORS.get(conn.type, "black")
        start = self._edge_point(source, target.x, target.y)
        end = self._edge_point(target, source.x, source.y)
        line_id = self.canvas.create_line(
            start[0], start[1], end[0], end[1],
            arrow=tk.LAST, fill=color, tags="connection",
        )
        label_id = self.canvas.create_text(
            (source.x + target.x) / 2, (source.y + target.y) / 2,
            text=self.connection_label(conn), font=("Arial", 8),
        )
        key = self.connection_key(conn)
        self.connection_items[key] = {"line": line_id, "label": label_id}

    def _edge_point(self, element: Element, tx: float, ty: float) -> tuple:
        x, y = element.x, element.y
        hw, hh = self.size_for(element.type)
        if hw <= 0 and hh <= 0:
            return x, y
        dx, dy = tx - x, ty - y
        if dx == 0 and dy == 0:
            return x, y
        scale_x = (hw / abs(dx)) if dx else float("inf")
        scale_y = (hh / abs(dy)) if dy else float("inf")
        t = min(scale_x, scale_y)
        return x + dx * t, y + dy * t

    # ---------- connection ports ----------

    def set_ports_visible(self, visible: bool) -> None:
        visible = bool(visible)
        if visible == self._ports_visible:
            return
        self._ports_visible = visible
        if visible:
            if self.flowchart is not None:
                for element in self.flowchart.elements:
                    self.draw_ports(element)
        else:
            for item_ids in self._port_items.values():
                for pid in item_ids:
                    self.canvas.delete(pid)
            self._port_items.clear()

    def port_positions(self, element: Element) -> list:
        hw, hh = self.size_for(element.type)
        if hw <= 0 and hh <= 0:
            return []
        x, y = element.x, element.y
        return [
            (x - hw, y), (x + hw, y),
            (x, y - hh), (x, y + hh),
        ]

    def draw_ports(self, element: Element) -> None:
        self.remove_ports(element.id)
        positions = self.port_positions(element)
        if not positions:
            return
        ids = []
        for px, py in positions:
            pid = self.canvas.create_oval(
                px - 4, py - 4, px + 4, py + 4,
                fill="#5E81AC", outline="white", width=1, tags="port",
            )
            ids.append(pid)
        if ids:
            self._port_items[element.id] = ids

    def remove_ports(self, element_id: str) -> None:
        for pid in self._port_items.pop(element_id, []):
            self.canvas.delete(pid)

    def find_port_at(self, x: int, y: int, tolerance: int = 8):
        if not self._ports_visible or self.flowchart is None:
            return None
        for element in self.flowchart.elements:
            for px, py in self.port_positions(element):
                if math.hypot(x - px, y - py) <= tolerance:
                    return element
        return None

    def _redraw_ports_for(self, element: Element) -> None:
        if self._ports_visible:
            self.draw_ports(element)

    # ---------- selection highlight ----------

    def set_selected(self, element_id: Optional[str]) -> None:
        if self._selection_box is not None:
            self.canvas.delete(self._selection_box)
            self._selection_box = None
        self._selected_id = element_id
        if element_id is None or self.flowchart is None:
            return
        element = self.flowchart.element_by_id(element_id)
        if element is None:
            return
        hw, hh = self.size_for(element.type)
        if hw <= 0 and hh <= 0:
            return
        self._selection_box = self.canvas.create_rectangle(
            element.x - hw - 4, element.y - hh - 4,
            element.x + hw + 4, element.y + hh + 4,
            outline="#EBCB8B", width=2, dash=(4, 3),
        )

    def clear_selected(self) -> None:
        self.set_selected(None)

    @staticmethod
    def connection_key(conn: Connection) -> tuple:
        return (conn.source_id, conn.target_id, conn.type)

    @staticmethod
    def connection_label(conn: Connection) -> str:
        if conn.type == ConnectionType.BODY:
            return f"Body ({conn.priority})"
        return conn.type

    @staticmethod
    def _truncate(text: str, limit: int = 24) -> str:
        text = text or ""
        return text[:limit] + "..." if len(text) > limit else text

    def update_label(self, element: Element) -> None:
        items = self.element_items.get(element.id)
        if not items:
            return
        self.canvas.itemconfig(
            items["label"], text=self._truncate(element.label_text())
        )

    def move_element_visual(self, element: Element) -> None:
        items = self.element_items.get(element.id)
        if items:
            coords = self._shape_coords(element)
            kind, _ = self.shape_for(element.type)
            if kind == "text":
                self.canvas.coords(items["shape"], element.x, element.y)
            else:
                self.canvas.coords(items["shape"], *coords)
            self.canvas.coords(items["label"], element.x, element.y)
        self._redraw_ports_for(element)
        if self._selected_id == element.id:
            self.set_selected(element.id)
        if self.flowchart is None:
            return
        for conn in self.flowchart.connections:
            if conn.source_id == element.id or conn.target_id == element.id:
                self.update_connection_visual(conn)

    def update_connection_visual(self, conn: Connection) -> None:
        key = self.connection_key(conn)
        items = self.connection_items.get(key)
        source = self.flowchart.element_by_id(conn.source_id) if self.flowchart else None
        target = self.flowchart.element_by_id(conn.target_id) if self.flowchart else None
        if not items or source is None or target is None:
            return
        start = self._edge_point(source, target.x, target.y)
        end = self._edge_point(target, source.x, source.y)
        self.canvas.coords(items["line"], start[0], start[1], end[0], end[1])
        self.canvas.coords(
            items["label"], (source.x + target.x) / 2, (source.y + target.y) / 2
        )

    def remove_connection_visual(self, conn: Connection) -> None:
        items = self.connection_items.pop(self.connection_key(conn), None)
        if items:
            self.canvas.delete(items["line"])
            self.canvas.delete(items["label"])

    def remove_element_visual(self, element_id: str) -> None:
        items = self.element_items.pop(element_id, None)
        if items:
            self.canvas.delete(items["shape"])
            self.canvas.delete(items["label"])
        self.remove_ports(element_id)
        if self._selected_id == element_id:
            self.clear_selected()

    def set_fill(self, element_id: str, color: str) -> None:
        items = self.element_items.get(element_id)
        if not items:
            return
        try:
            current = self.canvas.itemcget(items["shape"], "fill")
        except tk.TclError:
            return
        if element_id not in self._fills:
            self._fills[element_id] = current
        self.canvas.itemconfig(items["shape"], fill=color)

    def restore_fill(self, element_id: str) -> None:
        items = self.element_items.get(element_id)
        original = self._fills.pop(element_id, None)
        if items and original is not None:
            try:
                self.canvas.itemconfig(items["shape"], fill=original)
            except tk.TclError:
                pass

    def set_connection_highlight(self, conn: Connection, color: str = "yellow") -> None:
        items = self.connection_items.get(self.connection_key(conn))
        if items:
            self.canvas.itemconfig(items["line"], fill=color, width=2)

    def restore_connection(self, conn: Connection) -> None:
        items = self.connection_items.get(self.connection_key(conn))
        if items:
            color = CONNECTION_COLORS.get(conn.type, "black")
            self.canvas.itemconfig(items["line"], fill=color, width=1)

    def find_element_at(self, x: int, y: int, tolerance: int = 25) -> Optional[Element]:
        if self.flowchart is None:
            return None
        best = None
        best_dist = tolerance
        for element in self.flowchart.elements:
            hw, hh = self.size_for(element.type)
            dx = max(abs(x - element.x) - hw, 0)
            dy = max(abs(y - element.y) - hh, 0)
            dist = math.hypot(dx, dy)
            if dist <= best_dist:
                best_dist = dist
                best = element
        if best is None:
            for element in self.flowchart.elements:
                if abs(x - element.x) <= tolerance and abs(y - element.y) <= tolerance:
                    return element
        return best

    def find_connection_at(self, x: int, y: int, tolerance: int = 20) -> Optional[Connection]:
        if self.flowchart is None:
            return None
        for conn in self.flowchart.connections:
            source = self.flowchart.element_by_id(conn.source_id)
            target = self.flowchart.element_by_id(conn.target_id)
            if source is None or target is None:
                continue
            dist = _point_segment_distance(
                x, y, source.x, source.y, target.x, target.y
            )
            if dist <= tolerance:
                return conn
        return None

    def start_temp_line(self, x: int, y: int, color: Optional[str] = None) -> None:
        self.end_temp_line()
        self._temp_color = color or "#5E81AC"
        self.temp_line = self.canvas.create_line(
            x, y, x, y, arrow=tk.LAST, dash=(4, 2), fill=self._temp_color
        )

    def update_temp_line(self, x: int, y: int) -> None:
        if self.temp_line is None:
            return
        coords = self.canvas.coords(self.temp_line)
        if len(coords) >= 2:
            self.canvas.coords(self.temp_line, coords[0], coords[1], x, y)

    def end_temp_line(self) -> None:
        if self.temp_line is not None:
            self.canvas.delete(self.temp_line)
            self.temp_line = None

    def flash_error(self, element_id: str, duration_ms: int, root) -> None:
        self.set_fill(element_id, "red")
        root.after(duration_ms, lambda: self.restore_fill(element_id))


def _point_segment_distance(px, py, x1, y1, x2, y2) -> float:
    length_sq = (x2 - x1) ** 2 + (y2 - y1) ** 2
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / length_sq))
    proj_x = x1 + t * (x2 - x1)
    proj_y = y1 + t * (y2 - y1)
    return math.hypot(px - proj_x, py - proj_y)

"""
panel_builder.py
----------------
Pannello laterale organizzato a schede (TabControl) per evitare
ogni sovrapposizione dei widget.

Layout:
  ┌──────────────────────────────────┐
  │  Frame3D Manager                 │
  │  [Undo]  [Redo]                  │
  ├──────┬────────┬────────┬─────────┤
  │Frame │ Nastri │  Tool  │  I/O    │
  ├──────┴────────┴────────┴─────────┤
  │  (contenuto della scheda attiva) │
  │                                  │
  └──────────────────────────────────┘
  │  Status:                         │
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, TYPE_CHECKING

import open3d.visualization.gui as gui

from frame import Frame
from logger import get_logger

if TYPE_CHECKING:
    from frame_tree import FrameTree

log = get_logger("panel_builder")

PANEL_WIDTH_EM = 30


class PanelBuilder:
    """Pannello laterale con 4 tab: Frame, Nastri, Strumenti, I/O."""

    def __init__(self) -> None:
        # ── Frame ──
        self.panel: Optional[gui.Vert] = None
        self.tree_widget: Optional[gui.TreeView] = None
        self.edit_name: Optional[gui.TextEdit] = None
        self.combo_parent: Optional[gui.Combobox] = None
        self.ne_tx: Optional[gui.NumberEdit] = None
        self.ne_ty: Optional[gui.NumberEdit] = None
        self.ne_tz: Optional[gui.NumberEdit] = None
        self.ne_roll: Optional[gui.NumberEdit] = None
        self.ne_pitch: Optional[gui.NumberEdit] = None
        self.ne_yaw: Optional[gui.NumberEdit] = None
        self.lbl_T: Optional[gui.Label] = None
        self.lbl_status: Optional[gui.Label] = None
        self.btn_undo: Optional[gui.Button] = None
        self.btn_redo: Optional[gui.Button] = None
        self.btn_rename: Optional[gui.Button] = None
        self.btn_add: Optional[gui.Button] = None
        self.btn_remove: Optional[gui.Button] = None
        self.btn_apply: Optional[gui.Button] = None
        self.btn_copy: Optional[gui.Button] = None
        self.btn_paste: Optional[gui.Button] = None

        # ── Nastri ──
        self.ribbon_list: Optional[gui.ListView] = None
        self.btn_add_ribbon: Optional[gui.Button] = None
        self.btn_remove_ribbon: Optional[gui.Button] = None
        self.ribbon_edit_name: Optional[gui.TextEdit] = None
        self.ribbon_combo_parent: Optional[gui.Combobox] = None
        self.ne_r_width: Optional[gui.NumberEdit] = None
        self.ne_r_length: Optional[gui.NumberEdit] = None
        self.ne_r_height: Optional[gui.NumberEdit] = None
        self.ne_r_tx: Optional[gui.NumberEdit] = None
        self.ne_r_ty: Optional[gui.NumberEdit] = None
        self.ne_r_tz: Optional[gui.NumberEdit] = None
        self.ne_r_roll: Optional[gui.NumberEdit] = None
        self.ne_r_pitch: Optional[gui.NumberEdit] = None
        self.ne_r_yaw: Optional[gui.NumberEdit] = None
        self.ne_r_red: Optional[gui.NumberEdit] = None
        self.ne_r_green: Optional[gui.NumberEdit] = None
        self.ne_r_blue: Optional[gui.NumberEdit] = None
        self.btn_apply_ribbon: Optional[gui.Button] = None

        # ── Strumenti ──
        self.combo_dist_a: Optional[gui.Combobox] = None
        self.combo_dist_b: Optional[gui.Combobox] = None
        self.btn_measure: Optional[gui.Button] = None
        self.lbl_distance: Optional[gui.Label] = None
        self.btn_screenshot: Optional[gui.Button] = None
        self.btn_import_mesh: Optional[gui.Button] = None

        # ── I/O ──
        self._btn_save_json: Optional[gui.Button] = None
        self._btn_load_json: Optional[gui.Button] = None
        self._btn_export_urdf: Optional[gui.Button] = None
        self._btn_import_urdf: Optional[gui.Button] = None
        self._btn_export_csv: Optional[gui.Button] = None
        self._btn_import_csv: Optional[gui.Button] = None
        self._btn_export_yaml: Optional[gui.Button] = None
        self._btn_import_yaml: Optional[gui.Button] = None
        self._btn_export_dh: Optional[gui.Button] = None

        self._tree_item_ids: Dict[str, int] = {}
        self._em: float = 14.0

    # ==================================================================
    # Build
    # ==================================================================

    def build(self, em: float) -> gui.Vert:
        """Costruisce il pannello con TabControl."""
        self._em = em
        sp = int(0.3 * em)
        m = gui.Margins(int(0.4 * em))

        # Container principale
        self.panel = gui.Vert(sp, m)

        # Titolo
        self.panel.add_child(gui.Label("Frame3D Manager"))

        # Undo / Redo
        row_ur = gui.Horiz(sp)
        self.btn_undo = gui.Button("Undo")
        self.btn_redo = gui.Button("Redo")
        self.btn_undo.enabled = False
        self.btn_redo.enabled = False
        row_ur.add_child(self.btn_undo)
        row_ur.add_child(self.btn_redo)
        self.panel.add_child(row_ur)

        # ── TabControl ──
        tabs = gui.TabControl()

        tabs.add_tab("Frame", self._build_tab_frame())
        tabs.add_tab("Nastri", self._build_tab_ribbon())
        tabs.add_tab("Tool", self._build_tab_tools())
        tabs.add_tab("I/O", self._build_tab_io())

        self.panel.add_child(tabs)

        # Status
        self.lbl_status = gui.Label("")
        self.panel.add_child(self.lbl_status)

        return self.panel

    # ==================================================================
    # Tab 1: Frame
    # ==================================================================

    def _build_tab_frame(self) -> gui.Widget:
        em = self._em
        sp = int(0.3 * em)
        tab = gui.ScrollableVert(sp, gui.Margins(int(0.3 * em)))

        # TreeView
        tab.add_child(gui.Label("Struttura:"))
        self.tree_widget = gui.TreeView()
        tab.add_child(self.tree_widget)

        # Pulsanti
        row = gui.Horiz(sp)
        self.btn_add = gui.Button("Nuovo")
        self.btn_remove = gui.Button("Rimuovi")
        self.btn_copy = gui.Button("Copia")
        self.btn_paste = gui.Button("Incolla")
        row.add_child(self.btn_add)
        row.add_child(self.btn_remove)
        row.add_child(self.btn_copy)
        row.add_child(self.btn_paste)
        tab.add_child(row)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Modifica Frame:"))

        # Nome + Rinomina
        r_name = gui.Horiz(sp)
        r_name.add_child(gui.Label("Nome"))
        self.edit_name = gui.TextEdit()
        r_name.add_child(self.edit_name)
        self.btn_rename = gui.Button("Rinomina")
        r_name.add_child(self.btn_rename)
        tab.add_child(r_name)

        # Parent
        r_parent = gui.Horiz(sp)
        r_parent.add_child(gui.Label("Parent"))
        self.combo_parent = gui.Combobox()
        r_parent.add_child(self.combo_parent)
        tab.add_child(r_parent)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Traslazione (m):"))
        self.ne_tx = self._num(tab, "X", 0.0)
        self.ne_ty = self._num(tab, "Y", 0.0)
        self.ne_tz = self._num(tab, "Z", 0.0)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Rotazione Euler XYZ (deg):"))
        self.ne_roll = self._num(tab, "Roll", 0.0)
        self.ne_pitch = self._num(tab, "Pitch", 0.0)
        self.ne_yaw = self._num(tab, "Yaw", 0.0)

        tab.add_child(gui.Label(""))
        self.btn_apply = gui.Button("Applica Trasformazione")
        tab.add_child(self.btn_apply)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("T Mondo 4x4:"))
        self.lbl_T = gui.Label("( seleziona un frame )")
        tab.add_child(self.lbl_T)

        return tab

    # ==================================================================
    # Tab 2: Nastri
    # ==================================================================

    def _build_tab_ribbon(self) -> gui.Widget:
        em = self._em
        sp = int(0.3 * em)
        tab = gui.ScrollableVert(sp, gui.Margins(int(0.3 * em)))

        tab.add_child(gui.Label("Lista Nastri:"))
        self.ribbon_list = gui.ListView()
        tab.add_child(self.ribbon_list)

        row = gui.Horiz(sp)
        self.btn_add_ribbon = gui.Button("Nuovo Nastro")
        self.btn_remove_ribbon = gui.Button("Rimuovi")
        row.add_child(self.btn_add_ribbon)
        row.add_child(self.btn_remove_ribbon)
        tab.add_child(row)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Modifica Nastro:"))

        r_n = gui.Horiz(sp)
        r_n.add_child(gui.Label("Nome"))
        self.ribbon_edit_name = gui.TextEdit()
        r_n.add_child(self.ribbon_edit_name)
        tab.add_child(r_n)

        r_p = gui.Horiz(sp)
        r_p.add_child(gui.Label("Frame"))
        self.ribbon_combo_parent = gui.Combobox()
        r_p.add_child(self.ribbon_combo_parent)
        tab.add_child(r_p)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Dimensioni (m):"))
        self.ne_r_width = self._num(tab, "Larghezza", 1.0, 3)
        self.ne_r_length = self._num(tab, "Lunghezza", 2.0, 3)
        self.ne_r_height = self._num(tab, "Altezza", 0.05, 4)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Offset posizione (m):"))
        self.ne_r_tx = self._num(tab, "X", 0.0)
        self.ne_r_ty = self._num(tab, "Y", 0.0)
        self.ne_r_tz = self._num(tab, "Z", 0.0)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Rotazione (deg):"))
        self.ne_r_roll = self._num(tab, "Roll", 0.0)
        self.ne_r_pitch = self._num(tab, "Pitch", 0.0)
        self.ne_r_yaw = self._num(tab, "Yaw", 0.0)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Colore RGB (0-1):"))
        self.ne_r_red = self._num(tab, "R", 0.60, 2)
        self.ne_r_green = self._num(tab, "G", 0.60, 2)
        self.ne_r_blue = self._num(tab, "B", 0.60, 2)

        tab.add_child(gui.Label(""))
        self.btn_apply_ribbon = gui.Button("Applica Nastro")
        tab.add_child(self.btn_apply_ribbon)

        return tab

    # ==================================================================
    # Tab 3: Strumenti
    # ==================================================================

    def _build_tab_tools(self) -> gui.Widget:
        em = self._em
        sp = int(0.3 * em)
        tab = gui.Vert(sp, gui.Margins(int(0.3 * em)))

        tab.add_child(gui.Label("Distanza tra frame:"))
        r_dist = gui.Horiz(sp)
        self.combo_dist_a = gui.Combobox()
        self.combo_dist_b = gui.Combobox()
        self.btn_measure = gui.Button("Misura")
        r_dist.add_child(self.combo_dist_a)
        r_dist.add_child(self.combo_dist_b)
        r_dist.add_child(self.btn_measure)
        tab.add_child(r_dist)

        self.lbl_distance = gui.Label("---")
        tab.add_child(self.lbl_distance)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Mesh 3D:"))
        self.btn_import_mesh = gui.Button("Importa Mesh (.stl/.obj)")
        tab.add_child(self.btn_import_mesh)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("Cattura:"))
        self.btn_screenshot = gui.Button("Salva Screenshot (.png)")
        tab.add_child(self.btn_screenshot)

        return tab

    # ==================================================================
    # Tab 4: I/O
    # ==================================================================

    def _build_tab_io(self) -> gui.Widget:
        sp = int(0.3 * self._em)
        tab = gui.Vert(sp, gui.Margins(int(0.3 * self._em)))

        tab.add_child(gui.Label("JSON:"))
        r1 = gui.Horiz(sp)
        self._btn_save_json = gui.Button("Salva JSON")
        self._btn_load_json = gui.Button("Carica JSON")
        r1.add_child(self._btn_save_json)
        r1.add_child(self._btn_load_json)
        tab.add_child(r1)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("URDF:"))
        r2 = gui.Horiz(sp)
        self._btn_export_urdf = gui.Button("Export URDF")
        self._btn_import_urdf = gui.Button("Import URDF")
        r2.add_child(self._btn_export_urdf)
        r2.add_child(self._btn_import_urdf)
        tab.add_child(r2)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("CSV:"))
        r3 = gui.Horiz(sp)
        self._btn_export_csv = gui.Button("Export CSV")
        self._btn_import_csv = gui.Button("Import CSV")
        r3.add_child(self._btn_export_csv)
        r3.add_child(self._btn_import_csv)
        tab.add_child(r3)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("YAML:"))
        r4 = gui.Horiz(sp)
        self._btn_export_yaml = gui.Button("Export YAML")
        self._btn_import_yaml = gui.Button("Import YAML")
        r4.add_child(self._btn_export_yaml)
        r4.add_child(self._btn_import_yaml)
        tab.add_child(r4)

        tab.add_child(gui.Label(""))
        tab.add_child(gui.Label("DH Parameters:"))
        self._btn_export_dh = gui.Button("Export DH Params")
        tab.add_child(self._btn_export_dh)

        return tab

    # ==================================================================
    # Helper
    # ==================================================================

    def _num(
        self, parent: gui.Widget, label: str, default: float,
        precision: int = 4,
    ) -> gui.NumberEdit:
        sp = int(0.3 * self._em)
        row = gui.Horiz(sp)
        row.add_child(gui.Label(f"  {label}"))
        ne = gui.NumberEdit(gui.NumberEdit.DOUBLE)
        ne.double_value = default
        ne.decimal_precision = precision
        row.add_child(ne)
        parent.add_child(row)
        return ne

    # ==================================================================
    # TreeView
    # ==================================================================

    def refresh_tree(self, tree: "FrameTree") -> None:
        self.tree_widget.clear()
        self._tree_item_ids.clear()
        self._add_tree_node(tree, "world", parent_id=0)

        self.combo_parent.clear_items()
        for n in tree.get_all_names():
            self.combo_parent.add_item(n)

        self.ribbon_combo_parent.clear_items()
        for n in tree.get_all_names():
            self.ribbon_combo_parent.add_item(n)

        self.combo_dist_a.clear_items()
        self.combo_dist_b.clear_items()
        for n in tree.get_all_names():
            self.combo_dist_a.add_item(n)
            self.combo_dist_b.add_item(n)

    def refresh_ribbon_list(self, tree: "FrameTree") -> None:
        names = tree.get_ribbon_names()
        self.ribbon_list.set_items(names)

    def _add_tree_node(
        self, tree: "FrameTree", name: str, parent_id: int
    ) -> None:
        if parent_id == 0:
            item_id = self.tree_widget.add_item(
                self.tree_widget.get_root_item(), gui.Label(name)
            )
        else:
            item_id = self.tree_widget.add_item(parent_id, gui.Label(name))
        self._tree_item_ids[name] = item_id
        for child_name in tree.get_children(name):
            self._add_tree_node(tree, child_name, item_id)

    def get_name_from_tree_item(self, item_id: int) -> Optional[str]:
        for name, tid in self._tree_item_ids.items():
            if tid == item_id:
                return name
        return None

    # ==================================================================
    # Callback wiring
    # ==================================================================

    def wire_callbacks(
        self,
        on_tree_selected: Callable,
        on_add: Callable,
        on_remove: Callable,
        on_rename: Callable,
        on_apply: Callable,
        on_combo_parent: Callable,
        on_undo: Callable,
        on_redo: Callable,
        on_copy: Callable,
        on_paste: Callable,
        on_save_json: Callable,
        on_load_json: Callable,
        on_export_urdf: Callable,
        on_import_urdf: Callable,
        on_export_csv: Callable,
        on_import_csv: Callable,
        on_export_yaml: Callable,
        on_import_yaml: Callable,
        on_export_dh: Callable,
        on_add_ribbon: Callable,
        on_remove_ribbon: Callable,
        on_ribbon_selected: Callable,
        on_apply_ribbon: Callable,
        on_measure_distance: Callable,
        on_import_mesh: Callable,
        on_screenshot: Callable,
    ) -> None:
        # Frame
        self.tree_widget.set_on_selection_changed(on_tree_selected)
        self.btn_add.set_on_clicked(on_add)
        self.btn_remove.set_on_clicked(on_remove)
        self.btn_rename.set_on_clicked(on_rename)
        self.btn_apply.set_on_clicked(on_apply)
        self.combo_parent.set_on_selection_changed(on_combo_parent)
        self.btn_undo.set_on_clicked(on_undo)
        self.btn_redo.set_on_clicked(on_redo)
        self.btn_copy.set_on_clicked(on_copy)
        self.btn_paste.set_on_clicked(on_paste)
        # Nastri
        self.btn_add_ribbon.set_on_clicked(on_add_ribbon)
        self.btn_remove_ribbon.set_on_clicked(on_remove_ribbon)
        self.ribbon_list.set_on_selection_changed(on_ribbon_selected)
        self.btn_apply_ribbon.set_on_clicked(on_apply_ribbon)
        # Strumenti
        self.btn_measure.set_on_clicked(on_measure_distance)
        self.btn_import_mesh.set_on_clicked(on_import_mesh)
        self.btn_screenshot.set_on_clicked(on_screenshot)
        # I/O
        self._btn_save_json.set_on_clicked(on_save_json)
        self._btn_load_json.set_on_clicked(on_load_json)
        self._btn_export_urdf.set_on_clicked(on_export_urdf)
        self._btn_import_urdf.set_on_clicked(on_import_urdf)
        self._btn_export_csv.set_on_clicked(on_export_csv)
        self._btn_import_csv.set_on_clicked(on_import_csv)
        self._btn_export_yaml.set_on_clicked(on_export_yaml)
        self._btn_import_yaml.set_on_clicked(on_import_yaml)
        self._btn_export_dh.set_on_clicked(on_export_dh)

    # ==================================================================
    # Status
    # ==================================================================

    def set_status(self, msg: str) -> None:
        self.lbl_status.text = msg

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None:
        self.btn_undo.enabled = can_undo
        self.btn_redo.enabled = can_redo

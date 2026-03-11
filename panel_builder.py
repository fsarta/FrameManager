"""
panel_builder.py
----------------
Costruisce il pannello laterale della GUI con sezioni collassabili,
TreeView gerarchico, editor frame, editor nastri, strumenti e I/O.

Usa gui.CollapsableVert per organizzare le sezioni e
altezze fisse per TreeView/ListView per evitare sovrapposizioni.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, TYPE_CHECKING

import open3d.visualization.gui as gui

from frame import Frame
from logger import get_logger

if TYPE_CHECKING:
    from frame_tree import FrameTree

log = get_logger("panel_builder")

# Larghezza pannello (em)
PANEL_WIDTH_EM = 30


class PanelBuilder:
    """
    Costruisce e gestisce tutti i widget del pannello laterale.
    Organizzato in sezioni collassabili per evitare sovrapposizioni.
    """

    def __init__(self) -> None:
        # ── Frame editor ──
        self.panel: Optional[gui.ScrollableVert] = None
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

        # ── Nastri editor ──
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

        # ── I/O (interno) ──
        self._btn_save_json: Optional[gui.Button] = None
        self._btn_load_json: Optional[gui.Button] = None
        self._btn_export_urdf: Optional[gui.Button] = None
        self._btn_import_urdf: Optional[gui.Button] = None
        self._btn_export_csv: Optional[gui.Button] = None
        self._btn_import_csv: Optional[gui.Button] = None
        self._btn_export_yaml: Optional[gui.Button] = None
        self._btn_import_yaml: Optional[gui.Button] = None
        self._btn_export_dh: Optional[gui.Button] = None

        # Internals
        self._tree_item_ids: Dict[str, int] = {}
        self._em: float = 14.0

    # ==================================================================
    # Build
    # ==================================================================

    def build(self, em: float) -> gui.ScrollableVert:
        """Costruisce il pannello scrollabile con sezioni collassabili."""
        self._em = em
        sp = int(0.25 * em)
        margin = gui.Margins(int(0.5 * em), int(0.5 * em),
                             int(0.5 * em), int(0.5 * em))
        self.panel = gui.ScrollableVert(sp, margin)

        # Titolo
        self.panel.add_child(gui.Label("Frame3D Manager"))

        # ── Toolbar Undo/Redo ──
        row_ur = gui.Horiz(int(0.25 * em))
        self.btn_undo = gui.Button("Undo")
        self.btn_redo = gui.Button("Redo")
        self.btn_undo.enabled = False
        self.btn_redo.enabled = False
        row_ur.add_child(self.btn_undo)
        row_ur.add_child(self.btn_redo)
        self.panel.add_child(row_ur)

        # ══ SEZIONE 1: Albero Frame ══
        sec_tree = gui.CollapsableVert("Struttura Frame", sp, gui.Margins(0))
        self.tree_widget = gui.TreeView()
        sec_tree.add_child(self.tree_widget)

        row_btns = gui.Horiz(int(0.25 * em))
        self.btn_add = gui.Button("+ Nuovo")
        self.btn_remove = gui.Button("Rimuovi")
        self.btn_copy = gui.Button("Copia")
        self.btn_paste = gui.Button("Incolla")
        row_btns.add_child(self.btn_add)
        row_btns.add_child(self.btn_remove)
        row_btns.add_child(self.btn_copy)
        row_btns.add_child(self.btn_paste)
        sec_tree.add_child(row_btns)
        self.panel.add_child(sec_tree)

        # ══ SEZIONE 2: Modifica Frame ══
        sec_edit = gui.CollapsableVert("Modifica Frame", sp, gui.Margins(0))
        self._build_editor_contents(sec_edit)
        self.panel.add_child(sec_edit)

        # ══ SEZIONE 3: Matrice 4x4 ══
        sec_mat = gui.CollapsableVert("T Mondo 4x4", sp, gui.Margins(0))
        self.lbl_T = gui.Label("( seleziona un frame )")
        sec_mat.add_child(self.lbl_T)
        self.panel.add_child(sec_mat)

        # ══ SEZIONE 4: Nastri ══
        sec_ribbon = gui.CollapsableVert("Nastri / Conveyor", sp, gui.Margins(0))
        self._build_ribbon_contents(sec_ribbon)
        self.panel.add_child(sec_ribbon)

        # ══ SEZIONE 5: Strumenti ══
        sec_tools = gui.CollapsableVert("Strumenti", sp, gui.Margins(0))
        self._build_tools_contents(sec_tools)
        self.panel.add_child(sec_tools)

        # ══ SEZIONE 6: Import/Export ══
        sec_io = gui.CollapsableVert("Import / Export", sp, gui.Margins(0))
        self._build_io_contents(sec_io)
        self.panel.add_child(sec_io)

        # ── Status ──
        self.lbl_status = gui.Label("")
        self.panel.add_child(self.lbl_status)

        return self.panel

    # ==================================================================
    # Contenuti sezioni
    # ==================================================================

    def _build_editor_contents(self, parent: gui.Widget) -> None:
        em = self._em
        sp = int(0.25 * em)

        # Nome + Rinomina
        r_name = gui.Horiz(sp)
        r_name.add_child(gui.Label("Nome"))
        self.edit_name = gui.TextEdit()
        r_name.add_child(self.edit_name)
        self.btn_rename = gui.Button("Rinomina")
        r_name.add_child(self.btn_rename)
        parent.add_child(r_name)

        # Parent
        r_parent = gui.Horiz(sp)
        r_parent.add_child(gui.Label("Parent"))
        self.combo_parent = gui.Combobox()
        r_parent.add_child(self.combo_parent)
        parent.add_child(r_parent)

        # Traslazione
        parent.add_child(gui.Label("Traslazione (m)"))
        self.ne_tx = self._make_num_row("X", 0.0, parent)
        self.ne_ty = self._make_num_row("Y", 0.0, parent)
        self.ne_tz = self._make_num_row("Z", 0.0, parent)

        # Rotazione
        parent.add_child(gui.Label("Rotazione Euler XYZ (gradi)"))
        self.ne_roll = self._make_num_row("Roll", 0.0, parent)
        self.ne_pitch = self._make_num_row("Pitch", 0.0, parent)
        self.ne_yaw = self._make_num_row("Yaw", 0.0, parent)

        # Applica
        self.btn_apply = gui.Button("Applica Trasformazione")
        parent.add_child(self.btn_apply)

    def _build_ribbon_contents(self, parent: gui.Widget) -> None:
        em = self._em
        sp = int(0.25 * em)

        # Lista nastri
        self.ribbon_list = gui.ListView()
        parent.add_child(self.ribbon_list)

        row = gui.Horiz(sp)
        self.btn_add_ribbon = gui.Button("+ Nastro")
        self.btn_remove_ribbon = gui.Button("Rimuovi")
        row.add_child(self.btn_add_ribbon)
        row.add_child(self.btn_remove_ribbon)
        parent.add_child(row)

        # Nome nastro
        r_rn = gui.Horiz(sp)
        r_rn.add_child(gui.Label("Nome"))
        self.ribbon_edit_name = gui.TextEdit()
        r_rn.add_child(self.ribbon_edit_name)
        parent.add_child(r_rn)

        # Frame padre
        r_rp = gui.Horiz(sp)
        r_rp.add_child(gui.Label("Frame"))
        self.ribbon_combo_parent = gui.Combobox()
        r_rp.add_child(self.ribbon_combo_parent)
        parent.add_child(r_rp)

        # Dimensioni
        parent.add_child(gui.Label("Dimensioni (m)"))
        self.ne_r_width = self._make_num_row("Largh.", 1.0, parent, 3)
        self.ne_r_length = self._make_num_row("Lungh.", 2.0, parent, 3)
        self.ne_r_height = self._make_num_row("Altez.", 0.05, parent, 4)

        # Offset
        parent.add_child(gui.Label("Offset (m)"))
        self.ne_r_tx = self._make_num_row("X", 0.0, parent)
        self.ne_r_ty = self._make_num_row("Y", 0.0, parent)
        self.ne_r_tz = self._make_num_row("Z", 0.0, parent)

        # Rotazione
        parent.add_child(gui.Label("Rotazione (gradi)"))
        self.ne_r_roll = self._make_num_row("Roll", 0.0, parent)
        self.ne_r_pitch = self._make_num_row("Pitch", 0.0, parent)
        self.ne_r_yaw = self._make_num_row("Yaw", 0.0, parent)

        # Colore
        parent.add_child(gui.Label("Colore RGB (0-1)"))
        self.ne_r_red = self._make_num_row("R", 0.60, parent, 2)
        self.ne_r_green = self._make_num_row("G", 0.60, parent, 2)
        self.ne_r_blue = self._make_num_row("B", 0.60, parent, 2)

        # Applica
        self.btn_apply_ribbon = gui.Button("Applica Nastro")
        parent.add_child(self.btn_apply_ribbon)

    def _build_tools_contents(self, parent: gui.Widget) -> None:
        em = self._em
        sp = int(0.25 * em)

        parent.add_child(gui.Label("Distanza tra frame"))
        r_dist = gui.Horiz(sp)
        self.combo_dist_a = gui.Combobox()
        self.combo_dist_b = gui.Combobox()
        self.btn_measure = gui.Button("Misura")
        r_dist.add_child(self.combo_dist_a)
        r_dist.add_child(self.combo_dist_b)
        r_dist.add_child(self.btn_measure)
        parent.add_child(r_dist)
        self.lbl_distance = gui.Label("---")
        parent.add_child(self.lbl_distance)

        r_tools = gui.Horiz(sp)
        self.btn_import_mesh = gui.Button("Importa Mesh")
        self.btn_screenshot = gui.Button("Screenshot")
        r_tools.add_child(self.btn_import_mesh)
        r_tools.add_child(self.btn_screenshot)
        parent.add_child(r_tools)

    def _build_io_contents(self, parent: gui.Widget) -> None:
        sp = int(0.25 * self._em)

        r1 = gui.Horiz(sp)
        self._btn_save_json = gui.Button("Salva JSON")
        self._btn_load_json = gui.Button("Carica JSON")
        r1.add_child(self._btn_save_json)
        r1.add_child(self._btn_load_json)
        parent.add_child(r1)

        r2 = gui.Horiz(sp)
        self._btn_export_urdf = gui.Button("Export URDF")
        self._btn_import_urdf = gui.Button("Import URDF")
        r2.add_child(self._btn_export_urdf)
        r2.add_child(self._btn_import_urdf)
        parent.add_child(r2)

        r3 = gui.Horiz(sp)
        self._btn_export_csv = gui.Button("CSV out")
        self._btn_import_csv = gui.Button("CSV in")
        self._btn_export_yaml = gui.Button("YAML out")
        self._btn_import_yaml = gui.Button("YAML in")
        r3.add_child(self._btn_export_csv)
        r3.add_child(self._btn_import_csv)
        r3.add_child(self._btn_export_yaml)
        r3.add_child(self._btn_import_yaml)
        parent.add_child(r3)

        r4 = gui.Horiz(sp)
        self._btn_export_dh = gui.Button("Export DH Params")
        r4.add_child(self._btn_export_dh)
        parent.add_child(r4)

    # ==================================================================
    # Helper
    # ==================================================================

    def _make_num_row(
        self, label: str, default: float,
        parent: gui.Widget, precision: int = 4,
    ) -> gui.NumberEdit:
        """Crea riga label + NumberEdit e la aggiunge al parent."""
        sp = int(0.25 * self._em)
        row = gui.Horiz(sp)
        lbl = gui.Label(f"  {label}")
        row.add_child(lbl)
        ne = gui.NumberEdit(gui.NumberEdit.DOUBLE)
        ne.double_value = default
        ne.decimal_precision = precision
        row.add_child(ne)
        parent.add_child(row)
        return ne

    # ==================================================================
    # TreeView population
    # ==================================================================

    def refresh_tree(self, tree: "FrameTree") -> None:
        """Ricostruisce il TreeView e tutti i combo box."""
        self.tree_widget.clear()
        self._tree_item_ids.clear()
        self._add_tree_node(tree, "world", parent_id=0)

        # Combo parent (frame)
        self.combo_parent.clear_items()
        for name in tree.get_all_names():
            self.combo_parent.add_item(name)

        # Combo nastri parent
        self.ribbon_combo_parent.clear_items()
        for name in tree.get_all_names():
            self.ribbon_combo_parent.add_item(name)

        # Combo distanza
        self.combo_dist_a.clear_items()
        self.combo_dist_b.clear_items()
        for name in tree.get_all_names():
            self.combo_dist_a.add_item(name)
            self.combo_dist_b.add_item(name)

    def refresh_ribbon_list(self, tree: "FrameTree") -> None:
        """Aggiorna la lista dei nastri."""
        names = tree.get_ribbon_names()
        self.ribbon_list.set_items(names)

    def _add_tree_node(
        self, tree: "FrameTree", name: str, parent_id: int
    ) -> None:
        """Aggiunge ricorsivamente un nodo al TreeView."""
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
        """Dato un item ID del TreeView, restituisce il nome del frame."""
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
        """Connette tutti i callback ai widget."""
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
        self.btn_add_ribbon.set_on_clicked(on_add_ribbon)
        self.btn_remove_ribbon.set_on_clicked(on_remove_ribbon)
        self.ribbon_list.set_on_selection_changed(on_ribbon_selected)
        self.btn_apply_ribbon.set_on_clicked(on_apply_ribbon)
        self.btn_measure.set_on_clicked(on_measure_distance)
        self.btn_import_mesh.set_on_clicked(on_import_mesh)
        self.btn_screenshot.set_on_clicked(on_screenshot)
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
    # Status helpers
    # ==================================================================

    def set_status(self, msg: str) -> None:
        self.lbl_status.text = msg

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None:
        self.btn_undo.enabled = can_undo
        self.btn_redo.enabled = can_redo

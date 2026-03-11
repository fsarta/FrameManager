"""
panel_builder.py
----------------
Costruisce il pannello laterale della GUI con TreeView gerarchico,
editor frame con rinomina, pulsanti I/O estesi, e toolbar Undo/Redo.

Estratto da app.py per separare la costruzione GUI dalla logica.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, TYPE_CHECKING

import open3d.visualization.gui as gui

from frame import Frame
from logger import get_logger

if TYPE_CHECKING:
    from frame_tree import FrameTree

log = get_logger("panel_builder")


class PanelBuilder:
    """
    Costruisce e gestisce tutti i widget del pannello laterale.

    Tutti i widget sono esposti come attributi per l'accesso da app.py.
    I callback sono configurati dall'esterno tramite metodi `set_on_*`.
    """

    def __init__(self) -> None:
        # Widget esposti
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

        # TreeView internals
        self._tree_item_ids: Dict[str, int] = {}  # name → tree item id

    def build(self, em: float) -> gui.Vert:
        """
        Costruisce il pannello completo e lo restituisce.

        Parameters
        ----------
        em : float
            Dimensione del font in pixel (dal theme).

        Returns
        -------
        gui.Vert
            Il pannello laterale con tutti i widget.
        """
        margin = gui.Margins(int(0.5 * em))
        self.panel = gui.Vert(int(0.35 * em), margin)

        self._build_title()
        self._build_undo_redo_toolbar(em)
        self._build_tree_view(em)
        self._build_frame_buttons(em)
        self._build_editor(em)
        self._build_world_matrix()
        self._build_io_buttons(em)
        self._build_status_bar()

        return self.panel

    # ------------------------------------------------------------------
    # Sezioni del pannello
    # ------------------------------------------------------------------

    def _build_title(self) -> None:
        self.panel.add_child(gui.Label("  Frame3D Manager"))
        self.panel.add_child(gui.Label(""))

    def _build_undo_redo_toolbar(self, em: float) -> None:
        row = gui.Horiz(int(0.3 * em))
        self.btn_undo = gui.Button("↩ Undo")
        self.btn_redo = gui.Button("↪ Redo")
        self.btn_undo.enabled = False
        self.btn_redo.enabled = False
        row.add_child(self.btn_undo)
        row.add_child(self.btn_redo)
        self.panel.add_child(row)
        self.panel.add_child(gui.Label(""))

    def _build_tree_view(self, em: float) -> None:
        self.panel.add_child(gui.Label("Struttura frame (TreeView):"))
        self.tree_widget = gui.TreeView()
        self.panel.add_child(self.tree_widget)

    def _build_frame_buttons(self, em: float) -> None:
        btn_row = gui.Horiz(int(0.3 * em))
        self.btn_add = gui.Button("+ Nuovo")
        self.btn_remove = gui.Button("x Rimuovi")
        btn_row.add_child(self.btn_add)
        btn_row.add_child(self.btn_remove)
        self.panel.add_child(btn_row)
        self.panel.add_child(gui.Label(""))

    def _build_editor(self, em: float) -> None:
        self.panel.add_child(gui.Label("-- Modifica Frame ----------"))

        # Nome + Rinomina
        r_name = gui.Horiz(int(0.3 * em))
        r_name.add_child(gui.Label("Nome:  "))
        self.edit_name = gui.TextEdit()
        r_name.add_child(self.edit_name)
        self.btn_rename = gui.Button("Rinomina")
        r_name.add_child(self.btn_rename)
        self.panel.add_child(r_name)

        # Parent combo
        r_parent = gui.Horiz(int(0.3 * em))
        r_parent.add_child(gui.Label("Parent:"))
        self.combo_parent = gui.Combobox()
        r_parent.add_child(self.combo_parent)
        self.panel.add_child(r_parent)

        # Traslazione
        self.panel.add_child(gui.Label("Traslazione (m):"))
        self.ne_tx = self._add_num_row("  X", 0.0)
        self.ne_ty = self._add_num_row("  Y", 0.0)
        self.ne_tz = self._add_num_row("  Z", 0.0)

        # Rotazione
        self.panel.add_child(gui.Label("Rotazione Euler XYZ (gradi):"))
        self.ne_roll = self._add_num_row("  Roll ", 0.0)
        self.ne_pitch = self._add_num_row("  Pitch", 0.0)
        self.ne_yaw = self._add_num_row("  Yaw  ", 0.0)

        # Bottone applica
        self.btn_apply = gui.Button("Applica Trasformazione")
        self.panel.add_child(self.btn_apply)
        self.panel.add_child(gui.Label(""))

    def _build_world_matrix(self) -> None:
        self.panel.add_child(gui.Label("-- T Mondo 4x4 -------------"))
        self.lbl_T = gui.Label("( seleziona un frame )")
        self.panel.add_child(self.lbl_T)
        self.panel.add_child(gui.Label(""))

    def _build_io_buttons(self, em: float) -> None:
        self.panel.add_child(gui.Label("-- Import / Export ---------"))

        # JSON
        io_row1 = gui.Horiz(int(0.3 * em))
        self._btn_save_json = gui.Button("Salva JSON")
        self._btn_load_json = gui.Button("Carica JSON")
        io_row1.add_child(self._btn_save_json)
        io_row1.add_child(self._btn_load_json)
        self.panel.add_child(io_row1)

        # URDF
        io_row2 = gui.Horiz(int(0.3 * em))
        self._btn_export_urdf = gui.Button("Esporta URDF")
        self._btn_import_urdf = gui.Button("Importa URDF")
        io_row2.add_child(self._btn_export_urdf)
        io_row2.add_child(self._btn_import_urdf)
        self.panel.add_child(io_row2)

        # CSV
        io_row3 = gui.Horiz(int(0.3 * em))
        self._btn_export_csv = gui.Button("Esporta CSV")
        self._btn_import_csv = gui.Button("Importa CSV")
        io_row3.add_child(self._btn_export_csv)
        io_row3.add_child(self._btn_import_csv)
        self.panel.add_child(io_row3)

        # YAML
        io_row4 = gui.Horiz(int(0.3 * em))
        self._btn_export_yaml = gui.Button("Esporta YAML")
        self._btn_import_yaml = gui.Button("Importa YAML")
        io_row4.add_child(self._btn_export_yaml)
        io_row4.add_child(self._btn_import_yaml)
        self.panel.add_child(io_row4)

        # DH
        io_row5 = gui.Horiz(int(0.3 * em))
        self._btn_export_dh = gui.Button("Esporta DH Params")
        io_row5.add_child(self._btn_export_dh)
        self.panel.add_child(io_row5)

        self.panel.add_child(gui.Label(""))

    def _build_status_bar(self) -> None:
        self.lbl_status = gui.Label("")
        self.panel.add_child(self.lbl_status)

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def _add_num_row(self, label: str, default: float) -> gui.NumberEdit:
        """Helper: crea una riga label + NumberEdit e la aggiunge al pannello."""
        row = gui.Horiz(int(4))
        row.add_child(gui.Label(label))
        ne = gui.NumberEdit(gui.NumberEdit.DOUBLE)
        ne.double_value = default
        ne.decimal_precision = 4
        row.add_child(ne)
        self.panel.add_child(row)
        return ne

    # ------------------------------------------------------------------
    # TreeView population
    # ------------------------------------------------------------------

    def refresh_tree(self, tree: "FrameTree") -> None:
        """
        Ricostruisce il TreeView con la struttura gerarchica dell'albero.

        Parameters
        ----------
        tree : FrameTree
            L'albero dei frame.
        """
        self.tree_widget.clear()
        self._tree_item_ids.clear()

        # Costruisci l'albero ricorsivamente partendo da "world"
        self._add_tree_node(tree, "world", parent_id=0)

        # Aggiorna anche il combo parent
        self.combo_parent.clear_items()
        for name in tree.get_all_names():
            self.combo_parent.add_item(name)

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

        # Aggiungi i figli
        children = tree.get_children(name)
        for child_name in children:
            self._add_tree_node(tree, child_name, item_id)

    def get_name_from_tree_item(self, item_id: int) -> Optional[str]:
        """Dato un item ID del TreeView, restituisce il nome del frame."""
        for name, tid in self._tree_item_ids.items():
            if tid == item_id:
                return name
        return None

    # ------------------------------------------------------------------
    # Callback wiring (chiamato da app.py)
    # ------------------------------------------------------------------

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
        on_save_json: Callable,
        on_load_json: Callable,
        on_export_urdf: Callable,
        on_import_urdf: Callable,
        on_export_csv: Callable,
        on_import_csv: Callable,
        on_export_yaml: Callable,
        on_import_yaml: Callable,
        on_export_dh: Callable,
    ) -> None:
        """Connette tutti i callback ai widget del pannello."""
        self.tree_widget.set_on_selection_changed(on_tree_selected)
        self.btn_add.set_on_clicked(on_add)
        self.btn_remove.set_on_clicked(on_remove)
        self.btn_rename.set_on_clicked(on_rename)
        self.btn_apply.set_on_clicked(on_apply)
        self.combo_parent.set_on_selection_changed(on_combo_parent)
        self.btn_undo.set_on_clicked(on_undo)
        self.btn_redo.set_on_clicked(on_redo)
        self._btn_save_json.set_on_clicked(on_save_json)
        self._btn_load_json.set_on_clicked(on_load_json)
        self._btn_export_urdf.set_on_clicked(on_export_urdf)
        self._btn_import_urdf.set_on_clicked(on_import_urdf)
        self._btn_export_csv.set_on_clicked(on_export_csv)
        self._btn_import_csv.set_on_clicked(on_import_csv)
        self._btn_export_yaml.set_on_clicked(on_export_yaml)
        self._btn_import_yaml.set_on_clicked(on_import_yaml)
        self._btn_export_dh.set_on_clicked(on_export_dh)

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def set_status(self, msg: str) -> None:
        """Aggiorna il testo della status bar."""
        self.lbl_status.text = msg

    def update_undo_redo_state(self, can_undo: bool, can_redo: bool) -> None:
        """Abilita/disabilita i pulsanti Undo/Redo."""
        self.btn_undo.enabled = can_undo
        self.btn_redo.enabled = can_redo

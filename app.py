"""
app.py
------
Applicazione principale: finestra Open3D con pannello laterale per la
gestione interattiva dei frame 3D, nastri e mesh.

Architettura
-----------
  - SceneRenderer: rendering 3D con highlight, nastri e mesh
  - PanelBuilder: pannello scrollabile (TreeView, editor, nastri, strumenti, I/O)
  - UndoRedoManager: annulla/ripristina operazioni
  - IOHandler: salvataggio/caricamento (JSON, URDF, CSV, YAML, DH)
  - FrameTree → Observer pattern: notifica automatica dei cambiamenti

Layout
------
  ┌──────────────────────────────┬─────────────────────────┐
  │                              │  ↩ Undo  ↪ Redo         │
  │      Scena 3D                │  Struttura TreeView      │
  │   (assi, nastri, mesh,       │  [+] [✕] [📋] [📄]      │
  │    highlight selezione)      │  ── Modifica Frame ───── │
  │                              │  Nome [Rinomina]         │
  │                              │  Parent / Pos / Rot      │
  │                              │  [Applica]               │
  │                              │  ── T mondo 4×4 ──────── │
  │                              │  ── Nastri ────────────── │
  │                              │  Lista / Dim / Pos / Col  │
  │                              │  ── Strumenti ─────────── │
  │                              │  Distanza / Mesh / 📷     │
  │                              │  ── Import / Export ────── │
  └──────────────────────────────┴─────────────────────────┘
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from frame import Frame
from ribbon import Ribbon
from frame_tree import FrameTree
from io_handler import IOHandler
from scene_renderer import SceneRenderer
from panel_builder import PanelBuilder, PANEL_WIDTH_EM
from undo_redo import UndoRedoManager
from logger import get_logger

log = get_logger("app")


class Frame3DApp:
    """
    Applicazione GUI per la visualizzazione e gestione di frame 3D.

    Usage
    -----
    >>> app = Frame3DApp()
    >>> app.run()
    """

    def __init__(self) -> None:
        self.tree = FrameTree()
        self.io = IOHandler()
        self.undo_mgr = UndoRedoManager()
        self._selected: Optional[str] = None
        self._selected_ribbon: Optional[str] = None
        self._clipboard_frame: Optional[Frame] = None
        self._updating_ui: bool = False

        # Recovery o demo
        if IOHandler.has_autosave():
            recovered = IOHandler.load_autosave()
            if recovered is not None:
                self.tree = recovered
                log.info("Sessione recuperata da autosave")
            else:
                self._build_demo_scene()
        else:
            self._build_demo_scene()

        self.undo_mgr.save_state(self.tree.to_dict())
        self._connect_tree_signals()
        self._build_gui()

    # ------------------------------------------------------------------
    # Observer
    # ------------------------------------------------------------------

    def _connect_tree_signals(self) -> None:
        self.tree.frame_added.connect(self._on_tree_changed)
        self.tree.frame_removed.connect(self._on_tree_changed)
        self.tree.frame_modified.connect(self._on_tree_changed)
        self.tree.ribbon_changed.connect(self._on_tree_changed)
        self.tree.tree_loaded.connect(self._on_tree_loaded)

    def _disconnect_tree_signals(self) -> None:
        self.tree.frame_added.clear()
        self.tree.frame_removed.clear()
        self.tree.frame_modified.clear()
        self.tree.ribbon_changed.clear()
        self.tree.tree_loaded.clear()

    def _on_tree_changed(self, name: str = "") -> None:
        if not self._updating_ui:
            self._autosave()

    def _on_tree_loaded(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Demo scene
    # ------------------------------------------------------------------

    def _build_demo_scene(self) -> None:
        fa = Frame("frame_A", parent="world",
                   translation=np.array([1.0, 0.0, 0.0]))
        fa.set_rotation_euler(0, 0, 30)
        self.tree.add_frame(fa)

        fb = Frame("frame_B", parent="frame_A",
                   translation=np.array([0.6, 0.3, 0.2]))
        fb.set_rotation_euler(15, -10, 0)
        self.tree.add_frame(fb)

        fc = Frame("frame_C", parent="world",
                   translation=np.array([0.0, 0.9, 0.5]))
        fc.set_rotation_euler(0, 45, 0)
        self.tree.add_frame(fc)

        fd = Frame("frame_D", parent="frame_C",
                   translation=np.array([0.4, 0.0, 0.0]))
        self.tree.add_frame(fd)

        # Nastro di esempio
        r = Ribbon("nastro_1", parent_frame="world",
                   width=1.0, length=2.5, height=0.04,
                   translation=np.array([-0.5, 0.0, 0.5]),
                   color=[0.20, 0.40, 0.85], opacity=0.7)
        self.tree.add_ribbon(r)

    # ------------------------------------------------------------------
    # GUI
    # ------------------------------------------------------------------

    def _build_gui(self) -> None:
        app = gui.Application.instance
        app.initialize()

        self.win = app.create_window("Frame3D Manager", 1440, 900)
        em = self.win.theme.font_size

        # Vista 3D
        self._scene_widget = gui.SceneWidget()
        self._scene_widget.scene = rendering.Open3DScene(self.win.renderer)

        self.renderer = SceneRenderer(self._scene_widget)
        self.renderer.setup_scene()

        # Pannello
        self.panel_builder = PanelBuilder()
        panel = self.panel_builder.build(em)

        self.panel_builder.wire_callbacks(
            on_tree_selected=self._on_tree_selected,
            on_add=self._on_click_add,
            on_remove=self._on_click_remove,
            on_rename=self._on_click_rename,
            on_apply=self._on_click_apply,
            on_combo_parent=self._on_combo_parent_changed,
            on_undo=self._on_undo,
            on_redo=self._on_redo,
            on_copy=self._on_copy,
            on_paste=self._on_paste,
            on_save_json=self._on_save_json,
            on_load_json=self._on_load_json,
            on_export_urdf=self._on_export_urdf,
            on_import_urdf=self._on_import_urdf,
            on_export_csv=self._on_export_csv,
            on_import_csv=self._on_import_csv,
            on_export_yaml=self._on_export_yaml,
            on_import_yaml=self._on_import_yaml,
            on_export_dh=self._on_export_dh,
            on_add_ribbon=self._on_add_ribbon,
            on_remove_ribbon=self._on_remove_ribbon,
            on_ribbon_selected=self._on_ribbon_selected,
            on_apply_ribbon=self._on_apply_ribbon,
            on_measure_distance=self._on_measure_distance,
            on_import_mesh=self._on_import_mesh,
            on_screenshot=self._on_screenshot,
        )

        self.undo_mgr.state_changed.connect(
            self.panel_builder.update_undo_redo_state
        )

        self.win.add_child(self._scene_widget)
        self.win.add_child(panel)
        self.win.set_on_layout(self._on_layout)

        self._refresh_all()
        self.renderer.reset_camera()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _on_layout(self, ctx) -> None:
        r = self.win.content_rect
        em = self.win.theme.font_size
        panel_w = int(PANEL_WIDTH_EM * em)
        self._scene_widget.frame = gui.Rect(
            r.x, r.y, r.width - panel_w, r.height
        )
        self.panel_builder.panel.frame = gui.Rect(
            r.x + r.width - panel_w, r.y, panel_w, r.height
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        self.renderer.refresh_scene(self.tree, self._selected)
        self.panel_builder.refresh_tree(self.tree)
        self.panel_builder.refresh_ribbon_list(self.tree)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_undo_state(self) -> None:
        self.undo_mgr.save_state(self.tree.to_dict())

    def _autosave(self) -> None:
        try:
            IOHandler.autosave(self.tree)
        except Exception as exc:
            log.warning("Autosave fallito: %s", exc)

    def _status(self, msg: str) -> None:
        self.panel_builder.set_status(msg)
        log.info("Status: %s", msg)

    # ------------------------------------------------------------------
    # Callbacks: Frame selection
    # ------------------------------------------------------------------

    def _on_tree_selected(self, item_id: int) -> None:
        name = self.panel_builder.get_name_from_tree_item(item_id)
        if name:
            self._selected = name
            self._sync_ui_from_frame(name)
            self.renderer.refresh_scene(self.tree, self._selected)

    def _sync_ui_from_frame(self, name: str) -> None:
        if name not in self.tree.frames:
            return
        self._updating_ui = True
        pb = self.panel_builder
        frame = self.tree.frames[name]
        pb.edit_name.text_value = name

        all_names = self.tree.get_all_names()
        parent = frame.parent or "world"
        if parent in all_names:
            pb.combo_parent.selected_index = all_names.index(parent)

        t = frame.translation
        pb.ne_tx.double_value = float(t[0])
        pb.ne_ty.double_value = float(t[1])
        pb.ne_tz.double_value = float(t[2])

        rpy = frame.get_rotation_euler(degrees=True)
        pb.ne_roll.double_value = float(rpy[0])
        pb.ne_pitch.double_value = float(rpy[1])
        pb.ne_yaw.double_value = float(rpy[2])

        try:
            T = self.tree.get_world_transform(name)
            rows = [
                f"[{T[i,0]:+6.3f} {T[i,1]:+6.3f} {T[i,2]:+6.3f} {T[i,3]:+6.3f}]"
                for i in range(4)
            ]
            pb.lbl_T.text = "\n".join(rows)
        except RuntimeError as exc:
            pb.lbl_T.text = f"Errore: {exc}"

        self._updating_ui = False

    # ------------------------------------------------------------------
    # Callbacks: Frame editing
    # ------------------------------------------------------------------

    def _on_combo_parent_changed(self, val: str, idx: int) -> None:
        pass

    def _on_click_apply(self) -> None:
        if not self._selected or self._selected == "world":
            self._status("Seleziona un frame non-world da modificare.")
            return
        pb = self.panel_builder
        frame = self.tree.frames[self._selected]
        self._save_undo_state()

        frame.translation = np.array([
            pb.ne_tx.double_value,
            pb.ne_ty.double_value,
            pb.ne_tz.double_value,
        ])
        frame.set_rotation_euler(
            pb.ne_roll.double_value,
            pb.ne_pitch.double_value,
            pb.ne_yaw.double_value,
            degrees=True,
        )

        all_names = self.tree.get_all_names()
        idx = pb.combo_parent.selected_index
        if 0 <= idx < len(all_names):
            new_parent = all_names[idx]
            if new_parent != self._selected:
                if not self.tree.would_create_cycle(self._selected, new_parent):
                    frame.parent = new_parent
                else:
                    self._status("Errore: parent creerebbe un ciclo!")
                    return

        self._refresh_all()
        self._sync_ui_from_frame(self._selected)
        self._status(f"Frame '{self._selected}' aggiornato.")

    def _on_click_add(self) -> None:
        dlg = gui.Dialog("Nuovo Frame")
        body = gui.Vert(10, gui.Margins(15, 15, 15, 15))
        body.add_child(gui.Label("Nome del nuovo frame:"))
        name_field = gui.TextEdit()
        name_field.text_value = f"frame_{len(self.tree.frames)}"
        body.add_child(name_field)
        btns = gui.Horiz(8)
        ok_btn = gui.Button("  OK  ")
        ca_btn = gui.Button("Annulla")
        btns.add_child(ok_btn)
        btns.add_child(ca_btn)
        body.add_child(btns)
        dlg.add_child(body)

        def _ok() -> None:
            n = name_field.text_value.strip()
            if not Frame.validate_name(n):
                self._status(f"Nome '{n}' non valido (solo lettere, cifre, _).")
                self.win.close_dialog()
                return
            if n in self.tree.frames:
                self._status(f"Il nome '{n}' esiste già.")
                self.win.close_dialog()
                return
            self._save_undo_state()
            self.tree.add_frame(Frame(n, parent="world"))
            self._refresh_all()
            self._status(f"Frame '{n}' aggiunto.")
            self.win.close_dialog()

        ok_btn.set_on_clicked(_ok)
        ca_btn.set_on_clicked(self.win.close_dialog)
        self.win.show_dialog(dlg)

    def _on_click_remove(self) -> None:
        if not self._selected or self._selected == "world":
            self._status("Impossibile rimuovere 'world'.")
            return
        name = self._selected
        self._save_undo_state()
        self.tree.remove_frame(name)
        self._selected = None
        self.panel_builder.edit_name.text_value = ""
        self.panel_builder.lbl_T.text = "( seleziona un frame )"
        self._refresh_all()
        self._status(f"Frame '{name}' rimosso.")

    def _on_click_rename(self) -> None:
        if not self._selected or self._selected == "world":
            self._status("Impossibile rinominare 'world'.")
            return
        new_name = self.panel_builder.edit_name.text_value.strip()
        if not Frame.validate_name(new_name):
            self._status(f"Nome '{new_name}' non valido.")
            return
        if new_name == self._selected:
            return
        if new_name in self.tree.frames:
            self._status(f"Il nome '{new_name}' esiste già.")
            return
        old = self._selected
        self._save_undo_state()
        if self.tree.rename_frame(old, new_name):
            self._selected = new_name
            self._refresh_all()
            self._sync_ui_from_frame(new_name)
            self._status(f"Rinominato: '{old}' → '{new_name}'.")

    # ------------------------------------------------------------------
    # Callbacks: Copy / Paste
    # ------------------------------------------------------------------

    def _on_copy(self) -> None:
        if not self._selected or self._selected == "world":
            self._status("Seleziona un frame da copiare.")
            return
        self._clipboard_frame = self.tree.frames[self._selected].copy()
        self._status(f"Frame '{self._selected}' copiato.")

    def _on_paste(self) -> None:
        if self._clipboard_frame is None:
            self._status("Nessun frame nella clipboard.")
            return
        new_frame = self._clipboard_frame.copy()
        # Genera un nome unico
        base_name = new_frame.name + "_copy"
        name = base_name
        counter = 1
        while name in self.tree.frames:
            name = f"{base_name}_{counter}"
            counter += 1
        new_frame.name = name
        self._save_undo_state()
        self.tree.add_frame(new_frame)
        self._refresh_all()
        self._status(f"Frame '{name}' incollato.")

    # ------------------------------------------------------------------
    # Callbacks: Undo / Redo
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        state = self.undo_mgr.undo()
        if state is not None:
            self._restore_tree_from_dict(state)
            self._status("Undo eseguito.")
        else:
            self._status("Nessuna operazione da annullare.")

    def _on_redo(self) -> None:
        state = self.undo_mgr.redo()
        if state is not None:
            self._restore_tree_from_dict(state)
            self._status("Redo eseguito.")
        else:
            self._status("Nessuna operazione da ripristinare.")

    def _restore_tree_from_dict(self, state: dict) -> None:
        self._disconnect_tree_signals()
        self.tree = FrameTree.from_dict(state)
        self._connect_tree_signals()
        self._selected = None
        self._selected_ribbon = None
        self.panel_builder.edit_name.text_value = ""
        self.panel_builder.lbl_T.text = "( seleziona un frame )"
        self._refresh_all()

    # ------------------------------------------------------------------
    # Callbacks: Nastri
    # ------------------------------------------------------------------

    def _on_add_ribbon(self) -> None:
        dlg = gui.Dialog("Nuovo Nastro")
        body = gui.Vert(10, gui.Margins(15, 15, 15, 15))
        body.add_child(gui.Label("Nome del nuovo nastro:"))
        name_field = gui.TextEdit()
        name_field.text_value = f"nastro_{len(self.tree.ribbons) + 1}"
        body.add_child(name_field)
        btns = gui.Horiz(8)
        ok_btn = gui.Button("  OK  ")
        ca_btn = gui.Button("Annulla")
        btns.add_child(ok_btn)
        btns.add_child(ca_btn)
        body.add_child(btns)
        dlg.add_child(body)

        def _ok() -> None:
            n = name_field.text_value.strip()
            if not Ribbon.validate_name(n):
                self._status(f"Nome nastro '{n}' non valido.")
                self.win.close_dialog()
                return
            if n in self.tree.ribbons:
                self._status(f"Il nastro '{n}' esiste già.")
                self.win.close_dialog()
                return
            self._save_undo_state()
            r = Ribbon(n, parent_frame="world")
            self.tree.add_ribbon(r)
            self._refresh_all()
            self._status(f"Nastro '{n}' aggiunto.")
            self.win.close_dialog()

        ok_btn.set_on_clicked(_ok)
        ca_btn.set_on_clicked(self.win.close_dialog)
        self.win.show_dialog(dlg)

    def _on_remove_ribbon(self) -> None:
        if not self._selected_ribbon:
            self._status("Seleziona un nastro da rimuovere.")
            return
        name = self._selected_ribbon
        self._save_undo_state()
        self.tree.remove_ribbon(name)
        self._selected_ribbon = None
        self._refresh_all()
        self._status(f"Nastro '{name}' rimosso.")

    def _on_ribbon_selected(self, new_val: str, is_double_click: bool) -> None:
        self._selected_ribbon = new_val
        self._sync_ui_from_ribbon(new_val)

    def _sync_ui_from_ribbon(self, name: str) -> None:
        if name not in self.tree.ribbons:
            return
        self._updating_ui = True
        pb = self.panel_builder
        ribbon = self.tree.ribbons[name]

        pb.ribbon_edit_name.text_value = name

        # Parent combo
        all_names = self.tree.get_all_names()
        if ribbon.parent_frame in all_names:
            pb.ribbon_combo_parent.selected_index = all_names.index(ribbon.parent_frame)

        # Dimensioni
        pb.ne_r_width.double_value = ribbon.width
        pb.ne_r_length.double_value = ribbon.length
        pb.ne_r_height.double_value = ribbon.height

        # Offset posizione
        pb.ne_r_tx.double_value = float(ribbon.translation[0])
        pb.ne_r_ty.double_value = float(ribbon.translation[1])
        pb.ne_r_tz.double_value = float(ribbon.translation[2])

        # Rotazione
        rpy = ribbon.get_rotation_euler(degrees=True)
        pb.ne_r_roll.double_value = float(rpy[0])
        pb.ne_r_pitch.double_value = float(rpy[1])
        pb.ne_r_yaw.double_value = float(rpy[2])

        # Colore
        pb.ne_r_red.double_value = ribbon.color[0]
        pb.ne_r_green.double_value = ribbon.color[1]
        pb.ne_r_blue.double_value = ribbon.color[2]

        self._updating_ui = False

    def _on_apply_ribbon(self) -> None:
        if not self._selected_ribbon:
            self._status("Seleziona un nastro da modificare.")
            return
        if self._selected_ribbon not in self.tree.ribbons:
            self._status("Nastro non trovato.")
            return

        pb = self.panel_builder
        ribbon = self.tree.ribbons[self._selected_ribbon]
        self._save_undo_state()

        # Frame padre
        all_names = self.tree.get_all_names()
        idx = pb.ribbon_combo_parent.selected_index
        if 0 <= idx < len(all_names):
            ribbon.parent_frame = all_names[idx]

        # Dimensioni
        ribbon.width = max(0.001, pb.ne_r_width.double_value)
        ribbon.length = max(0.001, pb.ne_r_length.double_value)
        ribbon.height = max(0.001, pb.ne_r_height.double_value)

        # Offset
        ribbon.translation = np.array([
            pb.ne_r_tx.double_value,
            pb.ne_r_ty.double_value,
            pb.ne_r_tz.double_value,
        ])

        # Rotazione
        ribbon.set_rotation_euler(
            pb.ne_r_roll.double_value,
            pb.ne_r_pitch.double_value,
            pb.ne_r_yaw.double_value,
            degrees=True,
        )

        # Colore
        ribbon.color = [
            max(0.0, min(1.0, pb.ne_r_red.double_value)),
            max(0.0, min(1.0, pb.ne_r_green.double_value)),
            max(0.0, min(1.0, pb.ne_r_blue.double_value)),
        ]

        self._refresh_all()
        self._status(f"Nastro '{self._selected_ribbon}' aggiornato.")

    # ------------------------------------------------------------------
    # Callbacks: Distance measurement
    # ------------------------------------------------------------------

    def _on_measure_distance(self) -> None:
        pb = self.panel_builder
        all_names = self.tree.get_all_names()
        idx_a = pb.combo_dist_a.selected_index
        idx_b = pb.combo_dist_b.selected_index

        if idx_a < 0 or idx_b < 0 or idx_a >= len(all_names) or idx_b >= len(all_names):
            self._status("Seleziona due frame per misurare.")
            return

        name_a = all_names[idx_a]
        name_b = all_names[idx_b]

        try:
            T_a = self.tree.get_world_transform(name_a)
            T_b = self.tree.get_world_transform(name_b)
            dist = float(np.linalg.norm(T_a[:3, 3] - T_b[:3, 3]))
            delta = T_b[:3, 3] - T_a[:3, 3]
            pb.lbl_distance.text = (
                f"  Distanza: {dist:.4f} m\n"
                f"  Δ = [{delta[0]:+.4f}, {delta[1]:+.4f}, {delta[2]:+.4f}]"
            )
            self._status(f"Distanza {name_a}↔{name_b}: {dist:.4f} m")
        except Exception as exc:
            pb.lbl_distance.text = f"  Errore: {exc}"

    # ------------------------------------------------------------------
    # Callbacks: Mesh import
    # ------------------------------------------------------------------

    def _on_import_mesh(self) -> None:
        if not self._selected or self._selected == "world":
            self._status("Seleziona un frame a cui attaccare la mesh.")
            return
        d = gui.FileDialog(gui.FileDialog.OPEN, "Importa Mesh", self.win.theme)
        d.add_filter(".stl", "File STL (*.stl)")
        d.add_filter(".obj", "File OBJ (*.obj)")
        d.add_filter(".ply", "File PLY (*.ply)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_import_mesh)
        self.win.show_dialog(d)

    def _do_import_mesh(self, path: str) -> None:
        self.win.close_dialog()
        if not self._selected:
            return
        if self.renderer.attach_mesh(self._selected, path):
            self._refresh_all()
            self._status(f"Mesh caricata su '{self._selected}': {path}")
        else:
            self._status(f"Errore nel caricamento della mesh: {path}")

    # ------------------------------------------------------------------
    # Callbacks: Screenshot
    # ------------------------------------------------------------------

    def _on_screenshot(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Salva Screenshot", self.win.theme)
        d.add_filter(".png", "File PNG (*.png)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_screenshot)
        self.win.show_dialog(d)

    def _do_screenshot(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".png"):
                path += ".png"

            def _capture(img):
                o3d.io.write_image(path, img)
                gui.Application.instance.post_to_main_thread(
                    self.win,
                    lambda: self._status(f"Screenshot salvato: {path}")
                )

            self._scene_widget.scene.scene.render_to_image(_capture)
        except Exception as exc:
            log.error("Errore screenshot: %s", exc)
            self._status(f"Errore screenshot: {exc}")

    # ------------------------------------------------------------------
    # Callbacks: I/O
    # ------------------------------------------------------------------

    def _on_save_json(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Salva JSON", self.win.theme)
        d.add_filter(".json", "File JSON (*.json)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_save_json)
        self.win.show_dialog(d)

    def _do_save_json(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".json"):
                path += ".json"
            self.io.save_json(self.tree, path)
            self._status(f"Salvato: {path}")
        except Exception as exc:
            log.error("Errore salvataggio JSON: %s", exc)
            self._status(f"Errore salvataggio: {exc}")

    def _on_load_json(self) -> None:
        d = gui.FileDialog(gui.FileDialog.OPEN, "Carica JSON", self.win.theme)
        d.add_filter(".json", "File JSON (*.json)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_load_json)
        self.win.show_dialog(d)

    def _do_load_json(self, path: str) -> None:
        self.win.close_dialog()
        try:
            self._save_undo_state()
            self._disconnect_tree_signals()
            self.tree = self.io.load_json(path)
            self._connect_tree_signals()
            self._selected = None
            self._selected_ribbon = None
            self._refresh_all()
            self._status(f"Caricato: {path}")
        except Exception as exc:
            log.error("Errore caricamento JSON: %s", exc)
            self._status(f"Errore caricamento: {exc}")

    def _on_export_urdf(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Esporta URDF", self.win.theme)
        d.add_filter(".urdf", "File URDF (*.urdf)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_export_urdf)
        self.win.show_dialog(d)

    def _do_export_urdf(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".urdf"):
                path += ".urdf"
            self.io.export_urdf(self.tree, path)
            self._status(f"URDF esportato: {path}")
        except Exception as exc:
            log.error("Errore esportazione URDF: %s", exc)
            self._status(f"Errore esportazione: {exc}")

    def _on_import_urdf(self) -> None:
        d = gui.FileDialog(gui.FileDialog.OPEN, "Importa URDF", self.win.theme)
        d.add_filter(".urdf", "File URDF (*.urdf)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_import_urdf)
        self.win.show_dialog(d)

    def _do_import_urdf(self, path: str) -> None:
        self.win.close_dialog()
        try:
            self._save_undo_state()
            self._disconnect_tree_signals()
            self.tree = self.io.import_urdf(path)
            self._connect_tree_signals()
            self._selected = None
            self._refresh_all()
            self._status(f"URDF importato: {path}")
        except Exception as exc:
            log.error("Errore importazione URDF: %s", exc)
            self._status(f"Errore importazione: {exc}")

    def _on_export_csv(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Esporta CSV", self.win.theme)
        d.add_filter(".csv", "File CSV (*.csv)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_export_csv)
        self.win.show_dialog(d)

    def _do_export_csv(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".csv"):
                path += ".csv"
            self.io.export_csv(self.tree, path)
            self._status(f"CSV esportato: {path}")
        except Exception as exc:
            self._status(f"Errore esportazione: {exc}")

    def _on_import_csv(self) -> None:
        d = gui.FileDialog(gui.FileDialog.OPEN, "Importa CSV", self.win.theme)
        d.add_filter(".csv", "File CSV (*.csv)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_import_csv)
        self.win.show_dialog(d)

    def _do_import_csv(self, path: str) -> None:
        self.win.close_dialog()
        try:
            self._save_undo_state()
            self._disconnect_tree_signals()
            self.tree = self.io.import_csv(path)
            self._connect_tree_signals()
            self._selected = None
            self._refresh_all()
            self._status(f"CSV importato: {path}")
        except Exception as exc:
            self._status(f"Errore importazione: {exc}")

    def _on_export_yaml(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Esporta YAML", self.win.theme)
        d.add_filter(".yaml", "File YAML (*.yaml)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_export_yaml)
        self.win.show_dialog(d)

    def _do_export_yaml(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".yaml") and not path.endswith(".yml"):
                path += ".yaml"
            self.io.export_yaml(self.tree, path)
            self._status(f"YAML esportato: {path}")
        except ImportError as exc:
            self._status(f"PyYAML non installato: {exc}")
        except Exception as exc:
            self._status(f"Errore esportazione: {exc}")

    def _on_import_yaml(self) -> None:
        d = gui.FileDialog(gui.FileDialog.OPEN, "Importa YAML", self.win.theme)
        d.add_filter(".yaml", "File YAML (*.yaml)")
        d.add_filter(".yml", "File YAML (*.yml)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_import_yaml)
        self.win.show_dialog(d)

    def _do_import_yaml(self, path: str) -> None:
        self.win.close_dialog()
        try:
            self._save_undo_state()
            self._disconnect_tree_signals()
            self.tree = self.io.import_yaml(path)
            self._connect_tree_signals()
            self._selected = None
            self._refresh_all()
            self._status(f"YAML importato: {path}")
        except ImportError as exc:
            self._status(f"PyYAML non installato: {exc}")
        except Exception as exc:
            self._status(f"Errore importazione: {exc}")

    def _on_export_dh(self) -> None:
        d = gui.FileDialog(gui.FileDialog.SAVE, "Esporta DH Parameters", self.win.theme)
        d.add_filter(".csv", "File CSV (*.csv)")
        d.set_on_cancel(self.win.close_dialog)
        d.set_on_done(self._do_export_dh)
        self.win.show_dialog(d)

    def _do_export_dh(self, path: str) -> None:
        self.win.close_dialog()
        try:
            if not path.endswith(".csv"):
                path += ".csv"
            self.io.export_dh(self.tree, path)
            self._status(f"DH esportati: {path}")
        except Exception as exc:
            self._status(f"Errore esportazione: {exc}")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        log.info("Frame3D Manager avviato")
        gui.Application.instance.run()

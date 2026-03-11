"""
app.py
------
Applicazione principale: finestra Open3D con pannello laterale per la
gestione interattiva dei frame 3D.

Architettura
-----------
  - SceneRenderer: rendering 3D con highlight
  - PanelBuilder: costruzione pannello laterale (TreeView, editor, I/O)
  - UndoRedoManager: annulla/ripristina operazioni
  - IOHandler: salvataggio/caricamento (JSON, URDF, CSV, YAML, DH)
  - FrameTree → Observer pattern: notifica automatica dei cambiamenti

Layout
------
  ┌─────────────────────────────┬──────────────────────┐
  │                             │  ↩ Undo  ↪ Redo      │
  │      Scena 3D               │  Struttura TreeView   │
  │   (assi XYZ colorati,       │  [+ Nuovo] [✕ Rimuovi]│
  │    linee di connessione,    │  ── Modifica ──────── │
  │    evidenzia selezione)     │  Nome [Rinomina]      │
  │                             │  Parent               │
  │                             │  Traslazione X Y Z    │
  │                             │  Rotazione R P Y      │
  │                             │  [Applica]            │
  │                             │  ── T mondo (4×4) ──  │
  │                             │  ── I/O ────────────  │
  │                             │  JSON URDF CSV YAML DH│
  └─────────────────────────────┴──────────────────────┘

Scorciatoie Open3D standard nella vista 3D:
  - Tasto sinistro + trascina → rotazione
  - Tasto destro + trascina   → pan
  - Rotellina                 → zoom
  - R                         → reset camera
"""

from __future__ import annotations

from typing import Optional
import numpy as np
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from frame import Frame
from frame_tree import FrameTree
from io_handler import IOHandler
from scene_renderer import SceneRenderer
from panel_builder import PanelBuilder
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
        self._updating_ui: bool = False  # guard per evitare re-entrate

        # Scena dimostrativa o recovery da autosave
        if IOHandler.has_autosave():
            recovered = IOHandler.load_autosave()
            if recovered is not None:
                self.tree = recovered
                log.info("Sessione recuperata da autosave")
            else:
                self._build_demo_scene()
        else:
            self._build_demo_scene()

        # Salva stato iniziale per undo
        self.undo_mgr.save_state(self.tree.to_dict())

        # Connetti i segnali dell'albero
        self._connect_tree_signals()

        self._build_gui()

    # ------------------------------------------------------------------
    # Segnali Observer
    # ------------------------------------------------------------------

    def _connect_tree_signals(self) -> None:
        """Collega i segnali del FrameTree alla GUI."""
        self.tree.frame_added.connect(self._on_tree_changed)
        self.tree.frame_removed.connect(self._on_tree_changed)
        self.tree.frame_modified.connect(self._on_tree_changed)
        self.tree.tree_loaded.connect(self._on_tree_loaded)

    def _disconnect_tree_signals(self) -> None:
        """Scollega i segnali (utile prima di caricare un nuovo albero)."""
        self.tree.frame_added.clear()
        self.tree.frame_removed.clear()
        self.tree.frame_modified.clear()
        self.tree.tree_loaded.clear()

    def _on_tree_changed(self, name: str = "") -> None:
        """Callback generico: aggiorna scena e tree view dopo un cambiamento."""
        if not self._updating_ui:
            self._autosave()

    def _on_tree_loaded(self) -> None:
        """Callback per caricamento completo dell'albero."""
        pass  # il refresh viene fatto esplicitamente dopo il load

    # ------------------------------------------------------------------
    # Scena demo
    # ------------------------------------------------------------------

    def _build_demo_scene(self) -> None:
        """Popola l'albero con frame di esempio per mostrare le funzionalità."""
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

    # ------------------------------------------------------------------
    # Costruzione GUI
    # ------------------------------------------------------------------

    def _build_gui(self) -> None:
        app = gui.Application.instance
        app.initialize()

        self.win = app.create_window("Frame3D Manager", 1440, 900)
        em = self.win.theme.font_size

        # ── Vista 3D ──────────────────────────────────────────────────
        self._scene_widget = gui.SceneWidget()
        self._scene_widget.scene = rendering.Open3DScene(self.win.renderer)

        # ── SceneRenderer ─────────────────────────────────────────────
        self.renderer = SceneRenderer(self._scene_widget)
        self.renderer.setup_scene()

        # ── PanelBuilder ──────────────────────────────────────────────
        self.panel_builder = PanelBuilder()
        panel = self.panel_builder.build(em)

        # Connetti i callback
        self.panel_builder.wire_callbacks(
            on_tree_selected=self._on_tree_selected,
            on_add=self._on_click_add,
            on_remove=self._on_click_remove,
            on_rename=self._on_click_rename,
            on_apply=self._on_click_apply,
            on_combo_parent=self._on_combo_parent_changed,
            on_undo=self._on_undo,
            on_redo=self._on_redo,
            on_save_json=self._on_save_json,
            on_load_json=self._on_load_json,
            on_export_urdf=self._on_export_urdf,
            on_import_urdf=self._on_import_urdf,
            on_export_csv=self._on_export_csv,
            on_import_csv=self._on_import_csv,
            on_export_yaml=self._on_export_yaml,
            on_import_yaml=self._on_import_yaml,
            on_export_dh=self._on_export_dh,
        )

        # Connetti segnale undo/redo allo stato dei pulsanti
        self.undo_mgr.state_changed.connect(
            self.panel_builder.update_undo_redo_state
        )

        self.win.add_child(self._scene_widget)
        self.win.add_child(panel)
        self.win.set_on_layout(self._on_layout)

        # Primo rendering
        self._refresh_all()
        self.renderer.reset_camera()

    # ------------------------------------------------------------------
    # Layout responsivo
    # ------------------------------------------------------------------

    def _on_layout(self, ctx) -> None:
        r = self.win.content_rect
        em = self.win.theme.font_size
        panel_w = int(22 * em)
        self._scene_widget.frame = gui.Rect(
            r.x, r.y, r.width - panel_w, r.height
        )
        self.panel_builder.panel.frame = gui.Rect(
            r.x + r.width - panel_w, r.y, panel_w, r.height
        )

    # ------------------------------------------------------------------
    # Refresh centralizzato
    # ------------------------------------------------------------------

    def _refresh_all(self) -> None:
        """Aggiorna scena 3D e TreeView."""
        self.renderer.refresh_scene(self.tree, self._selected)
        self.panel_builder.refresh_tree(self.tree)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _save_undo_state(self) -> None:
        """Salva lo stato corrente prima di una modifica."""
        self.undo_mgr.save_state(self.tree.to_dict())

    def _autosave(self) -> None:
        """Autosave asincrono."""
        try:
            IOHandler.autosave(self.tree)
        except Exception as exc:
            log.warning("Autosave fallito: %s", exc)

    def _status(self, msg: str) -> None:
        """Aggiorna la barra di stato."""
        self.panel_builder.set_status(msg)
        log.info("Status: %s", msg)

    # ------------------------------------------------------------------
    # Callbacks: selezione frame
    # ------------------------------------------------------------------

    def _on_tree_selected(self, item_id: int) -> None:
        """Callback per selezione nel TreeView."""
        name = self.panel_builder.get_name_from_tree_item(item_id)
        if name:
            self._selected = name
            self._sync_ui_from_frame(name)
            self.renderer.refresh_scene(self.tree, self._selected)

    def _sync_ui_from_frame(self, name: str) -> None:
        """Aggiorna i campi dell'editor con i dati del frame selezionato."""
        if name not in self.tree.frames:
            return
        self._updating_ui = True

        pb = self.panel_builder
        frame = self.tree.frames[name]
        pb.edit_name.text_value = name

        # Parent combo
        all_names = self.tree.get_all_names()
        parent = frame.parent or "world"
        if parent in all_names:
            pb.combo_parent.selected_index = all_names.index(parent)

        # Traslazione
        t = frame.translation
        pb.ne_tx.double_value = float(t[0])
        pb.ne_ty.double_value = float(t[1])
        pb.ne_tz.double_value = float(t[2])

        # Rotazione
        rpy = frame.get_rotation_euler(degrees=True)
        pb.ne_roll.double_value = float(rpy[0])
        pb.ne_pitch.double_value = float(rpy[1])
        pb.ne_yaw.double_value = float(rpy[2])

        # Matrice mondiale 4×4
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
    # Callbacks: modifica frame
    # ------------------------------------------------------------------

    def _on_combo_parent_changed(self, val: str, idx: int) -> None:
        pass  # applicato solo al click su "Applica"

    def _on_click_apply(self) -> None:
        """Applica traslazione, rotazione e parent al frame selezionato."""
        if not self._selected or self._selected == "world":
            self._status("Seleziona un frame non-world da modificare.")
            return

        pb = self.panel_builder

        # Validazione
        frame = self.tree.frames[self._selected]

        # Salva stato per undo
        self._save_undo_state()

        # Traslazione
        frame.translation = np.array([
            pb.ne_tx.double_value,
            pb.ne_ty.double_value,
            pb.ne_tz.double_value,
        ])

        # Rotazione
        frame.set_rotation_euler(
            pb.ne_roll.double_value,
            pb.ne_pitch.double_value,
            pb.ne_yaw.double_value,
            degrees=True,
        )

        # Parent (solo se non crea un ciclo)
        all_names = self.tree.get_all_names()
        idx = pb.combo_parent.selected_index
        if 0 <= idx < len(all_names):
            new_parent = all_names[idx]
            if new_parent != self._selected:
                if not self.tree.would_create_cycle(self._selected, new_parent):
                    frame.parent = new_parent
                else:
                    self._status("Errore: il parent scelto creerebbe un ciclo!")
                    return

        self._refresh_all()
        self._sync_ui_from_frame(self._selected)
        self._status(f"Frame '{self._selected}' aggiornato.")

    def _on_click_add(self) -> None:
        """Apre un dialog per creare un nuovo frame."""
        dlg = gui.Dialog("Nuovo Frame")
        body = gui.Vert(10, gui.Margins(10, 10, 10, 10))
        body.add_child(gui.Label("Nome del nuovo frame:"))
        name_field = gui.TextEdit()
        name_field.text_value = f"frame_{len(self.tree.frames)}"
        body.add_child(name_field)

        btns = gui.Horiz(5)
        ok_btn = gui.Button("OK")
        ca_btn = gui.Button("Annulla")
        btns.add_child(ok_btn)
        btns.add_child(ca_btn)
        body.add_child(btns)
        dlg.add_child(body)

        def _ok() -> None:
            n = name_field.text_value.strip()

            # Validazione nome
            if not Frame.validate_name(n):
                self._status(
                    f"Errore: nome '{n}' non valido. "
                    "Usa solo lettere, cifre e underscore."
                )
                self.win.close_dialog()
                return

            if n and n not in self.tree.frames:
                self._save_undo_state()
                self.tree.add_frame(Frame(n, parent="world"))
                self._refresh_all()
                self._status(f"Frame '{n}' aggiunto.")
            elif n in self.tree.frames:
                self._status(f"Errore: il nome '{n}' esiste già.")
            self.win.close_dialog()

        ok_btn.set_on_clicked(_ok)
        ca_btn.set_on_clicked(self.win.close_dialog)
        self.win.show_dialog(dlg)

    def _on_click_remove(self) -> None:
        """Rimuove il frame selezionato."""
        if not self._selected or self._selected == "world":
            self._status("Impossibile rimuovere il frame 'world'.")
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
        """Rinomina il frame selezionato."""
        if not self._selected or self._selected == "world":
            self._status("Impossibile rinominare il frame 'world'.")
            return

        new_name = self.panel_builder.edit_name.text_value.strip()

        # Validazione
        if not Frame.validate_name(new_name):
            self._status(
                f"Errore: nome '{new_name}' non valido. "
                "Usa solo lettere, cifre e underscore."
            )
            return

        if new_name == self._selected:
            self._status("Il nome non è cambiato.")
            return

        if new_name in self.tree.frames:
            self._status(f"Errore: il nome '{new_name}' esiste già.")
            return

        old_name = self._selected
        self._save_undo_state()

        if self.tree.rename_frame(old_name, new_name):
            self._selected = new_name
            self._refresh_all()
            self._sync_ui_from_frame(new_name)
            self._status(f"Frame rinominato: '{old_name}' → '{new_name}'.")
        else:
            self._status("Errore nella rinomina del frame.")

    # ------------------------------------------------------------------
    # Callbacks: Undo / Redo
    # ------------------------------------------------------------------

    def _on_undo(self) -> None:
        """Annulla l'ultima operazione."""
        state = self.undo_mgr.undo()
        if state is not None:
            self._restore_tree_from_dict(state)
            self._status("Undo eseguito.")
        else:
            self._status("Nessuna operazione da annullare.")

    def _on_redo(self) -> None:
        """Ripristina l'ultima operazione annullata."""
        state = self.undo_mgr.redo()
        if state is not None:
            self._restore_tree_from_dict(state)
            self._status("Redo eseguito.")
        else:
            self._status("Nessuna operazione da ripristinare.")

    def _restore_tree_from_dict(self, state: dict) -> None:
        """Ricostruisce il FrameTree da un dizionario (undo/redo)."""
        self._disconnect_tree_signals()
        self.tree = FrameTree.from_dict(state)
        self._connect_tree_signals()
        self._selected = None
        self.panel_builder.edit_name.text_value = ""
        self.panel_builder.lbl_T.text = "( seleziona un frame )"
        self._refresh_all()

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
            log.error("Errore esportazione CSV: %s", exc)
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
            log.error("Errore importazione CSV: %s", exc)
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
            log.error("Errore esportazione YAML: %s", exc)
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
            log.error("Errore importazione YAML: %s", exc)
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
            self._status(f"DH parameters esportati: {path}")
        except Exception as exc:
            log.error("Errore esportazione DH: %s", exc)
            self._status(f"Errore esportazione: {exc}")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Avvia il loop principale dell'applicazione."""
        log.info("Frame3D Manager avviato")
        gui.Application.instance.run()

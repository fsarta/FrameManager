"""
scene_renderer.py
-----------------
Gestisce il rendering della scena 3D: assi, link e label.

Estratto da app.py per separare responsabilità.
"""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

import numpy as np
import open3d as o3d
import open3d.visualization.gui as gui
import open3d.visualization.rendering as rendering

from logger import get_logger

if TYPE_CHECKING:
    from frame_tree import FrameTree

log = get_logger("scene_renderer")

# Dimensione degli assi del sistema di riferimento (in metri)
AXIS_SIZE: float = 0.4

# Colore delle linee di collegamento padre→figlio
LINK_COLOR = [0.95, 0.80, 0.10]

# Colore highlight per il frame selezionato
HIGHLIGHT_COLOR = [0.0, 0.85, 1.0, 0.25]  # ciano semi-trasparente

# Colore di sfondo della scena
BG_COLOR = [0.10, 0.10, 0.16, 1.0]


class SceneRenderer:
    """
    Gestisce la visualizzazione 3D dei frame, con highlight per la selezione.

    Attributes
    ----------
    scene_widget : gui.SceneWidget
        Il widget della scena 3D (creato esternamente da app.py).
    """

    def __init__(self, scene_widget: gui.SceneWidget) -> None:
        self._scene_widget = scene_widget
        self._labels_3d: List = []
        self._selected: Optional[str] = None

    def setup_scene(self) -> None:
        """Configura le impostazioni iniziali della scena (background, ground plane, luce)."""
        s = self._scene_widget.scene
        s.set_background(BG_COLOR)
        s.show_ground_plane(True, rendering.Scene.GroundPlane.XZ)
        s.scene.enable_sun_light(True)

    def refresh_scene(
        self, tree: "FrameTree", selected: Optional[str] = None
    ) -> None:
        """
        Ri-renderizza l'intera scena: assi, link e label.

        Parameters
        ----------
        tree : FrameTree
            L'albero dei frame da visualizzare.
        selected : str | None
            Nome del frame selezionato (verrà evidenziato).
        """
        self._selected = selected
        s = self._scene_widget.scene
        s.clear_geometry()

        # Rimuovi le label 3D precedenti
        for lbl in self._labels_3d:
            try:
                self._scene_widget.remove_3d_label(lbl)
            except Exception:
                log.debug("Impossibile rimuovere label 3D")
        self._labels_3d.clear()

        # Materiali
        mat_mesh = rendering.MaterialRecord()
        mat_mesh.shader = "defaultLit"

        mat_line = rendering.MaterialRecord()
        mat_line.shader = "unlitLine"
        mat_line.line_width = 2.5

        mat_highlight = rendering.MaterialRecord()
        mat_highlight.shader = "defaultUnlit"

        for name, frame in tree.frames.items():
            try:
                T = tree.get_world_transform(name)
            except RuntimeError as exc:
                log.error("Errore nel calcolo della trasformazione per '%s': %s",
                          name, exc)
                continue

            is_selected = (name == selected)

            # ── Sistema di riferimento (assi X=rosso, Y=verde, Z=blu) ──
            if name == "world":
                size = AXIS_SIZE * 1.4
            elif is_selected:
                size = AXIS_SIZE * 1.6  # più grande se selezionato
            else:
                size = AXIS_SIZE

            mesh = o3d.geometry.TriangleMesh.create_coordinate_frame(
                size=size, origin=[0.0, 0.0, 0.0]
            )
            mesh.transform(T)
            s.add_geometry(f"frame_{name}", mesh, mat_mesh)

            # ── Sfera highlight per il frame selezionato ──
            if is_selected:
                sphere = o3d.geometry.TriangleMesh.create_sphere(
                    radius=size * 0.35
                )
                sphere.paint_uniform_color(HIGHLIGHT_COLOR[:3])
                sphere.compute_vertex_normals()
                sphere.transform(T)
                s.add_geometry(f"highlight_{name}", sphere, mat_highlight)

            # ── Linea di collegamento al frame padre ──
            if frame.parent and frame.parent in tree.frames:
                try:
                    T_parent = tree.get_world_transform(frame.parent)
                    p0 = T_parent[:3, 3]
                    p1 = T[:3, 3]
                    ls = o3d.geometry.LineSet(
                        points=o3d.utility.Vector3dVector([p0, p1]),
                        lines=o3d.utility.Vector2iVector([[0, 1]]),
                    )
                    ls.colors = o3d.utility.Vector3dVector([LINK_COLOR])
                    s.add_geometry(f"link_{frame.parent}_{name}", ls, mat_line)
                except RuntimeError:
                    pass

            # ── Etichetta 3D con il nome del frame ──
            label_pos = T[:3, 3] + T[:3, 2] * size * 0.2
            try:
                lbl_obj = self._scene_widget.add_3d_label(label_pos, name)
                self._labels_3d.append(lbl_obj)
            except Exception:
                log.debug("add_3d_label non disponibile per '%s'", name)

    def reset_camera(self) -> None:
        """Posiziona la camera per inquadrare tutti i frame."""
        bbox = self._scene_widget.scene.bounding_box
        if bbox.is_empty():
            bbox = o3d.geometry.AxisAlignedBoundingBox(
                min_bound=np.array([-2.0, -2.0, -2.0]),
                max_bound=np.array([2.0, 2.0, 2.0]),
            )
        self._scene_widget.setup_camera(60, bbox, bbox.get_center())

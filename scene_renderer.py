"""
scene_renderer.py
-----------------
Gestisce il rendering della scena 3D: assi, link, label, nastri e mesh.

Estratto da app.py per separare responsabilità.
"""

from __future__ import annotations

from typing import Dict, List, Optional, TYPE_CHECKING

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
    Gestisce la visualizzazione 3D dei frame, nastri e mesh,
    con highlight per la selezione.

    Attributes
    ----------
    scene_widget : gui.SceneWidget
        Il widget della scena 3D (creato esternamente da app.py).
    """

    def __init__(self, scene_widget: gui.SceneWidget) -> None:
        self._scene_widget = scene_widget
        self._labels_3d: List = []
        self._selected: Optional[str] = None
        # Mesh importate: {frame_name: (mesh, file_path)}
        self._attached_meshes: Dict[str, tuple] = {}

    def setup_scene(self) -> None:
        """Configura le impostazioni iniziali della scena."""
        s = self._scene_widget.scene
        s.set_background(BG_COLOR)
        s.show_ground_plane(True, rendering.Scene.GroundPlane.XZ)
        s.scene.enable_sun_light(True)

    # ------------------------------------------------------------------
    # Refresh completo
    # ------------------------------------------------------------------

    def refresh_scene(
        self, tree: "FrameTree", selected: Optional[str] = None
    ) -> None:
        """
        Ri-renderizza l'intera scena: assi, link, label, nastri e mesh.
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

        # ── Frame ─────────────────────────────────────────────────────
        for name, frame in tree.frames.items():
            try:
                T = tree.get_world_transform(name)
            except RuntimeError as exc:
                log.error("Errore trasformazione '%s': %s", name, exc)
                continue

            is_selected = (name == selected)

            # Assi
            if name == "world":
                size = AXIS_SIZE * 1.4
            elif is_selected:
                size = AXIS_SIZE * 1.6
            else:
                size = AXIS_SIZE

            mesh_axes = o3d.geometry.TriangleMesh.create_coordinate_frame(
                size=size, origin=[0.0, 0.0, 0.0]
            )
            mesh_axes.transform(T)
            s.add_geometry(f"frame_{name}", mesh_axes, mat_mesh)

            # Sfera highlight
            if is_selected:
                sphere = o3d.geometry.TriangleMesh.create_sphere(
                    radius=size * 0.35
                )
                sphere.paint_uniform_color(HIGHLIGHT_COLOR[:3])
                sphere.compute_vertex_normals()
                sphere.transform(T)
                s.add_geometry(f"highlight_{name}", sphere, mat_highlight)

            # Linea di collegamento al padre
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

            # Label 3D
            label_pos = T[:3, 3] + T[:3, 2] * size * 0.2
            try:
                lbl_obj = self._scene_widget.add_3d_label(label_pos, name)
                self._labels_3d.append(lbl_obj)
            except Exception:
                log.debug("add_3d_label non disponibile per '%s'", name)

            # Mesh importata attaccata a questo frame
            if name in self._attached_meshes:
                imported_mesh, _ = self._attached_meshes[name]
                m = o3d.geometry.TriangleMesh(imported_mesh)
                m.transform(T)
                mat_imported = rendering.MaterialRecord()
                mat_imported.shader = "defaultLit"
                s.add_geometry(f"mesh_{name}", m, mat_imported)

        # ── Nastri ────────────────────────────────────────────────────
        for rname, ribbon in tree.ribbons.items():
            self._render_ribbon(tree, ribbon, s)

    # ------------------------------------------------------------------
    # Rendering nastri
    # ------------------------------------------------------------------

    def _render_ribbon(
        self, tree: "FrameTree", ribbon, scene
    ) -> None:
        """Renderizza un nastro come box 3D colorato."""
        # Calcola la trasformazione world del frame padre
        parent = ribbon.parent_frame
        if parent not in tree.frames:
            parent = "world"

        try:
            T_parent = tree.get_world_transform(parent)
        except RuntimeError:
            T_parent = np.eye(4)

        # Trasformazione locale del nastro
        T_local = ribbon.transform
        T_world = T_parent @ T_local

        # Crea il box centrato
        box = o3d.geometry.TriangleMesh.create_box(
            width=ribbon.width,
            height=ribbon.height,
            depth=ribbon.length,
        )
        # Centra il box (create_box parte da [0,0,0])
        box.translate([
            -ribbon.width / 2.0,
            -ribbon.height / 2.0,
            -ribbon.length / 2.0,
        ])
        box.paint_uniform_color(ribbon.color)
        box.compute_vertex_normals()
        box.transform(T_world)

        # Materiale
        mat = rendering.MaterialRecord()
        mat.shader = "defaultLit"
        mat.base_color = [
            ribbon.color[0], ribbon.color[1], ribbon.color[2],
            ribbon.opacity,
        ]

        scene.add_geometry(f"ribbon_{ribbon.name}", box, mat)

        # Label
        label_pos = T_world[:3, 3] + np.array([0, ribbon.height * 2, 0])
        try:
            lbl = self._scene_widget.add_3d_label(label_pos, f"🔲 {ribbon.name}")
            self._labels_3d.append(lbl)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Mesh importate
    # ------------------------------------------------------------------

    def attach_mesh(self, frame_name: str, file_path: str) -> bool:
        """
        Carica e attacca un file mesh (.stl, .obj, .ply) a un frame.

        Returns
        -------
        bool
            True se il caricamento ha avuto successo.
        """
        try:
            mesh = o3d.io.read_triangle_mesh(file_path)
            if not mesh.has_vertices():
                log.warning("Mesh vuota: %s", file_path)
                return False
            mesh.compute_vertex_normals()
            self._attached_meshes[frame_name] = (mesh, file_path)
            log.info("Mesh '%s' attaccata al frame '%s'", file_path, frame_name)
            return True
        except Exception as exc:
            log.error("Errore nel caricamento mesh: %s", exc)
            return False

    def detach_mesh(self, frame_name: str) -> None:
        """Rimuove la mesh attaccata a un frame."""
        self._attached_meshes.pop(frame_name, None)

    def get_attached_mesh_path(self, frame_name: str) -> Optional[str]:
        """Restituisce il path della mesh attaccata, o None."""
        if frame_name in self._attached_meshes:
            return self._attached_meshes[frame_name][1]
        return None

    # ------------------------------------------------------------------
    # Camera
    # ------------------------------------------------------------------

    def reset_camera(self) -> None:
        """Posiziona la camera per inquadrare tutti i frame."""
        bbox = self._scene_widget.scene.bounding_box
        if bbox.is_empty():
            bbox = o3d.geometry.AxisAlignedBoundingBox(
                min_bound=np.array([-2.0, -2.0, -2.0]),
                max_bound=np.array([2.0, 2.0, 2.0]),
            )
        self._scene_widget.setup_camera(60, bbox, bbox.get_center())

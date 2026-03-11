"""
io_handler.py
-------------
Import / Export del FrameTree verso:
  - JSON  (formato nativo del progetto)
  - URDF  (subset fixed-joint, compatibile con ROS/robotica)
  - CSV   (tabellare: name, parent, tx, ty, tz, roll, pitch, yaw)
  - YAML  (struttura gerarchica leggibile)
  - DH    (parametri Denavit-Hartenberg, solo export)

Funzionalità aggiuntive:
  - Autosave / recovery
"""

from __future__ import annotations

import json
import csv
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from frame import Frame
from frame_tree import FrameTree
from logger import get_logger

log = get_logger("io_handler")

AUTOSAVE_DIR = Path.home() / ".frame3d"
AUTOSAVE_FILE = AUTOSAVE_DIR / "autosave.json"


class IOHandler:
    """
    Gestisce la lettura e la scrittura del FrameTree su file.

    Formati supportati: JSON, URDF, CSV, YAML, DH (export only).
    """

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    @staticmethod
    def save_json(tree: FrameTree, path: str) -> None:
        """Salva il FrameTree in un file JSON indentato."""
        data = tree.to_dict()
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        log.info("JSON salvato: %s", path)

    @staticmethod
    def load_json(path: str) -> FrameTree:
        """Carica un FrameTree da un file JSON salvato con save_json."""
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        log.info("JSON caricato: %s", path)
        return FrameTree.from_dict(data)

    # ------------------------------------------------------------------
    # Autosave / Recovery
    # ------------------------------------------------------------------

    @staticmethod
    def autosave(tree: FrameTree) -> None:
        """
        Salva automaticamente lo stato in ~/.frame3d/autosave.json.
        Chiamato ad ogni modifica per consentire il recovery in caso di crash.
        """
        try:
            AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
            data = tree.to_dict()
            data["_autosave"] = True
            with open(AUTOSAVE_FILE, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            log.debug("Autosave completato: %s", AUTOSAVE_FILE)
        except OSError as exc:
            log.warning("Autosave fallito: %s", exc)

    @staticmethod
    def has_autosave() -> bool:
        """Verifica se esiste un file di autosave."""
        return AUTOSAVE_FILE.is_file()

    @staticmethod
    def load_autosave() -> Optional[FrameTree]:
        """
        Carica il FrameTree dall'autosave se disponibile.

        Returns
        -------
        FrameTree | None
            L'albero recuperato, o None se non disponibile.
        """
        if not AUTOSAVE_FILE.is_file():
            return None
        try:
            with open(AUTOSAVE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            log.info("Autosave caricato: %s", AUTOSAVE_FILE)
            return FrameTree.from_dict(data)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("Errore nel caricamento autosave: %s", exc)
            return None

    @staticmethod
    def clear_autosave() -> None:
        """Rimuove il file di autosave."""
        try:
            AUTOSAVE_FILE.unlink(missing_ok=True)
            log.debug("Autosave rimosso")
        except OSError:
            pass

    # ------------------------------------------------------------------
    # URDF — Export
    # ------------------------------------------------------------------

    @staticmethod
    def export_urdf(tree: FrameTree, path: str) -> None:
        """
        Esporta il FrameTree come file URDF (fixed joints).

        Il file prodotto è valido per ROS/MoveIt e qualsiasi tool
        compatibile URDF. Ogni relazione padre→figlio genera un
        <joint type="fixed"> con l'origin corrispondente.
        """
        from scipy.spatial.transform import Rotation
        import xml.etree.ElementTree as ET

        robot = ET.Element("robot", name="frame_tree")

        # Un <link> per ciascun frame
        for name in tree.get_all_names():
            ET.SubElement(robot, "link", name=name)

        # Un <joint> per ciascuna relazione padre→figlio
        for name, frame in tree.frames.items():
            if name == "world" or not frame.parent:
                continue
            parent = frame.parent or "world"
            joint = ET.SubElement(
                robot,
                "joint",
                name=f"joint_{parent}_to_{name}",
                type="fixed",
            )
            ET.SubElement(joint, "parent", link=parent)
            ET.SubElement(joint, "child", link=name)

            rpy = Rotation.from_matrix(frame.rotation).as_euler("xyz", degrees=False)
            t = frame.translation
            ET.SubElement(
                joint,
                "origin",
                xyz=f"{t[0]:.6f} {t[1]:.6f} {t[2]:.6f}",
                rpy=f"{rpy[0]:.6f} {rpy[1]:.6f} {rpy[2]:.6f}",
            )

        etree = ET.ElementTree(robot)
        try:
            ET.indent(etree, space="  ")  # Python 3.9+
        except AttributeError:
            pass  # versioni più vecchie: nessun indenting
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0"?>\n')
            etree.write(fh, encoding="unicode")
        log.info("URDF esportato: %s", path)

    # ------------------------------------------------------------------
    # URDF — Import
    # ------------------------------------------------------------------

    @staticmethod
    def import_urdf(path: str) -> FrameTree:
        """
        Importa un file URDF come FrameTree.

        Per ogni <joint> viene creato un frame con il nome del link figlio.
        I joint mobili (revolute, prismatic, …) vengono segnalati con un
        warning e trattati come fixed: viene usata solo la loro <origin>.
        """
        from scipy.spatial.transform import Rotation
        import xml.etree.ElementTree as ET

        root_el = ET.parse(path).getroot()
        tree = FrameTree()

        joint_data: Dict[str, Dict[str, Any]] = {}
        for joint in root_el.findall("joint"):
            parent_el = joint.find("parent")
            child_el = joint.find("child")
            origin_el = joint.find("origin")

            if parent_el is None or child_el is None:
                continue

            # ── Warning per joint non-fixed ──
            joint_type = joint.get("type", "fixed")
            joint_name = joint.get("name", "?")
            if joint_type != "fixed":
                log.warning(
                    "URDF import: joint '%s' è di tipo '%s' (non fixed). "
                    "Verrà trattato come fixed, la posa dinamica è ignorata.",
                    joint_name, joint_type
                )

            parent_name: str = parent_el.get("link", "world")
            child_name: Optional[str] = child_el.get("link")
            if not child_name:
                continue

            t: NDArray[np.float64] = np.zeros(3)
            R: NDArray[np.float64] = np.eye(3)
            if origin_el is not None:
                xyz_str = origin_el.get("xyz", "0 0 0")
                rpy_str = origin_el.get("rpy", "0 0 0")
                t = np.fromstring(xyz_str, sep=" ")
                rpy = np.fromstring(rpy_str, sep=" ")
                R = Rotation.from_euler("xyz", rpy).as_matrix()

            joint_data[child_name] = {
                "parent": parent_name,
                "translation": t,
                "rotation": R,
            }

        # Inserzione topologica: i padri prima dei figli
        added: set[str] = {"world"}
        remaining: List[tuple[str, Dict[str, Any]]] = list(joint_data.items())
        max_iters = max(len(remaining) ** 2 + 10, 100)
        iters = 0
        while remaining and iters < max_iters:
            iters += 1
            child_name, info = remaining.pop(0)
            parent_name = info["parent"]
            if parent_name in added or parent_name not in joint_data:
                actual_parent = parent_name if parent_name in tree.frames else "world"
                f = Frame(
                    child_name,
                    parent=actual_parent,
                    translation=info["translation"],
                    rotation=info["rotation"],
                )
                tree.add_frame(f)
                added.add(child_name)
            else:
                remaining.append((child_name, info))  # riprova

        log.info("URDF importato: %s (%d frame)", path, len(tree))
        return tree

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    @staticmethod
    def export_csv(tree: FrameTree, path: str) -> None:
        """
        Esporta il FrameTree in formato CSV.

        Colonne: name, parent, tx, ty, tz, roll_deg, pitch_deg, yaw_deg
        """
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "name", "parent", "tx", "ty", "tz",
                "roll_deg", "pitch_deg", "yaw_deg"
            ])
            for name, frame in tree.frames.items():
                if name == "world":
                    continue
                rpy = frame.get_rotation_euler(degrees=True)
                t = frame.translation
                writer.writerow([
                    name, frame.parent or "world",
                    f"{t[0]:.6f}", f"{t[1]:.6f}", f"{t[2]:.6f}",
                    f"{rpy[0]:.4f}", f"{rpy[1]:.4f}", f"{rpy[2]:.4f}",
                ])
        log.info("CSV esportato: %s", path)

    @staticmethod
    def import_csv(path: str) -> FrameTree:
        """
        Importa un FrameTree da un file CSV.

        Il file deve avere le colonne:
        name, parent, tx, ty, tz, roll_deg, pitch_deg, yaw_deg
        """
        tree = FrameTree()
        with open(path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows: List[Dict[str, str]] = list(reader)

        # Inserzione topologica
        added: set[str] = {"world"}
        remaining = list(rows)
        max_iters = max(len(remaining) ** 2 + 10, 100)
        iters = 0
        while remaining and iters < max_iters:
            iters += 1
            row = remaining.pop(0)
            parent = row.get("parent", "world") or "world"
            if parent in added:
                f = Frame(row["name"], parent=parent)
                f.translation = np.array([
                    float(row["tx"]), float(row["ty"]), float(row["tz"])
                ])
                f.set_rotation_euler(
                    float(row["roll_deg"]),
                    float(row["pitch_deg"]),
                    float(row["yaw_deg"]),
                    degrees=True,
                )
                tree.add_frame(f)
                added.add(f.name)
            else:
                remaining.append(row)

        log.info("CSV importato: %s (%d frame)", path, len(tree))
        return tree

    # ------------------------------------------------------------------
    # YAML
    # ------------------------------------------------------------------

    @staticmethod
    def export_yaml(tree: FrameTree, path: str) -> None:
        """
        Esporta il FrameTree in formato YAML leggibile.

        Richiede PyYAML (pip install pyyaml).
        """
        try:
            import yaml
        except ImportError:
            log.error("PyYAML non installato. Installa con: pip install pyyaml")
            raise ImportError(
                "PyYAML è richiesto per l'export YAML. "
                "Installa con: pip install pyyaml"
            )

        data: Dict[str, Any] = {"frames": []}
        for name, frame in tree.frames.items():
            if name == "world":
                continue
            rpy = frame.get_rotation_euler(degrees=True).tolist()
            data["frames"].append({
                "name": name,
                "parent": frame.parent or "world",
                "translation": {
                    "x": round(float(frame.translation[0]), 6),
                    "y": round(float(frame.translation[1]), 6),
                    "z": round(float(frame.translation[2]), 6),
                },
                "rotation_euler_xyz_deg": {
                    "roll": round(rpy[0], 4),
                    "pitch": round(rpy[1], 4),
                    "yaw": round(rpy[2], 4),
                },
            })

        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True,
                      sort_keys=False)
        log.info("YAML esportato: %s", path)

    @staticmethod
    def import_yaml(path: str) -> FrameTree:
        """
        Importa un FrameTree da un file YAML.

        Richiede PyYAML (pip install pyyaml).
        """
        try:
            import yaml
        except ImportError:
            log.error("PyYAML non installato.")
            raise ImportError(
                "PyYAML è richiesto per l'import YAML. "
                "Installa con: pip install pyyaml"
            )

        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        tree = FrameTree()
        frames_data = data.get("frames", [])

        # Inserzione topologica
        added: set[str] = {"world"}
        remaining = list(frames_data)
        max_iters = max(len(remaining) ** 2 + 10, 100)
        iters = 0
        while remaining and iters < max_iters:
            iters += 1
            fd = remaining.pop(0)
            parent = fd.get("parent", "world") or "world"
            if parent in added:
                name = fd["name"]
                t = fd.get("translation", {})
                r = fd.get("rotation_euler_xyz_deg", {})
                f = Frame(name, parent=parent)
                f.translation = np.array([
                    float(t.get("x", 0)),
                    float(t.get("y", 0)),
                    float(t.get("z", 0)),
                ])
                f.set_rotation_euler(
                    float(r.get("roll", 0)),
                    float(r.get("pitch", 0)),
                    float(r.get("yaw", 0)),
                    degrees=True,
                )
                tree.add_frame(f)
                added.add(name)
            else:
                remaining.append(fd)

        log.info("YAML importato: %s (%d frame)", path, len(tree))
        return tree

    # ------------------------------------------------------------------
    # DH Parameters (Export only)
    # ------------------------------------------------------------------

    @staticmethod
    def export_dh(tree: FrameTree, path: str) -> None:
        """
        Esporta i parametri Denavit-Hartenberg (standard) in formato CSV.

        Per ogni frame non-world calcola i parametri DH rispetto al padre:
          - a     : distanza lungo X_i (traslazione lungo l'asse X locale)
          - alpha  : rotazione attorno a X_i
          - d     : distanza lungo Z_{i-1}
          - theta : rotazione attorno a Z_{i-1}

        Nota: i parametri DH sono un'approssimazione valida per catene
        cinematiche seriali; per alberi generici sono solo indicativi.

        Colonne: name, parent, a, alpha_deg, d, theta_deg
        """
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "name", "parent", "a", "alpha_deg", "d", "theta_deg"
            ])
            for name, frame in tree.frames.items():
                if name == "world":
                    continue
                T = frame.transform
                # Estrai parametri DH standard dalla matrice 4x4
                # d = tz, theta = atan2(r10, r00), a = tx, alpha = atan2(r21, r22)
                d = float(T[2, 3])
                a = math.sqrt(float(T[0, 3]) ** 2 + float(T[1, 3]) ** 2)
                theta = math.degrees(math.atan2(float(T[1, 0]), float(T[0, 0])))
                alpha = math.degrees(math.atan2(float(T[2, 1]), float(T[2, 2])))

                writer.writerow([
                    name, frame.parent or "world",
                    f"{a:.6f}", f"{alpha:.4f}", f"{d:.6f}", f"{theta:.4f}",
                ])
        log.info("DH parameters esportati: %s", path)

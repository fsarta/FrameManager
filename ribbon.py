"""
ribbon.py
---------
Rappresenta un nastro/conveyor 3D con dimensioni, posizione,
orientamento e colore personalizzabili.

Un Ribbon è sempre associato a un frame padre ed è posizionato
con un offset (traslazione + rotazione) rispetto ad esso.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from logger import get_logger

log = get_logger("ribbon")

_VALID_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Colori predefiniti per i nastri
RIBBON_PRESETS: Dict[str, List[float]] = {
    "grigio":   [0.60, 0.60, 0.60],
    "blu":      [0.20, 0.40, 0.85],
    "verde":    [0.25, 0.75, 0.30],
    "rosso":    [0.85, 0.25, 0.20],
    "arancio":  [0.95, 0.60, 0.10],
    "ciano":    [0.15, 0.80, 0.80],
    "viola":    [0.60, 0.30, 0.80],
}


class Ribbon:
    """
    Nastro/conveyor 3D con dimensioni e trasformazione personalizzabili.

    Attributi
    ---------
    name : str
        Nome univoco del nastro.
    parent_frame : str
        Nome del frame a cui è associato.
    width : float
        Larghezza del nastro (lungo X locale), in metri.
    length : float
        Lunghezza del nastro (lungo Y locale), in metri.
    height : float
        Altezza/spessore del nastro (lungo Z locale), in metri.
    translation : NDArray, shape (3,)
        Offset rispetto al frame padre.
    rotation : NDArray, shape (3, 3)
        Matrice di rotazione rispetto al frame padre.
    color : list[float], len 3
        Colore RGB [0-1].
    opacity : float
        Opacità [0-1], 1 = opaco.
    """

    def __init__(
        self,
        name: str,
        parent_frame: str = "world",
        width: float = 1.0,
        length: float = 2.0,
        height: float = 0.05,
        translation: Optional[NDArray[np.float64] | Sequence[float]] = None,
        rotation: Optional[NDArray[np.float64]] = None,
        color: Optional[List[float]] = None,
        opacity: float = 0.75,
    ) -> None:
        self.name = name
        self.parent_frame = parent_frame
        self.width = max(0.001, width)
        self.length = max(0.001, length)
        self.height = max(0.001, height)
        self.translation: NDArray[np.float64] = (
            np.array(translation, dtype=float)
            if translation is not None
            else np.zeros(3)
        )
        self.rotation: NDArray[np.float64] = (
            np.array(rotation, dtype=float)
            if rotation is not None
            else np.eye(3)
        )
        self.color = color if color is not None else [0.60, 0.60, 0.60]
        self.opacity = max(0.0, min(1.0, opacity))

    # ------------------------------------------------------------------
    # Validazione
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name(name: str) -> bool:
        """Valida il nome del nastro (stesse regole dei frame)."""
        return bool(_VALID_NAME_RE.match(name))

    # ------------------------------------------------------------------
    # Trasformazione
    # ------------------------------------------------------------------

    @property
    def transform(self) -> NDArray[np.float64]:
        """Matrice 4×4 di trasformazione locale (offset dal frame padre)."""
        T: NDArray[np.float64] = np.eye(4)
        T[:3, :3] = self.rotation
        T[:3, 3] = self.translation
        return T

    def set_rotation_euler(
        self, roll: float, pitch: float, yaw: float, degrees: bool = True
    ) -> None:
        """Imposta la rotazione tramite angoli di Eulero XYZ."""
        self.rotation = Rotation.from_euler(
            "xyz", [roll, pitch, yaw], degrees=degrees
        ).as_matrix()

    def get_rotation_euler(self, degrees: bool = True) -> NDArray[np.float64]:
        """Restituisce [roll, pitch, yaw] come array shape (3,)."""
        return Rotation.from_matrix(self.rotation).as_euler("xyz", degrees=degrees)

    # ------------------------------------------------------------------
    # Serializzazione
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        rpy = self.get_rotation_euler(degrees=True).tolist()
        return {
            "name": self.name,
            "parent_frame": self.parent_frame,
            "width": self.width,
            "length": self.length,
            "height": self.height,
            "translation": self.translation.tolist(),
            "rotation_euler_xyz_deg": rpy,
            "color": self.color,
            "opacity": self.opacity,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Ribbon:
        r = cls(
            name=d["name"],
            parent_frame=d.get("parent_frame", "world"),
            width=d.get("width", 1.0),
            length=d.get("length", 2.0),
            height=d.get("height", 0.05),
            color=d.get("color", [0.6, 0.6, 0.6]),
            opacity=d.get("opacity", 0.75),
        )
        r.translation = np.array(d.get("translation", [0, 0, 0]), dtype=float)
        rpy = d.get("rotation_euler_xyz_deg", [0, 0, 0])
        r.set_rotation_euler(*rpy, degrees=True)
        return r

    def copy(self) -> Ribbon:
        """Restituisce una copia indipendente."""
        return Ribbon(
            name=self.name,
            parent_frame=self.parent_frame,
            width=self.width,
            length=self.length,
            height=self.height,
            translation=self.translation.copy(),
            rotation=self.rotation.copy(),
            color=list(self.color),
            opacity=self.opacity,
        )

    def __repr__(self) -> str:
        return (
            f"Ribbon(name='{self.name}', parent='{self.parent_frame}', "
            f"dims=[{self.width:.3f}×{self.length:.3f}×{self.height:.3f}])"
        )

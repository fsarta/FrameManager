"""
frame.py
--------
Rappresenta un sistema di riferimento rigido nello spazio 3D.
Ogni frame ha un nome, un frame padre opzionale, una traslazione e una rotazione.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.spatial.transform import Rotation

from logger import get_logger

log = get_logger("frame")

# Regex per nomi frame validi: lettere, cifre e underscore, inizia con lettera o _
_VALID_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class Frame:
    """
    Frame di riferimento 6-DOF nello spazio 3D.

    La rotazione è memorizzata internamente come matrice 3×3.
    Sono disponibili getter/setter per:
      - Angoli di Eulero intrinseci XYZ  (roll, pitch, yaw)
      - Quaternioni [x, y, z, w]
      - Matrice di rotazione 3×3
      - Matrice omogenea 4×4

    Attributes
    ----------
    name : str
        Identificatore univoco del frame.
    parent : str | None
        Nome del frame padre (None → world).
    translation : NDArray[np.float64], shape (3,)
        Traslazione rispetto al frame padre.
    rotation : NDArray[np.float64], shape (3, 3)
        Matrice di rotazione rispetto al frame padre.
    """

    def __init__(
        self,
        name: str,
        parent: Optional[str] = None,
        translation: Optional[NDArray[np.float64] | Sequence[float]] = None,
        rotation: Optional[NDArray[np.float64]] = None,
    ) -> None:
        self.name = name
        self.parent = parent
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

    # ------------------------------------------------------------------
    # Validazione
    # ------------------------------------------------------------------

    @staticmethod
    def validate_name(name: str) -> bool:
        """
        Verifica che il nome sia valido per un frame.

        Regole: solo lettere, cifre e underscore; deve iniziare con
        una lettera o underscore. Minimo 1 carattere.

        Parameters
        ----------
        name : str
            Nome da validare.

        Returns
        -------
        bool
            True se il nome è valido.
        """
        return bool(_VALID_NAME_RE.match(name))

    # ------------------------------------------------------------------
    # Trasformazioni omogenee
    # ------------------------------------------------------------------

    @property
    def transform(self) -> NDArray[np.float64]:
        """Matrice di trasformazione omogenea 4×4 (rispetto al padre)."""
        T: NDArray[np.float64] = np.eye(4)
        T[:3, :3] = self.rotation
        T[:3, 3] = self.translation
        return T

    def set_from_transform(self, T: NDArray[np.float64]) -> None:
        """Imposta traslazione e rotazione da una matrice 4×4."""
        self.rotation = T[:3, :3].copy()
        self.translation = T[:3, 3].copy()

    # ------------------------------------------------------------------
    # Angoli di Eulero intrinseci XYZ (roll, pitch, yaw)
    # ------------------------------------------------------------------

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
    # Quaternioni [x, y, z, w]
    # ------------------------------------------------------------------

    def set_rotation_quaternion(self, q: Sequence[float] | NDArray[np.float64]) -> None:
        """
        Imposta la rotazione tramite quaternione [x, y, z, w].

        Parameters
        ----------
        q : array-like, shape (4,)
            Quaternione in formato [x, y, z, w] (convenzione scipy).
        """
        self.rotation = Rotation.from_quat(q).as_matrix()

    def get_rotation_quaternion(self) -> NDArray[np.float64]:
        """Restituisce il quaternione [x, y, z, w] come array shape (4,)."""
        return Rotation.from_matrix(self.rotation).as_quat()

    # ------------------------------------------------------------------
    # Serializzazione
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serializza il frame in un dizionario."""
        rpy = self.get_rotation_euler(degrees=True).tolist()
        return {
            "name": self.name,
            "parent": self.parent,
            "translation": self.translation.tolist(),
            "rotation_euler_xyz_deg": rpy,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Frame:
        """Deserializza un frame da un dizionario."""
        f = cls(d["name"], d.get("parent"))
        f.translation = np.array(d["translation"], dtype=float)
        f.set_rotation_euler(*d["rotation_euler_xyz_deg"], degrees=True)
        return f

    # ------------------------------------------------------------------
    # Utilità
    # ------------------------------------------------------------------

    def copy(self) -> Frame:
        """Restituisce una copia indipendente del frame."""
        return Frame(
            name=self.name,
            parent=self.parent,
            translation=self.translation.copy(),
            rotation=self.rotation.copy(),
        )

    def __repr__(self) -> str:
        t = self.translation
        rpy = self.get_rotation_euler(degrees=True)
        return (
            f"Frame(name='{self.name}', parent='{self.parent}', "
            f"t=[{t[0]:.3f}, {t[1]:.3f}, {t[2]:.3f}], "
            f"rpy=[{rpy[0]:.1f}°, {rpy[1]:.1f}°, {rpy[2]:.1f}°])"
        )

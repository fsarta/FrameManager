"""
frame_tree.py
-------------
Gestisce una collezione di frame organizzata come albero gerarchico.
La radice è sempre il frame 'world'.

Funzionalità principali:
  - Aggiunta / rimozione / rinomina di frame
  - Calcolo della trasformazione rispetto al mondo (forward kinematics)
  - Calcolo della trasformazione relativa tra due frame qualsiasi
  - Serializzazione / deserializzazione (usata da IOHandler)
  - Segnali Observer per notificare la GUI dei cambiamenti
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from numpy.typing import NDArray

from frame import Frame
from ribbon import Ribbon
from logger import get_logger
from observer import Signal

log = get_logger("frame_tree")

# Profondità massima per la catena cinematica (protezione da cicli)
_MAX_CHAIN_DEPTH = 200


class FrameTree:
    """
    Albero di frame di riferimento con radice 'world'.

    Ogni frame non-world conosce il proprio parent; la trasformazione
    mondiale si ottiene componendo le trasformazioni locali lungo la catena.

    Signals
    -------
    frame_added : Signal(name: str)
        Emesso dopo l'aggiunta di un frame.
    frame_removed : Signal(name: str)
        Emesso dopo la rimozione di un frame.
    frame_modified : Signal(name: str)
        Emesso dopo la modifica di un frame (parent, traslazione, rotazione).
    tree_loaded : Signal()
        Emesso dopo un caricamento completo dell'albero (load JSON, import URDF).

    Attributes
    ----------
    frames : dict[str, Frame]
        Mappa nome → Frame di tutti i frame gestiti.
    """

    def __init__(self) -> None:
        self.frames: Dict[str, Frame] = {}
        self.ribbons: Dict[str, Ribbon] = {}
        # La radice è sempre presente
        self.frames["world"] = Frame("world")

        # ── Segnali Observer ──
        self.frame_added = Signal()
        self.frame_removed = Signal()
        self.frame_modified = Signal()
        self.ribbon_changed = Signal()
        self.tree_loaded = Signal()

    # ------------------------------------------------------------------
    # Gestione frame
    # ------------------------------------------------------------------

    def add_frame(self, frame: Frame) -> bool:
        """
        Aggiunge un frame all'albero.

        Returns
        -------
        bool
            True se aggiunto con successo, False se il nome era già presente.
        """
        if frame.name in self.frames:
            log.warning("add_frame: nome '%s' già presente", frame.name)
            return False
        # Assicura che il parent esista
        if not frame.parent or frame.parent not in self.frames:
            log.info("add_frame: parent '%s' non trovato, uso 'world'", frame.parent)
            frame.parent = "world"
        self.frames[frame.name] = frame
        log.info("Frame '%s' aggiunto (parent='%s')", frame.name, frame.parent)
        self.frame_added.emit(frame.name)
        return True

    def remove_frame(self, name: str) -> bool:
        """
        Rimuove un frame. I figli vengono re-parentati al nonno.

        Returns
        -------
        bool
            True se rimosso, False se il frame non esiste o è 'world'.
        """
        if name == "world" or name not in self.frames:
            log.warning("remove_frame: impossibile rimuovere '%s'", name)
            return False
        new_parent = self.frames[name].parent or "world"
        reparented: List[str] = []
        for f in self.frames.values():
            if f.parent == name:
                f.parent = new_parent
                reparented.append(f.name)
        del self.frames[name]
        log.info("Frame '%s' rimosso (figli ri-parentati a '%s': %s)",
                 name, new_parent, reparented)
        self.frame_removed.emit(name)
        return True

    def rename_frame(self, old_name: str, new_name: str) -> bool:
        """
        Rinomina un frame aggiornando anche tutti i riferimenti nei figli.

        Returns
        -------
        bool
            True se rinominato con successo.
        """
        if old_name == "world" or old_name not in self.frames:
            log.warning("rename_frame: frame '%s' non rinominabile", old_name)
            return False
        if new_name in self.frames:
            log.warning("rename_frame: nome '%s' già esistente", new_name)
            return False
        frame = self.frames.pop(old_name)
        frame.name = new_name
        self.frames[new_name] = frame
        for f in self.frames.values():
            if f.parent == old_name:
                f.parent = new_name
        log.info("Frame rinominato: '%s' → '%s'", old_name, new_name)
        self.frame_modified.emit(new_name)
        return True

    def get_children(self, name: str) -> List[str]:
        """Restituisce i nomi dei figli diretti di *name*."""
        return [f.name for f in self.frames.values() if f.parent == name]

    def get_ancestors(self, name: str) -> List[str]:
        """Restituisce la lista dei predecessori fino a 'world' (incluso)."""
        chain: List[str] = []
        current: Optional[str] = name
        visited: set[str] = set()
        while current and current not in visited:
            visited.add(current)
            chain.append(current)
            if current not in self.frames:
                break
            current = self.frames[current].parent or ""
        return chain

    def get_all_names(self) -> List[str]:
        """Restituisce tutti i nomi: 'world' per primo, poi gli altri."""
        names = list(self.frames.keys())
        if "world" in names:
            names.remove("world")
            names.insert(0, "world")
        return names

    def get_subtree(self, name: str) -> Dict[str, List[str]]:
        """
        Restituisce la struttura gerarchica come dizionario
        { parent_name: [child_name, ...] } radicato in *name*.

        Utile per costruire un TreeView.
        """
        result: Dict[str, List[str]] = {}
        queue: List[str] = [name]
        while queue:
            current = queue.pop(0)
            children = self.get_children(current)
            result[current] = children
            queue.extend(children)
        return result

    def would_create_cycle(self, child_name: str, new_parent: str) -> bool:
        """Verifica se impostare *new_parent* come padre di *child_name* creerebbe un ciclo."""
        current: Optional[str] = new_parent
        visited: set[str] = set()
        while current and current not in visited:
            if current == child_name:
                return True
            visited.add(current)
            if current not in self.frames:
                break
            current = self.frames[current].parent or ""
        return False

    # ------------------------------------------------------------------
    # Calcolo trasformazioni
    # ------------------------------------------------------------------

    def get_world_transform(self, name: str) -> NDArray[np.float64]:
        """
        Calcola la posa di *name* nel frame mondo (4×4 homogeneous).

        Compone le trasformazioni locali lungo la catena cinematica
        fino alla radice, con protezione da cicli (max depth).

        Returns
        -------
        NDArray[np.float64], shape (4, 4)
            Trasformazione omogenea T_world_frame.

        Raises
        ------
        RuntimeError
            Se viene rilevato un ciclo nella catena cinematica.
        """
        if name == "world":
            return np.eye(4)
        if name not in self.frames:
            log.error("get_world_transform: frame '%s' non trovato", name)
            return np.eye(4)

        # Costruisce la catena dalla foglia alla radice con protezione
        chain: List[Frame] = []
        current: Optional[str] = name
        visited: set[str] = set()
        depth = 0

        while current and current != "world" and depth < _MAX_CHAIN_DEPTH:
            if current in visited:
                log.error("Ciclo rilevato nella catena di '%s'!", name)
                raise RuntimeError(
                    f"Ciclo nella catena cinematica al frame '{current}'"
                )
            visited.add(current)
            if current not in self.frames:
                log.warning("Frame '%s' non trovato nella catena di '%s'",
                            current, name)
                break
            chain.append(self.frames[current])
            current = self.frames[current].parent
            depth += 1

        if depth >= _MAX_CHAIN_DEPTH:
            log.error("Profondità massima raggiunta per '%s' (%d)", name, depth)
            raise RuntimeError(
                f"Profondità massima ({_MAX_CHAIN_DEPTH}) raggiunta per '{name}'"
            )

        # Componi: T_world = T_f1 @ T_f2 @ ... @ T_leaf
        T: NDArray[np.float64] = np.eye(4)
        for frame in reversed(chain):
            T = T @ frame.transform

        return T

    def get_relative_transform(
        self, source: str, target: str
    ) -> NDArray[np.float64]:
        """
        Trasformazione di *source* espressa nel frame *target*.

        T_target_source = inv(T_world_target) @ T_world_source
        """
        T_ws = self.get_world_transform(source)
        T_wt = self.get_world_transform(target)
        return np.linalg.inv(T_wt) @ T_ws

    def get_all_world_transforms(self) -> Dict[str, NDArray[np.float64]]:
        """Calcola e restituisce le trasformazioni mondiali per tutti i frame."""
        return {name: self.get_world_transform(name) for name in self.frames}

    # ------------------------------------------------------------------
    # Gestione nastri
    # ------------------------------------------------------------------

    def add_ribbon(self, ribbon: Ribbon) -> bool:
        """Aggiunge un nastro. Restituisce False se il nome esiste già."""
        if ribbon.name in self.ribbons:
            log.warning("add_ribbon: nome '%s' già presente", ribbon.name)
            return False
        if ribbon.parent_frame not in self.frames:
            log.info("add_ribbon: parent '%s' non trovato, uso 'world'", ribbon.parent_frame)
            ribbon.parent_frame = "world"
        self.ribbons[ribbon.name] = ribbon
        log.info("Nastro '%s' aggiunto (parent='%s')", ribbon.name, ribbon.parent_frame)
        self.ribbon_changed.emit(ribbon.name)
        return True

    def remove_ribbon(self, name: str) -> bool:
        """Rimuove un nastro. Restituisce False se non esiste."""
        if name not in self.ribbons:
            return False
        del self.ribbons[name]
        log.info("Nastro '%s' rimosso", name)
        self.ribbon_changed.emit(name)
        return True

    def get_ribbon_names(self) -> List[str]:
        """Restituisce la lista dei nomi dei nastri."""
        return list(self.ribbons.keys())

    # ------------------------------------------------------------------
    # Serializzazione
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serializza l'intero albero (frame + nastri) in un dizionario."""
        return {
            "frames": [
                f.to_dict()
                for f in self.frames.values()
                if f.name != "world"
            ],
            "ribbons": [
                r.to_dict()
                for r in self.ribbons.values()
            ],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> FrameTree:
        """
        Deserializza un FrameTree da dizionario, rispettando l'ordine
        topologico (il padre deve essere aggiunto prima del figlio).
        """
        tree = cls()
        frames_data = list(d.get("frames", []))
        added: set[str] = {"world"}
        max_iters = max(len(frames_data) ** 2 + 10, 100)
        iters = 0
        while frames_data and iters < max_iters:
            iters += 1
            fd = frames_data.pop(0)
            parent = fd.get("parent") or "world"
            if parent in added:
                f = Frame.from_dict(fd)
                tree.frames[f.name] = f  # bypass signal per il loading
                if f.parent and f.parent not in tree.frames:
                    f.parent = "world"
                added.add(f.name)
            else:
                frames_data.append(fd)  # riprova dopo

        # Deserializza nastri
        for rd in d.get("ribbons", []):
            r = Ribbon.from_dict(rd)
            tree.ribbons[r.name] = r

        tree.tree_loaded.emit()
        return tree

    # ------------------------------------------------------------------
    # Utilità
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.frames)

    def __contains__(self, name: str) -> bool:
        return name in self.frames

    def __repr__(self) -> str:
        return f"FrameTree({list(self.frames.keys())})"

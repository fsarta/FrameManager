"""
undo_redo.py
------------
Sistema Undo / Redo basato su snapshot JSON del FrameTree.

Ogni volta che si chiama `save_state()` viene salvata una copia
serializzata dell'albero. `undo()` e `redo()` restituiscono i
dizionari da cui ricostruire il FrameTree.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from logger import get_logger
from observer import Signal

log = get_logger("undo_redo")

MAX_UNDO_STEPS = 50


class UndoRedoManager:
    """
    Gestore Undo/Redo con stack limitato.

    Attributes
    ----------
    state_changed : Signal
        Emesso dopo ogni undo/redo con (can_undo: bool, can_redo: bool).
    """

    def __init__(self) -> None:
        self._undo_stack: List[Dict[str, Any]] = []
        self._redo_stack: List[Dict[str, Any]] = []
        self.state_changed = Signal()

    # ------------------------------------------------------------------
    # Stato
    # ------------------------------------------------------------------

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 1  # serve almeno lo stato corrente + precedente

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    def save_state(self, tree_dict: Dict[str, Any]) -> None:
        """
        Salva uno snapshot dello stato corrente.

        Deve essere chiamato *prima* di ogni modifica.
        Salva una copia profonda del dizionario.
        """
        import copy
        self._undo_stack.append(copy.deepcopy(tree_dict))

        # Limita la dimensione dello stack
        if len(self._undo_stack) > MAX_UNDO_STEPS:
            self._undo_stack.pop(0)

        # Una nuova azione invalida lo stack redo
        self._redo_stack.clear()

        log.debug("Stato salvato (undo stack: %d)", len(self._undo_stack))
        self.state_changed.emit(self.can_undo, self.can_redo)

    def undo(self) -> Optional[Dict[str, Any]]:
        """
        Annulla l'ultima operazione.

        Returns
        -------
        dict | None
            Dizionario dello stato precedente, o None se non disponibile.
        """
        if not self.can_undo:
            log.info("Nessuna operazione da annullare")
            return None

        # Sposta lo stato corrente nel redo stack
        current = self._undo_stack.pop()
        self._redo_stack.append(current)

        # Restituisce lo stato precedente (che rimane in cima all'undo stack)
        previous = self._undo_stack[-1]
        log.info("Undo eseguito (undo: %d, redo: %d)",
                 len(self._undo_stack), len(self._redo_stack))
        self.state_changed.emit(self.can_undo, self.can_redo)

        import copy
        return copy.deepcopy(previous)

    def redo(self) -> Optional[Dict[str, Any]]:
        """
        Ripristina l'ultima operazione annullata.

        Returns
        -------
        dict | None
            Dizionario dello stato ripristinato, o None se non disponibile.
        """
        if not self.can_redo:
            log.info("Nessuna operazione da ripristinare")
            return None

        state = self._redo_stack.pop()
        self._undo_stack.append(state)

        log.info("Redo eseguito (undo: %d, redo: %d)",
                 len(self._undo_stack), len(self._redo_stack))
        self.state_changed.emit(self.can_undo, self.can_redo)

        import copy
        return copy.deepcopy(state)

    def clear(self) -> None:
        """Resetta entrambi gli stack."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.state_changed.emit(False, False)

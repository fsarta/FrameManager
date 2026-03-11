"""
test_undo_redo.py
-----------------
Unit tests per UndoRedoManager.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from undo_redo import UndoRedoManager


def _state(n: int) -> dict:
    """Crea uno stato fittizio con n frame."""
    return {"frames": [{"name": f"frame_{i}"} for i in range(n)]}


class TestUndoRedoBasic:
    """Test delle operazioni base."""

    def test_initial_state(self):
        mgr = UndoRedoManager()
        assert mgr.can_undo is False
        assert mgr.can_redo is False

    def test_save_enables_undo(self):
        mgr = UndoRedoManager()
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        assert mgr.can_undo is True

    def test_undo_returns_previous(self):
        mgr = UndoRedoManager()
        s1 = _state(1)
        s2 = _state(2)
        mgr.save_state(s1)
        mgr.save_state(s2)
        result = mgr.undo()
        assert result is not None
        assert len(result["frames"]) == 1

    def test_redo_after_undo(self):
        mgr = UndoRedoManager()
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        mgr.undo()
        assert mgr.can_redo is True
        result = mgr.redo()
        assert result is not None
        assert len(result["frames"]) == 2

    def test_undo_when_empty(self):
        mgr = UndoRedoManager()
        assert mgr.undo() is None

    def test_redo_when_empty(self):
        mgr = UndoRedoManager()
        assert mgr.redo() is None


class TestUndoRedoStack:
    """Test del comportamento dello stack."""

    def test_new_action_invalidates_redo(self):
        mgr = UndoRedoManager()
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        mgr.undo()
        mgr.save_state(_state(3))
        assert mgr.can_redo is False

    def test_max_undo_steps(self):
        mgr = UndoRedoManager()
        for i in range(60):
            mgr.save_state(_state(i))
        # Lo stack deve essere limitato a MAX_UNDO_STEPS (50)
        count = 0
        while mgr.can_undo:
            mgr.undo()
            count += 1
        assert count <= 50

    def test_clear(self):
        mgr = UndoRedoManager()
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        mgr.clear()
        assert mgr.can_undo is False
        assert mgr.can_redo is False


class TestUndoRedoSignals:
    """Test dei segnali Observer."""

    def test_state_changed_emitted(self):
        mgr = UndoRedoManager()
        events = []
        mgr.state_changed.connect(
            lambda can_undo, can_redo: events.append((can_undo, can_redo))
        )
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        assert len(events) == 2

    def test_undo_redo_signals(self):
        mgr = UndoRedoManager()
        events = []
        mgr.state_changed.connect(
            lambda can_undo, can_redo: events.append((can_undo, can_redo))
        )
        mgr.save_state(_state(1))
        mgr.save_state(_state(2))
        mgr.undo()
        mgr.redo()
        assert len(events) == 4  # 2 saves + 1 undo + 1 redo


class TestUndoRedoDeepCopy:
    """Test che gli stati siano copie indipendenti."""

    def test_deep_copy(self):
        mgr = UndoRedoManager()
        s = _state(1)
        mgr.save_state(s)

        # Modifica l'originale
        s["frames"].append({"name": "extra"})

        # Lo stato salvato non deve cambiare
        mgr.save_state(_state(2))
        result = mgr.undo()
        assert len(result["frames"]) == 1

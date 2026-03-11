"""
test_frame_tree.py
------------------
Unit tests per la classe FrameTree.
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frame import Frame
from frame_tree import FrameTree


class TestFrameTreeInit:
    """Test di inizializzazione."""

    def test_default_has_world(self):
        tree = FrameTree()
        assert "world" in tree
        assert len(tree) == 1

    def test_world_is_identity(self):
        tree = FrameTree()
        T = tree.get_world_transform("world")
        np.testing.assert_array_almost_equal(T, np.eye(4))


class TestFrameTreeAddRemove:
    """Test di aggiunta e rimozione frame."""

    def test_add_frame(self):
        tree = FrameTree()
        f = Frame("A", parent="world", translation=np.array([1.0, 0, 0]))
        assert tree.add_frame(f) is True
        assert "A" in tree
        assert len(tree) == 2

    def test_add_duplicate(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        assert tree.add_frame(Frame("A")) is False

    def test_add_with_missing_parent(self):
        tree = FrameTree()
        f = Frame("A", parent="nonexistent")
        tree.add_frame(f)
        assert f.parent == "world"

    def test_remove_frame(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        assert tree.remove_frame("A") is True
        assert "A" not in tree

    def test_remove_world(self):
        tree = FrameTree()
        assert tree.remove_frame("world") is False

    def test_remove_reparents_children(self):
        tree = FrameTree()
        tree.add_frame(Frame("A", parent="world"))
        tree.add_frame(Frame("B", parent="A"))
        tree.remove_frame("A")
        assert tree.frames["B"].parent == "world"


class TestFrameTreeRename:
    """Test della rinomina frame."""

    def test_rename(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        assert tree.rename_frame("A", "B") is True
        assert "B" in tree
        assert "A" not in tree

    def test_rename_world(self):
        tree = FrameTree()
        assert tree.rename_frame("world", "root") is False

    def test_rename_to_existing(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B"))
        assert tree.rename_frame("A", "B") is False

    def test_rename_updates_children(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        tree.rename_frame("A", "C")
        assert tree.frames["B"].parent == "C"


class TestFrameTreeTransforms:
    """Test del calcolo delle trasformazioni."""

    def test_simple_chain(self):
        tree = FrameTree()
        f = Frame("A", parent="world", translation=np.array([1.0, 0.0, 0.0]))
        tree.add_frame(f)
        T = tree.get_world_transform("A")
        np.testing.assert_array_almost_equal(T[:3, 3], [1.0, 0.0, 0.0])

    def test_two_level_chain(self):
        tree = FrameTree()
        tree.add_frame(Frame("A", parent="world",
                             translation=np.array([1.0, 0.0, 0.0])))
        tree.add_frame(Frame("B", parent="A",
                             translation=np.array([0.0, 1.0, 0.0])))
        T = tree.get_world_transform("B")
        np.testing.assert_array_almost_equal(T[:3, 3], [1.0, 1.0, 0.0])

    def test_relative_transform(self):
        tree = FrameTree()
        tree.add_frame(Frame("A", parent="world",
                             translation=np.array([1.0, 0.0, 0.0])))
        tree.add_frame(Frame("B", parent="world",
                             translation=np.array([2.0, 0.0, 0.0])))
        T = tree.get_relative_transform("B", "A")
        np.testing.assert_array_almost_equal(T[:3, 3], [1.0, 0.0, 0.0])

    def test_nonexistent_frame(self):
        tree = FrameTree()
        T = tree.get_world_transform("nonexistent")
        np.testing.assert_array_almost_equal(T, np.eye(4))


class TestFrameTreeCycleDetection:
    """Test della rilevazione cicli."""

    def test_no_cycle(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        assert tree.would_create_cycle("A", "world") is False

    def test_direct_cycle(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        assert tree.would_create_cycle("A", "B") is True

    def test_indirect_cycle(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        tree.add_frame(Frame("C", parent="B"))
        assert tree.would_create_cycle("A", "C") is True


class TestFrameTreeHierarchy:
    """Test delle funzioni gerarchiche."""

    def test_get_children(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        tree.add_frame(Frame("C", parent="A"))
        children = tree.get_children("A")
        assert sorted(children) == ["B", "C"]

    def test_get_ancestors(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        ancestors = tree.get_ancestors("B")
        assert "B" in ancestors
        assert "A" in ancestors

    def test_get_subtree(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B", parent="A"))
        subtree = tree.get_subtree("world")
        assert "world" in subtree
        assert "A" in subtree["world"]

    def test_get_all_names_world_first(self):
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_frame(Frame("B"))
        names = tree.get_all_names()
        assert names[0] == "world"


class TestFrameTreeObserver:
    """Test dei segnali Observer."""

    def test_frame_added_signal(self):
        tree = FrameTree()
        events = []
        tree.frame_added.connect(lambda name: events.append(("added", name)))
        tree.add_frame(Frame("A"))
        assert len(events) == 1
        assert events[0] == ("added", "A")

    def test_frame_removed_signal(self):
        tree = FrameTree()
        events = []
        tree.frame_removed.connect(lambda name: events.append(("removed", name)))
        tree.add_frame(Frame("A"))
        tree.remove_frame("A")
        assert ("removed", "A") in events

    def test_frame_modified_signal(self):
        tree = FrameTree()
        events = []
        tree.frame_modified.connect(lambda name: events.append(("modified", name)))
        tree.add_frame(Frame("A"))
        tree.rename_frame("A", "B")
        assert ("modified", "B") in events


class TestFrameTreeSerialization:
    """Test della serializzazione."""

    def test_roundtrip(self):
        tree = FrameTree()
        tree.add_frame(Frame("A", parent="world",
                             translation=np.array([1.0, 2.0, 3.0])))
        fa = tree.frames["A"]
        fa.set_rotation_euler(10, 20, 30)
        tree.add_frame(Frame("B", parent="A",
                             translation=np.array([0.5, 0.5, 0.5])))

        d = tree.to_dict()
        tree2 = FrameTree.from_dict(d)

        assert len(tree2) == len(tree)
        assert "A" in tree2
        assert "B" in tree2
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].translation, [1.0, 2.0, 3.0]
        )
        assert tree2.frames["B"].parent == "A"

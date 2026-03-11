"""
test_ribbon.py
--------------
Unit tests per la classe Ribbon.
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ribbon import Ribbon


class TestRibbonInit:
    """Test di costruzione."""

    def test_default_values(self):
        r = Ribbon("test")
        assert r.name == "test"
        assert r.parent_frame == "world"
        assert r.width == 1.0
        assert r.length == 2.0
        assert r.height == 0.05
        assert r.opacity == 0.75
        np.testing.assert_array_equal(r.translation, np.zeros(3))
        np.testing.assert_array_equal(r.rotation, np.eye(3))

    def test_custom_values(self):
        r = Ribbon("belt", parent_frame="frame_A",
                   width=0.5, length=3.0, height=0.1,
                   translation=np.array([1, 2, 3]),
                   color=[0.2, 0.4, 0.8], opacity=0.5)
        assert r.width == 0.5
        assert r.length == 3.0
        assert r.height == 0.1
        assert r.color == [0.2, 0.4, 0.8]
        assert r.opacity == 0.5

    def test_min_dimensions(self):
        r = Ribbon("test", width=-1, length=0, height=-0.5)
        assert r.width == 0.001
        assert r.length == 0.001
        assert r.height == 0.001


class TestRibbonValidation:
    """Test validazione nome."""

    @pytest.mark.parametrize("name", ["nastro_1", "belt", "conveyor_A"])
    def test_valid_names(self, name):
        assert Ribbon.validate_name(name) is True

    @pytest.mark.parametrize("name", ["", "nastro 1", "123belt"])
    def test_invalid_names(self, name):
        assert Ribbon.validate_name(name) is False


class TestRibbonTransform:
    """Test trasformazione."""

    def test_identity_transform(self):
        r = Ribbon("test")
        T = r.transform
        np.testing.assert_array_almost_equal(T, np.eye(4))

    def test_euler_roundtrip(self):
        r = Ribbon("test")
        r.set_rotation_euler(10, 20, 30, degrees=True)
        rpy = r.get_rotation_euler(degrees=True)
        np.testing.assert_array_almost_equal(rpy, [10, 20, 30])


class TestRibbonSerialization:
    """Test serializzazione."""

    def test_roundtrip(self):
        r = Ribbon("belt", parent_frame="frame_A",
                   width=0.5, length=3.0, height=0.1,
                   color=[0.2, 0.4, 0.8], opacity=0.6)
        r.set_rotation_euler(15, -20, 45)
        r.translation = np.array([1.0, 2.0, 3.0])

        d = r.to_dict()
        r2 = Ribbon.from_dict(d)

        assert r2.name == r.name
        assert r2.parent_frame == r.parent_frame
        assert r2.width == pytest.approx(r.width)
        assert r2.length == pytest.approx(r.length)
        assert r2.height == pytest.approx(r.height)
        np.testing.assert_array_almost_equal(r2.translation, r.translation)
        np.testing.assert_array_almost_equal(
            r2.get_rotation_euler(), r.get_rotation_euler()
        )


class TestRibbonCopy:
    """Test copia indipendente."""

    def test_copy_independence(self):
        r = Ribbon("belt", width=1.0, color=[0.5, 0.5, 0.5])
        c = r.copy()
        c.width = 99.0
        c.color[0] = 0.0
        assert r.width == 1.0
        assert r.color[0] == 0.5


class TestRibbonInFrameTree:
    """Test integrazione con FrameTree."""

    def test_add_and_remove_ribbon(self):
        from frame_tree import FrameTree
        tree = FrameTree()
        r = Ribbon("belt_1")
        assert tree.add_ribbon(r) is True
        assert "belt_1" in tree.ribbons
        assert tree.remove_ribbon("belt_1") is True
        assert "belt_1" not in tree.ribbons

    def test_ribbon_in_serialization(self):
        from frame_tree import FrameTree
        from frame import Frame
        tree = FrameTree()
        tree.add_frame(Frame("A"))
        tree.add_ribbon(Ribbon("belt", parent_frame="A",
                               width=0.5, length=2.0))

        d = tree.to_dict()
        tree2 = FrameTree.from_dict(d)

        assert "belt" in tree2.ribbons
        assert tree2.ribbons["belt"].width == pytest.approx(0.5)
        assert tree2.ribbons["belt"].parent_frame == "A"

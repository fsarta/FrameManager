"""
test_frame.py
-------------
Unit tests per la classe Frame.
"""

import sys
import os
import numpy as np
import pytest

# Aggiungi la directory padre al path per gli import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frame import Frame


class TestFrameInit:
    """Test di costruzione del Frame."""

    def test_default_values(self):
        f = Frame("test")
        assert f.name == "test"
        assert f.parent is None
        np.testing.assert_array_equal(f.translation, np.zeros(3))
        np.testing.assert_array_equal(f.rotation, np.eye(3))

    def test_custom_values(self):
        t = np.array([1.0, 2.0, 3.0])
        R = np.eye(3)
        f = Frame("test", parent="world", translation=t, rotation=R)
        assert f.name == "test"
        assert f.parent == "world"
        np.testing.assert_array_almost_equal(f.translation, t)
        np.testing.assert_array_almost_equal(f.rotation, R)


class TestFrameValidation:
    """Test del metodo validate_name."""

    @pytest.mark.parametrize("name", [
        "frame_A", "world", "_private", "x", "frame123",
        "Frame_B", "ABC_DEF_123",
    ])
    def test_valid_names(self, name):
        assert Frame.validate_name(name) is True

    @pytest.mark.parametrize("name", [
        "", "frame A", "123frame", "frame-B", "frame.C",
        "frame@D", " leading", "trailing ",
    ])
    def test_invalid_names(self, name):
        assert Frame.validate_name(name) is False


class TestFrameTransform:
    """Test della proprietà transform e set_from_transform."""

    def test_identity(self):
        f = Frame("test")
        T = f.transform
        np.testing.assert_array_almost_equal(T, np.eye(4))

    def test_translation_only(self):
        f = Frame("test", translation=np.array([1.0, 2.0, 3.0]))
        T = f.transform
        assert T[0, 3] == pytest.approx(1.0)
        assert T[1, 3] == pytest.approx(2.0)
        assert T[2, 3] == pytest.approx(3.0)
        np.testing.assert_array_almost_equal(T[:3, :3], np.eye(3))

    def test_set_from_transform(self):
        T = np.eye(4)
        T[:3, 3] = [5.0, 6.0, 7.0]
        f = Frame("test")
        f.set_from_transform(T)
        np.testing.assert_array_almost_equal(f.translation, [5.0, 6.0, 7.0])
        np.testing.assert_array_almost_equal(f.rotation, np.eye(3))


class TestFrameEuler:
    """Test degli angoli di Eulero."""

    def test_roundtrip(self):
        f = Frame("test")
        f.set_rotation_euler(30, 45, 60, degrees=True)
        rpy = f.get_rotation_euler(degrees=True)
        np.testing.assert_array_almost_equal(rpy, [30, 45, 60], decimal=10)

    def test_zero_rotation(self):
        f = Frame("test")
        rpy = f.get_rotation_euler(degrees=True)
        np.testing.assert_array_almost_equal(rpy, [0, 0, 0])

    def test_radians(self):
        f = Frame("test")
        f.set_rotation_euler(0.5, 0.3, 0.1, degrees=False)
        rpy = f.get_rotation_euler(degrees=False)
        np.testing.assert_array_almost_equal(rpy, [0.5, 0.3, 0.1], decimal=10)


class TestFrameQuaternion:
    """Test dei quaternioni."""

    def test_identity_quaternion(self):
        f = Frame("test")
        q = f.get_rotation_quaternion()
        # Identità: [0, 0, 0, 1]
        np.testing.assert_array_almost_equal(q, [0, 0, 0, 1])

    def test_roundtrip(self):
        q_in = np.array([0.0, 0.0, 0.382683, 0.923880])  # 45° around Z
        f = Frame("test")
        f.set_rotation_quaternion(q_in)
        q_out = f.get_rotation_quaternion()
        np.testing.assert_array_almost_equal(q_out, q_in, decimal=5)


class TestFrameSerialization:
    """Test della serializzazione to_dict / from_dict."""

    def test_roundtrip(self):
        f = Frame("test_frame", parent="world",
                  translation=np.array([1.5, 2.5, 3.5]))
        f.set_rotation_euler(10, 20, 30)

        d = f.to_dict()
        f2 = Frame.from_dict(d)

        assert f2.name == f.name
        assert f2.parent == f.parent
        np.testing.assert_array_almost_equal(f2.translation, f.translation)
        np.testing.assert_array_almost_equal(
            f2.get_rotation_euler(), f.get_rotation_euler()
        )

    def test_dict_keys(self):
        f = Frame("test")
        d = f.to_dict()
        assert set(d.keys()) == {
            "name", "parent", "translation", "rotation_euler_xyz_deg"
        }


class TestFrameCopy:
    """Test della copia indipendente."""

    def test_copy_independence(self):
        f = Frame("original", parent="world",
                  translation=np.array([1.0, 2.0, 3.0]))
        f.set_rotation_euler(10, 20, 30)

        c = f.copy()
        c.translation[0] = 99.0
        c.set_rotation_euler(0, 0, 0)

        assert f.translation[0] == pytest.approx(1.0)
        assert f.get_rotation_euler(degrees=True)[0] != pytest.approx(0.0)


class TestFrameRepr:
    """Test della rappresentazione stringa."""

    def test_repr(self):
        f = Frame("test", parent="world")
        r = repr(f)
        assert "Frame(" in r
        assert "test" in r

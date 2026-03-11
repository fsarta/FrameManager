"""
test_io_handler.py
------------------
Unit tests per la classe IOHandler (JSON, CSV, URDF roundtrip).
"""

import sys
import os
import json
import tempfile
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from frame import Frame
from frame_tree import FrameTree
from io_handler import IOHandler


def _build_sample_tree() -> FrameTree:
    """Crea un albero di esempio per i test."""
    tree = FrameTree()
    fa = Frame("A", parent="world", translation=np.array([1.0, 0.0, 0.0]))
    fa.set_rotation_euler(10, 20, 30)
    tree.add_frame(fa)

    fb = Frame("B", parent="A", translation=np.array([0.5, 0.3, 0.2]))
    fb.set_rotation_euler(5, -10, 15)
    tree.add_frame(fb)

    fc = Frame("C", parent="world", translation=np.array([0.0, 1.0, 0.5]))
    tree.add_frame(fc)
    return tree


class TestJSONRoundtrip:
    """Test del roundtrip JSON."""

    def test_save_and_load(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.json")

        IOHandler.save_json(tree, path)
        tree2 = IOHandler.load_json(path)

        assert len(tree2) == len(tree)
        assert "A" in tree2
        assert "B" in tree2
        assert "C" in tree2
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].translation, tree.frames["A"].translation
        )
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].get_rotation_euler(),
            tree.frames["A"].get_rotation_euler(),
        )

    def test_json_file_content(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.json")
        IOHandler.save_json(tree, path)

        with open(path, "r") as f:
            data = json.load(f)
        assert "frames" in data
        names = [fr["name"] for fr in data["frames"]]
        assert "A" in names
        assert "B" in names


class TestURDFRoundtrip:
    """Test del roundtrip URDF."""

    def test_export_and_import(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.urdf")

        IOHandler.export_urdf(tree, path)
        tree2 = IOHandler.import_urdf(path)

        assert len(tree2) == len(tree)
        assert "A" in tree2
        assert "B" in tree2
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].translation, tree.frames["A"].translation,
            decimal=5,
        )

    def test_urdf_is_valid_xml(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.urdf")
        IOHandler.export_urdf(tree, path)

        import xml.etree.ElementTree as ET
        root = ET.parse(path).getroot()
        assert root.tag == "robot"
        links = root.findall("link")
        assert len(links) >= 3  # world, A, B, C


class TestCSVRoundtrip:
    """Test del roundtrip CSV."""

    def test_export_and_import(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.csv")

        IOHandler.export_csv(tree, path)
        tree2 = IOHandler.import_csv(path)

        assert len(tree2) == len(tree)
        assert "A" in tree2
        assert "B" in tree2
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].translation, tree.frames["A"].translation,
            decimal=5,
        )

    def test_csv_has_header(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.csv")
        IOHandler.export_csv(tree, path)

        with open(path, "r") as f:
            first_line = f.readline().strip()
        assert "name" in first_line
        assert "parent" in first_line


class TestYAMLRoundtrip:
    """Test del roundtrip YAML (se PyYAML è installato)."""

    @pytest.fixture(autouse=True)
    def _check_yaml(self):
        pytest.importorskip("yaml")

    def test_export_and_import(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test.yaml")

        IOHandler.export_yaml(tree, path)
        tree2 = IOHandler.import_yaml(path)

        assert len(tree2) == len(tree)
        assert "A" in tree2
        np.testing.assert_array_almost_equal(
            tree2.frames["A"].translation, tree.frames["A"].translation,
            decimal=5,
        )


class TestDHExport:
    """Test dell'export DH parameters."""

    def test_export(self, tmp_path):
        tree = _build_sample_tree()
        path = str(tmp_path / "test_dh.csv")

        IOHandler.export_dh(tree, path)

        with open(path, "r") as f:
            lines = f.readlines()
        assert len(lines) >= 3  # header + A + B + C
        assert "name" in lines[0]
        assert "alpha_deg" in lines[0]


class TestAutosave:
    """Test del meccanismo di autosave."""

    def test_autosave_and_load(self, monkeypatch, tmp_path):
        import io_handler
        monkeypatch.setattr(io_handler, "AUTOSAVE_DIR", tmp_path)
        monkeypatch.setattr(io_handler, "AUTOSAVE_FILE", tmp_path / "autosave.json")

        tree = _build_sample_tree()
        IOHandler.autosave(tree)

        assert IOHandler.has_autosave()

        tree2 = IOHandler.load_autosave()
        assert tree2 is not None
        assert "A" in tree2
        assert len(tree2) == len(tree)

    def test_clear_autosave(self, monkeypatch, tmp_path):
        import io_handler
        monkeypatch.setattr(io_handler, "AUTOSAVE_DIR", tmp_path)
        monkeypatch.setattr(io_handler, "AUTOSAVE_FILE", tmp_path / "autosave.json")

        tree = _build_sample_tree()
        IOHandler.autosave(tree)
        IOHandler.clear_autosave()
        assert not IOHandler.has_autosave()

"""Ensure dependency analysis never inherits unrelated native tools from PATH."""

import ast
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.version import __version__


class VersionMetadataTests(unittest.TestCase):
    def test_windows_version_metadata_matches_application_version(self):
        root = Path(__file__).resolve().parents[1]
        tree = ast.parse((root / "version_info.txt").read_text("utf-8"))
        numeric = {}
        strings = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id == "FixedFileInfo":
                numeric.update((item.arg, ast.literal_eval(item.value)) for item in node.keywords
                               if item.arg in ("filevers", "prodvers"))
            elif node.func.id == "StringStruct":
                key, value = (ast.literal_eval(arg) for arg in node.args)
                if key in ("FileVersion", "ProductVersion"):
                    strings[key] = value
        version = tuple(map(int, __version__.split("."))) + (0,)
        self.assertEqual(numeric, {"filevers": version, "prodvers": version})
        self.assertEqual(strings, {"FileVersion": __version__ + ".0",
                                   "ProductVersion": __version__ + ".0"})


@unittest.skipUnless(os.name == "nt", "Windows build configuration")
class PackagingTests(unittest.TestCase):
    def test_spec_sanitizes_path_before_dependency_analysis(self):
        root = Path(__file__).resolve().parents[1]
        observed = []

        def analyze(*args, **kwargs):
            observed.extend(os.environ["PATH"].split(os.pathsep))
            self.assertEqual([Path(src).name for src, target in kwargs["datas"] if target == "icons"],
                             ["bin_0.ico", "bin_25.ico", "bin_50.ico", "bin_75.ico", "bin_full.ico",
                              "github.svg", "github_dark.svg"])
            return SimpleNamespace(pure=[], scripts=[], binaries=[], datas=[])

        namespace = {"SPECPATH": str(root), "Analysis": analyze,
                     "PYZ": lambda *a, **k: None, "EXE": lambda *a, **k: None}
        windows = Path(os.environ["SystemRoot"])
        with patch.dict(os.environ, {"PATH": r"C:\foreign-tools\poppler;C:\other-qt"}):
            exec(compile((root / "Binity.spec").read_text("utf-8"), "Binity.spec", "exec"), namespace)
        self.assertEqual(observed, [str(Path(sys.executable).parent), str(Path(sys.base_prefix)),
                                   str(Path(sys.base_prefix) / "DLLs"),
                                   str(windows / "System32"), str(windows)])


if __name__ == "__main__":
    unittest.main()

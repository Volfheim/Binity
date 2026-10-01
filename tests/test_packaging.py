"""Ensure dependency analysis never inherits unrelated native tools from PATH."""

import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


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

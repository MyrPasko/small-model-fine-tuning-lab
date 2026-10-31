import unittest
from importlib.metadata import version

from fine_tuning_lab import __version__


class TestPackage(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(__version__, "0.1.0")

    def test_installed_distribution_version_matches_package_version(self) -> None:
        self.assertEqual(version("small-model-fine-tuning-lab"), __version__)

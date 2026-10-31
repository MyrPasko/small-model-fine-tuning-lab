import unittest
from fine_tuning_lab import __version__

class Test(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(__version__, "0.1.0")
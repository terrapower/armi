"""macroXSGenerationInterface tests."""
import unittest

from armi.physics.neutronics.macroXSGenerationInterface import (
    MacroXSGenerationInterface,
)
from armi.reactor.tests.test_reactors import loadTestReactor
from armi.settings import Settings


class TestMacroXSGenerationInterface(unittest.TestCase):
    def test_macroXSGenerationInterface(self):
        cs = Settings()
        o, r = loadTestReactor()
        i = MacroXSGenerationInterface(r, cs)

        self.assertIsNone(i.macrosLastBuiltAt)
        self.assertEqual(i.name, "macroXsGen")


if __name__ == "__main__":
    unittest.main()

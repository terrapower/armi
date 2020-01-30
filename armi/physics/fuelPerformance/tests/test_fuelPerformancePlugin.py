"""
Tests for generic fuel performance plugin.
"""
import unittest

from armi.tests.test_plugins import TestPlugin
from armi.physics.fuelPerformance.plugin import FuelPerformancePlugin


class TestFuelPerformancePlugin(TestPlugin):
    plugin = FuelPerformancePlugin


if __name__ == "__main__":
    unittest.main()

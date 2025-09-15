"""Test utilities for :mod:`armi.physics.fuelCycle.fuelHandlerFactory`."""


class FileFuelHandler:
    """Fuel handler used when importing from a file path."""

    def __init__(self, operator):
        self.operator = operator


class ModuleFuelHandler:
    """Fuel handler used when importing from a module path."""

    def __init__(self, operator):
        self.operator = operator

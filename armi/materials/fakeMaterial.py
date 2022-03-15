"""fake test materials for unit tests in armi.reactor.converters.tests.test_axialExpansionChanger"""
from armi.materials.ht9 import HT9
from armi.utils import units

class Fake(HT9):
    """
    Fake material based on HT9, used to verify
    assembly axial expansion
    """
    name = "Fake"

    def __init__(self):
        HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.02*Tc

class FakeException(HT9):
    """
    Fake material based on HT9, used to verify exceptions
    in assembly axial expansion
    """
    name = "FakeException"

    def __init__(self):
        HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.08*Tc

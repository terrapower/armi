"""fake test materials for unit tests in armi.reactor.converters.tests.test_axialExpansionChanger"""
from armi.materials.ht9 import HT9
from armi.utils import units


class Fake(HT9):  # pylint: disable=abstract-method
    """Fake material used to verify armi.reactor.converters.axialExpansionChanger

    Notes
    -----
    - specifically used armi.reactor.converters.tests.test_axialExpansionChanger.py:TestAxialExpansionHeight
      to verify axialExpansionChanger produces expected heights from hand calculation
    - also used to verify mass and height conservation resulting from even amounts of expansion
      and contraction. See armi.reactor.converters.tests.test_axialExpansionChanger.py:TestConservation
    """

    name = "Fake"

    def __init__(self):
        HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.02 * Tc


class FakeException(HT9):  # pylint: disable=abstract-method
    """Fake material used to verify armi.reactor.converters.tests.test_axialExpansionChanger.py:TestExceptions

    Notes
    -----
    - the only difference between this and `class Fake(HT9)` above is that the thermal expansion factor
      is higher to ensure that a negative block height is caught in
      armi.reactor.converters.tests.test_axialExpansionChanger.py:TestExceptions:test_AssemblyAxialExpansionException.
    """

    name = "FakeException"

    def __init__(self):
        HT9.__init__(self)

    def linearExpansionPercent(self, Tk=None, Tc=None):
        """ A fake linear expansion percent"""
        Tc = units.getTc(Tc, Tk)
        return 0.08 * Tc

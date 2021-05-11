"""
Modifies inputs related to neutronics controls

Notes
-----
This may make more sense in the neutronics physics plugin.
"""

from armi.cases.inputModifiers import inputModifiers


class NeutronicConvergenceModifier(inputModifiers.InputModifier):
    """
    Adjust the neutronics convergence parameters ``epsEig``, ``epsFSAvg``, and ``epsFSPoint``.

    The supplied value is used for ``epsEig``. ``epsFSAvg`` and ``epsFSPoint`` are set
    to 100 times the supplied value.

    This can be used to perform sensitivity studies on convergence criteria.
    """

    def __init__(self, value):
        inputModifiers.InputModifier.__init__(self, {self.__class__.__name__: value})
        self.value = value
        if value > 1e-2 or value <= 0.0:
            raise ValueError(
                "Neutronic convergence modifier value must be greater than 0 and less "
                "than 1e-2 (got {})".format(value)
            )

    def __call__(self, cs, blueprints, geom):
        cs["epsFSAvg"] = self.value * 100
        cs["epsFSPoint"] = self.value * 100
        cs["epsEig"] = self.value


class NeutronicMeshsSizeModifier(inputModifiers.InputModifier):
    """
    Adjust the neutronics mesh in all assemblies by a multiplication factor.

    This can be useful when switching between nodal and finite difference
    approximations, or when doing mesh convergence sensitivity studies.

    Attributes
    ----------
    multFactor : int
        Factor to multiply the number of axial mesh points per block by.
    """

    def __init__(self, multFactor):
        inputModifiers.InputModifier.__init__(
            self, {self.__class__.__name__: multFactor}
        )
        if not isinstance(multFactor, int):
            raise TypeError(
                "multFactor must be an integer, but got {}".format(multFactor)
            )
        self.multFactor = multFactor

    def __call__(self, cs, blueprints, geom):
        for assemDesign in blueprints.assemDesigns:
            assemDesign.axialMeshPoints = [
                ax * self.multFactor for ax in assemDesign.axialMeshPoints
            ]

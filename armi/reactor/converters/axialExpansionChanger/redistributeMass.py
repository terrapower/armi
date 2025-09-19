import re
import typing
from math import isclose
from textwrap import dedent

from numpy import sum
from scipy.optimize import brentq

from armi import runLog
from armi.reactor.flags import Flags
from armi.utils import densityTools, units

if typing.TYPE_CHECKING:
    from armi.reactor.components.component import Component


class RedistributeMass:
    """Given ``deltaZTop``, add mass from ``fromComp`` and give it to ``toComp``.

    Parameters
    ----------
    fromComp
        Component which is going to give mass to toComp
    toComp
        Component that is recieving mass from fromComp
    deltaZTop
        The length, in cm, of fromComp being given to toComp
    initOnly
        Optional parameter to only initialize the class and not perform the redistribution. If True, the redistribution
        can be executed by calling :py:meth:`performRedistribution`.
    """

    def __init__(
        self, fromComp: "Component", toComp: "Component", deltaZTop: float, assemName: str, initOnly: bool = False
    ):
        self.fromComp = fromComp
        self.toComp = toComp
        self.assemblyName: str = assemName
        self.deltaZTop = deltaZTop
        self.massFrom: float = 0.0
        self.massTo: float = 0.0
        if not initOnly:
            self.performRedistribution()

    def performRedistribution(self):
        """Perform the mass redistribution between two compatible components."""
        if self.compatabilityCheck():
            self.setNewToCompNDens()
            self.setNewToCompTemperature()
            if self.fromComp.p.hmNuclidesBOL is not None and self.toComp.p.hmNuclidesBOL is not None:
                self.updateBOLParams()

    @property
    def fromCompVolume(self):
        return self.fromComp.getArea() * abs(self.deltaZTop)

    @property
    def toCompVolume(self):
        return self.toComp.getArea() * self.toComp.height

    @property
    def newVolume(self):
        """Compute and return the new post-redistribution volume of toComp."""
        return self.toCompVolume + self.fromCompVolume

    def compatabilityCheck(self) -> bool:
        """Ensure fromComp and toComp are the same material.

        Notes
        -----
        If the linked components are not the same material, we cannot transfer mass between materials because then the
        resulting material has unknown properties.

        Returns
        -------
        False if incompatible; true otherwise.
        """
        if type(self.fromComp.material) is not type(self.toComp.material):
            msg = f"""
            Cannot redistribute mass between components that are different materials!
                Trying to redistribute mass between the following components in {self.assemblyName}:
                    from --> {self.fromComp.parent} : {self.fromComp} : {type(self.fromComp.material)}
                      to --> {self.toComp.parent} : {self.toComp} : {type(self.toComp.material)}

                Instead, mass will be removed from ({self.fromComp} | {type(self.fromComp.material)}) and
                ({self.toComp} | {type(self.toComp.material)} will be artificially expanded. The consequence is that
                mass conservation is no longer guaranteed for the {self.toComp.getType()} component type on this
                assembly!
            """
            runLog.warning(dedent(msg), label="Cannot redistribute mass between different materials.", single=True)
            return False
        return True

    def setNewToCompNDens(self):
        """Calculate the post-redistribution number densities for toComp and determine how much mass is in play for
        fromComp and toComp.

        Notes
        -----
        Only the mass of ``toComp`` is changed in this method. The mass of ``fromComp`` is changed separately by
        changing the height of ``fromComp`` -- the number densities of ``fromComp`` are not modified. When
        redistributing mass, if ``fromComp`` and ``toComp`` are different temperatures, the temperature of
        ``toComp`` will change. See :py:meth:`setNewToCompTemperature`.
        """
        # calculate the mass of each nuclide and then the ndens for the new mass
        newNDens: dict[str, float] = {}
        nucs = self._getAllNucs(self.toComp.getNuclides(), self.fromComp.getNuclides())
        for nuc in nucs:
            massByNucFrom = densityTools.getMassInGrams(nuc, self.fromCompVolume, self.fromComp.getNumberDensity(nuc))
            massByNucTo = densityTools.getMassInGrams(nuc, self.toCompVolume, self.toComp.getNumberDensity(nuc))
            newNDens[nuc] = densityTools.calculateNumberDensity(nuc, massByNucFrom + massByNucTo, self.newVolume)
            self.massFrom += massByNucFrom
            self.massTo += massByNucTo

        # Set newNDens on toComp
        self.toComp.setNumberDensities(newNDens)

    def setNewToCompTemperature(self):
        r"""Calculate and set the post-redistribution temperature of toComp.

        Notes
        -----
        Calculating this new temperature is non trivial due to thermal expansion. The following defines what the area
        of ``toComp`` is post-redistribution,

        .. math::

            A_1(\hat{T}) \left( H_1 + \delta \right) &= A_1(T_1) H_1 + A_2(T_2)\delta,\\
            A_1(\hat{T}) &= \frac{A_1(T_1) H_1 + A_2(T_2)\delta}{H_1 + \delta}.

        Where, :math:`A_1, T_1, H_1`, are the area, temperature, and height of ``toComp``, :math:`A_2, T_2`, are the
        area and temparature of ``fromComp``, :math:`\delta` is the parameter ``deltaZTop``, and :math:`\hat{T}` is
        the new temperature of ``toComp`` post-redistribution. :func:`scipy.optimize.brentq` is used to
        find the root of the above equation, indicating the value for :math:`\hat{T}`
        that finds the desired area, post-redistribution of mass.
        """
        if isclose(self.fromComp.temperatureInC, self.toComp.temperatureInC, rel_tol=1e-09):
            # per isclose documentation, rel_tol of 1e-09 is roughly equivaluent to ensuring the temps are
            # the same to roughly 9 digits.
            newToCompTemp = self.toComp.temperatureInC
        else:
            targetArea = self.newVolume / (self.toComp.height + abs(self.deltaZTop))
            try:
                newToCompTemp = brentq(
                    f=lambda T: self.toComp.getArea(Tc=T) - targetArea,
                    a=self.fromComp.temperatureInC,
                    b=self.toComp.temperatureInC,
                )
            except ValueError:
                totalMass = self.massFrom + self.massTo
                newToCompTemp = (
                    self.massFrom / totalMass * self.fromComp.temperatureInC
                    + self.massTo / totalMass * self.toComp.temperatureInC
                )
                if (self.toComp.hasFlags(Flags.FUEL) or self.toComp.hasFlags(Flags.CONTROL)) or (
                    self.fromComp.hasFlags(Flags.FUEL) or self.fromComp.hasFlags(Flags.CONTROL)
                ):
                    msg = f"""
                    Temperature search algorithm in axial expansion has failed in {self.assemblyName}
                    Trying to search for new temp between
                        from --> {self.fromComp.parent} : {self.fromComp} : {type(self.fromComp.material)} at {self.fromComp.temperatureInC} C
                        to --> {self.toComp.parent} : {self.toComp} : {type(self.toComp.material)} at {self.toComp.temperatureInC} C

                    f({self.fromComp.temperatureInC}) = {self.toComp.getArea(Tc=self.fromComp.temperatureInC) - targetArea}
                    f({self.toComp.temperatureInC}) = {self.toComp.getArea(Tc=self.toComp.temperatureInC) - targetArea}

                    Instead, a mass weighted average temperature of {newToCompTemp} will be used. The consequence is that
                    mass conservation is no longer guaranteed for this component type on this assembly!
                    """  # noqa: E501
                    runLog.warning(dedent(msg), label="Temp Search Failure")
            except Exception as ee:
                raise ee

        # Do not use component.setTemperature as this mucks with the number densities we just calculated.
        self.toComp.temperatureInC = newToCompTemp
        self.toComp.clearCache()

    def updateBOLParams(self):
        """Update the BOL molesHmBOL and massHmBOL to stay consistent with the change in mass.

        Notes
        -----
        Unlike the non-BOL information determined in py:meth:`setNewToCompNDens` and :py:meth:`setNewToCompTemperature`,
        a new BOL temperature is not neccessary to be calculated here since we do not compute the ``massHmBOL`` or
        ``moledHmBOL`` information on-the-fly; this allows us to directly set the new values. However, we do need to
        compute the number densities and manually shift mass to account for the possibility of varying temperatures
        between toComp and fromComp at BOL.
        """
        # build the BOL HM NDens dictionary
        fromCompBOLNucs = [nucName.decode() for nucName in self.fromComp.p.hmNuclidesBOL]
        toCompBOLNucs = [nucName.decode() for nucName in self.toComp.p.hmNuclidesBOL]
        fromCompNDensBOL = dict(zip(fromCompBOLNucs, self.fromComp.p.hmNumberDensitiesBOL))
        toCompNDensBOL = dict(zip(toCompBOLNucs, self.toComp.p.hmNumberDensitiesBOL))

        # calculate the new BOL volume
        toCompVolBOL = self.toComp.getArea(Tc=self.toComp.p.temperatureInCBOL) * self.toComp.parent.p.heightBOL
        fromCompVolBOL = self.fromComp.getArea(Tc=self.fromComp.p.temperatureInCBOL) * abs(self.deltaZTop)
        newBOLVol = toCompVolBOL + fromCompVolBOL

        # calculate new molesHmBOL and massHmBOL for toComp
        newHMNDensBOL: dict[str, float] = {}
        hmNucsBOL = self._getAllNucs(fromCompBOLNucs, toCompBOLNucs)
        for nuc in hmNucsBOL:
            hmMassBOLByNucFromComp = densityTools.getMassInGrams(nuc, fromCompVolBOL, fromCompNDensBOL.get(nuc, 0.0))
            hmMassBOLByNucToComp = densityTools.getMassInGrams(nuc, toCompVolBOL, toCompNDensBOL.get(nuc, 0.0))
            newHMNDensBOL[nuc] = densityTools.calculateNumberDensity(
                nuc, hmMassBOLByNucFromComp + hmMassBOLByNucToComp, newBOLVol
            )
        self.toComp.p.molesHmBOL = (
            sum(list(newHMNDensBOL.values())) / units.MOLES_PER_CC_TO_ATOMS_PER_BARN_CM * newBOLVol
        )
        self.toComp.p.massHmBOL = densityTools.calculateMassDensity(newHMNDensBOL) * newBOLVol

        # update BOL Params for fromComp
        self.fromComp.p.molesHmBOL *= 1.0 - (abs(self.deltaZTop) / self.fromComp.parent.p.heightBOL)
        self.fromComp.p.massHmBOL *= 1.0 - (abs(self.deltaZTop) / self.fromComp.parent.p.heightBOL)

    @staticmethod
    def _sortKey(item):
        """Break isotope string down by element, atomic weight, and metastable state for sorting. Raises a RuntimeError
        if the string does not match the expected pattern.
        """
        pattern = re.compile(
            r"""
            ([a-zA-Z]{1,2}) # Element
            (\d{1,3})?      # atomic weight (optional, e.g., "C")
            ([a-zA-Z])?     # metastable state (optional, e.g., Am242M or Am242)
            """,
            re.VERBOSE,
        )
        match = re.search(pattern, item)
        if match:
            # Convert numeric parts to int for correct numerical sorting
            element = match.group(1)
            atomicWeight = int(match.group(2)) if match.group(2) else 0
            metastable = 1 if match.group(3) else 0
            return (atomicWeight, element, metastable)
        raise RuntimeError(f"Unknown isotope! - {item}")

    def _getAllNucs(self, nucsA: list[str], nucsB: list[str]) -> list[str]:
        """Return a list that contains all of the nuclides in nucsA and nucsB.

        Notes
        -----
        The returned list is sorted by :py:meth:`sortKey`. Isotopes are sorted based on 1) atomic weight, 2) element,
        and 3) metastable state.
        """
        nucsToAdd = set(nucsA).union(set(nucsB))
        return sorted(nucsToAdd, key=self._sortKey)

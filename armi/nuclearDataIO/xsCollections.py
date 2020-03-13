# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Cross section collections contain cross sections for a single nuclide or region.

Specifically, they are used as attributes of :py:class:`~armi.nuclearDataIO.xsNuclides.XSNuclide`, which
then are combined as a :py:class:`~armi.nuclearDataIO.xsLibraries.XSLibrary`.

These may represent microscopic or macroscopic neutron or photon cross sections. When they are macroscopic,
they generally represent a whole region with many nuclides, though this is not required.

See Also
--------
armi.nuclearDataIO.xsCollection.XSCollection : object that gets created.

Examples
--------
# creating a MicroscopicXSCollection by loading one from ISOTXS.
microLib = armi.nuclearDataIO.ISOTXS('ISOTXS')
micros = myLib.nuclides['U235AA'].micros

# creating macroscopic XS:
mc = MacroscopicCrossSectionCreator()
macroCollection = mc.createMacrosFromMicros(microLib, block)
blocksWithMacros = mc.createMacrosOnBlocklist(microLib, blocks)

"""
import numpy
from scipy import sparse

from armi import runLog
from armi.localization import exceptions
from armi.utils import properties
from armi.utils import units

# Basic cross-section types that are represented by a 1-D vector in the multigroup approximation
# No one is particularly proud of these names...we can claim
# they have some origin in the ISOTXS file format card 04 definition
# fmt: off
NGAMMA = "nGamma"      # radiative capture
NAPLHA = "nalph"       # (n, alpha)
NP = "np"              # (n, proton)
ND = "nd"              # (n, deuteron)
NT = "nt"              # (n, triton)
FISSION_XS = "fission" # (n, fission)
N2N_XS = "n2n"         # (n,2n)
NUSIGF = "nuSigF"      
NU = "neutronsPerFission"
# fmt: on
CAPTURE_XS = [NGAMMA, NAPLHA, NP, ND, NT]

# Cross section types that are represented by 2-D matrices in the multigroup approximation
BASIC_SCAT_MATRIX = ["elasticScatter", "inelasticScatter", "n2nScatter"]
OTHER_SCAT_MATRIX = ["totalScatter", "elasticScatter1stOrder"]
HIGHORDER_SCATTER = "higherOrderScatter"

# Subset of vector xs used to evaluate absorption cross-section
ABSORPTION_XS = CAPTURE_XS + [FISSION_XS, N2N_XS]

# Subset of vector xs evaluated by _convertBasicXS
BASIC_XS = ABSORPTION_XS + [NUSIGF]

# Subset vector xs that are derived from basic cross sections
DERIVED_XS = ["absorption", "removal"]

# Total and transport are treated differently since they are 2D (can have multiple moments)
TOTAL_XS = ["total", "transport"]

# Subset of all basic cross sections that include removal and scattering
ALL_XS = BASIC_XS + BASIC_SCAT_MATRIX + OTHER_SCAT_MATRIX + DERIVED_XS + TOTAL_XS

# All xs collection data
ALL_COLLECTION_DATA = ALL_XS + [
    "chi",
    NU,
    "strpd",
    HIGHORDER_SCATTER,
    "diffusionConstants",
]

E_CAPTURE = "ecapt"
E_FISSION = "efiss"


class XSCollection(object):
    """A cross section collection."""

    _zeroes = {}
    """
    A dict of numpy arrays set to the size of XSLibrary.numGroups.

    This is used to initialize cross sections which may not exist for the specific nuclide.
    Consequently, there should never be a situation where a cross section does not exist.
    In addition, they are all pointers to the same array, so we're not generating too much
    unnecessary data.

    Notes
    -----
    This is a dict so that it can store multiple 0_g "matricies", i.e. vectors. Realistically,
    during any given run there will only be a set of groups, e.g. 33.
    """

    @classmethod
    def getDefaultXs(cls, numGroups):
        default = cls._zeroes.get(numGroups, None)
        if default is None:
            default = numpy.zeros(numGroups)
            cls._zeroes[numGroups] = default
        return default

    def __init__(self, parent):
        """
        Construct a NuclideCollection.
        
        Parameters
        ----------
        parent : object
            The parent container, which may be a region, a nuclide, a block, etc.
        """
        self.numGroups = None
        self.transport = None
        self.total = None
        self.nGamma = None
        self.fission = None
        self.neutronsPerFission = None
        self.chi = None
        self.nalph = None
        self.np = None
        self.n2n = None
        self.nd = None
        self.nt = None
        self.strpd = None
        self.elasticScatter = None
        self.inelasticScatter = None
        self.n2nScatter = None
        self.elasticScatter1stOrder = None
        self.totalScatter = None
        self.absorption = None
        self.diffusionConstants = None
        self.removal = None
        self.nuSigF = None
        self.higherOrderScatter = {}
        self.source = "{}".format(parent)

    def __getitem__(self, key):
        """
        Access cross sections by key string (e.g. micros['fission'] = micros.fission.
        
        Notes
        -----
        These containers were originally
        dicts, but upgraded to objects with numpy values as specialization
        was needed. This access method could/should be phased out.
        """
        return self.__dict__[key]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def get(self, key, default):
        try:
            return self[key]
        except (IndexError, KeyError, TypeError):
            return default

    def getAbsorptionXS(self):
        """Return total absorption XS, which is the sum of capture + fission + others."""
        absXS = [
            self.nGamma,
            self.fission,
            self.nalph,
            self.np,
            self.nd,
            self.nt,
            self.n2n,
        ]
        return absXS

    def getTotalScatterMatrix(self):
        """
        Sum up scatter matrices to produce total scatter matrix.

        Multiply reaction-based n2n scatter matrix by 2.0 to convert to production-based.

        .. warning:: Not all lattice codes store (n,2n) matrices consistently. Some are 
                     production-based and some are absorption-based. If you use an
                     absorption-based one, your scatter matrix will be off, generally
                     leading to about a percent error in your neutron balance.

        Notes
        -----
        The total scattering matrix is produced by summing the elastic, inelastic, and n2n scattering matrices. If a
        specific scattering matrix does not exist for a composition (nuclide or region) then it is skipped and a
        warning is displayed stating that the scattering reaction is not available and is not included in the total
        scattering matrix.

        Example: When producing macroscopic cross sections in MC2-3 the code internally merges the elastic and
        inelastic scattering matrices into a single elastic scattering matrix.
        """
        scatters = []
        totalScatterComponents = {
            "elastic": self.elasticScatter,
            "inelastic": self.inelasticScatter,
            "n2n": self.n2nScatter * 2.0,
        }
        for sType, sMatrix in totalScatterComponents.items():
            if sMatrix is not None:
                scatters.append(sMatrix)
            else:
                runLog.warning(
                    "{} scattering matrix in {} is not defined. Generating total scattering matrix"
                    " without this data".format(sType.title(), self),
                    single=True,
                )
        return sum(scatters)

    def clear(self):
        """Zero out all the cross sections; this is useful for creating dummy cross sections."""
        for xsAttr in ALL_XS:
            value = getattr(self, xsAttr)
            # it should either be a list, a numpy array, or a sparse matrix
            if isinstance(value, list):
                value = [0.0] * len(value)
            elif isinstance(value, numpy.ndarray):
                value = numpy.zeros(value.shape)
            elif value is None:  # assume it is scipy.sparse
                pass
            elif value.nnz >= 0:
                value = sparse.csr_matrix(value.shape)
            setattr(self, xsAttr, value)
        # need to do the same thing for the higherOrderScatter
        for kk, currentMatrix in self.higherOrderScatter.items():
            self.higherOrderScatter[kk] = sparse.csr_matrix(currentMatrix.shape)

    @staticmethod
    def collapseCrossSection(crossSection, weights):
        r"""
        Collapse a cross section into 1-group.

        This is extremely useful for many analyses such as doing a shielding efficacy survey
        or computing one-group reaction rates.

        .. math::
        
            \bar{\sigma} = \frac{\sum_g{\sigma_g \phi_g}}{\sum_g{\phi_g}}

        Parameters
        ----------
        crossSection : list
            Multigroup cross section values
        weights : list
            energy group weights to apply (usually the multigroup flux)

        Returns
        -------
        oneGroupXS : float
            The one group cross section in the same units as the input cross section.
        """
        mult = numpy.array(crossSection) * numpy.array(weights)
        return sum(mult) / sum(weights)

    def compare(self, other, flux, relativeTolerance=0, verbose=False):
        """Compare the cross sections between two XSCollections objects."""
        equal = True
        for xsName in ALL_COLLECTION_DATA:

            myXsData = self.__dict__[xsName]
            theirXsData = other.__dict__[xsName]

            if xsName == HIGHORDER_SCATTER:
                for actualList, expectedList in zip(myXsData, theirXsData):
                    if actualList != expectedList:
                        equal = False
                        runLog.important(
                            "  {} {:<30} cross section is different.".format(
                                self.source, xsName
                            )
                        )

            elif sparse.issparse(myXsData) and sparse.issparse(theirXsData):
                if not numpy.allclose(
                    myXsData.todense(),
                    theirXsData.todense(),
                    rtol=relativeTolerance,
                    atol=0.0,
                ):
                    verboseData = (
                        ""
                        if not verbose
                        else "\n{},\n\n{}".format(myXsData, theirXsData)
                    )
                    runLog.important(
                        "  {} {:<30} cross section is different.{}".format(
                            self.source, xsName, verboseData
                        )
                    )
                    equal = False
            elif isinstance(myXsData, dict) and myXsData != theirXsData:
                # there are no dicts currently so code is untested
                raise NotImplementedError("there are no dicts")
            elif not properties.areEqual(myXsData, theirXsData, relativeTolerance):
                verboseData = (
                    "" if not verbose else "\n{},\n\n{}".format(myXsData, theirXsData)
                )
                runLog.important(
                    "  {} {:<30} cross section is different.{}".format(
                        self.source, xsName, verboseData
                    )
                )
                equal = False
        return equal

    def merge(self, other):
        """
        Merge the cross sections of two collections.

        Notes
        -----
        1. This can only merge if one hasn't been assigned at all, because it doesn't try to figure out how to
           account for overlapping cross sections.
        2. Update the current library (self) with values from the other library if all attributes in the library except
           ones in `attributesToIgnore` are None.
        3. Libraries are already merged if all attributes in the other library are None (This is nothing to merge!).
        """
        attributesToIgnore = ["source", HIGHORDER_SCATTER]
        if all(
            v is None for k, v in self.__dict__.items() if k not in attributesToIgnore
        ):
            self.__dict__.update(other.__dict__)  # See note 2
        elif all(
            v is None for k, v in other.__dict__.items() if k not in attributesToIgnore
        ):
            pass  # See note 3
        else:
            overlappingAttrs = set(
                k for k, v in self.__dict__.items() if v is not None and k != "source"
            )
            overlappingAttrs &= set(
                k for k, v in other.__dict__.items() if v is not None and k != "source"
            )
            raise exceptions.XSLibraryError(
                "Cannot merge {} and {}.\n Cross sections overlap in "
                "attributes: {}.".format(
                    self.source, other.source, ", ".join(overlappingAttrs)
                )
            )
            raise exceptions.XSLibraryError(
                "Cannot merge from and from \n Cross sections overlap in "
                "attributes:."
            )


class MacroscopicCrossSectionCreator(object):
    """
    Create macroscopic cross sections from micros and number density.

    Object encapsulating all high-level methods related to the creation of
    macroscopic cross sections.
    """

    def __init__(self, buildScatterMatrix=True, buildOnlyCoolant=False):
        self.densities = None
        self.macros = None
        self.micros = None
        self.buildScatterMatrix = buildScatterMatrix
        self.buildOnlyCoolant = (
            buildOnlyCoolant  # TODO: this is not implemented yet. is it needed?
        )
        self.block = None

    def createMacrosOnBlocklist(
        self, microLibrary, blockList, nucNames=None, libType="micros"
    ):
        for block in blockList:
            block.macros = self.createMacrosFromMicros(
                microLibrary, block, nucNames, libType=libType
            )
        return blockList

    def createMacrosFromMicros(
        self, microLibrary, block, nucNames=None, libType="micros"
    ):
        """
        Creates a macroscopic cross section set based on a microscopic XS library using a block object

        Micro libraries have lots of nuclides, but macros only have 1.

        Parameters
        ----------
        microLibrary : xsCollection.XSCollection
            Input micros

        block : Block
            Object whos number densities should be used to generate macros

        nucNames : list, optional
            List of nuclides to include in the macros. Defaults to all in block.

        libType : str, optional
            The block attribute containing the desired microscopic XS for this block:
            either "micros" for neutron XS or "gammaXS" for gamma XS.

        Returns
        -------
        macros : xsCollection.XSCollection
            A new XSCollection full of macroscopic cross sections

        """
        runLog.debug("Building macroscopic cross sections for {0}".format(block))
        if nucNames is None:
            nucNames = block.getNuclides()

        self.microLibrary = microLibrary
        self.block = block
        self.xsSuffix = block.getMicroSuffix()
        self.macros = XSCollection(parent=block)
        self.densities = dict(zip(nucNames, block.getNuclideNumberDensities(nucNames)))
        self.ng = getattr(self.microLibrary, "numGroups" + _getLibTypeSuffix(libType))

        self._initializeMacros()
        self._convertBasicXS(libType=libType)
        self._computeAbsorptionXS()
        self._convertScatterMatrices(libType=libType)
        self._computeDiffusionConstants()
        self._buildTotalScatterMatrix()
        self._computeRemovalXS()
        self.macros.chi = computeBlockAverageChi(
            b=self.block, isotxsLib=self.microLibrary
        )

        return self.macros

    def _initializeMacros(self):
        m = self.macros
        for xsName in BASIC_XS + DERIVED_XS:
            setattr(m, xsName, numpy.zeros(self.ng))

        for matrixName in BASIC_SCAT_MATRIX:
            # lil_matrices are good for indexing but bad for certain math operations.
            # use csr for faster math
            setattr(m, matrixName, sparse.csr_matrix((self.ng, self.ng)))

    def _convertBasicXS(self, libType="micros"):
        """
        Converts basic XS such as fission, nGamma, etc.

        Parameters
        ----------
        libType : str, optional
            The block attribute containing the desired microscopic XS for this block:
            either "micros" for neutron XS or "gammaXS" for gamma XS.
        """
        reactions = BASIC_XS + TOTAL_XS
        if NUSIGF in reactions:
            reactions.remove(NUSIGF)
            self.macros[NUSIGF] = computeMacroscopicGroupConstants(
                FISSION_XS,
                self.densities,
                self.microLibrary,
                self.xsSuffix,
                libType=libType,
                multConstant=NU,
            )

        for reaction in reactions:
            self.macros[reaction] = computeMacroscopicGroupConstants(
                reaction,
                self.densities,
                self.microLibrary,
                self.xsSuffix,
                libType=libType,
            )

    def _convertScatterMatrices(self, libType="micros"):
        """
        Build macroscopic scatter matrices.

        Parameters
        ----------
        libType : str, optional
            The block attribute containing the desired microscopic XS for this block:
            either "micros" for neutron XS or "gammaXS" for gamma XS.
        """

        if not self.buildScatterMatrix:
            return

        for nuclide in self.microLibrary.getNuclides(self.xsSuffix):
            microCollection = getattr(nuclide, libType)
            nDens = self.densities.get(nuclide.name, 0.0)
            if microCollection.elasticScatter is not None:
                self.macros.elasticScatter += microCollection.elasticScatter * nDens
            if microCollection.inelasticScatter is not None:
                self.macros.inelasticScatter += microCollection.inelasticScatter * nDens
            if microCollection.n2nScatter is not None:
                self.macros.n2nScatter += microCollection.n2nScatter * nDens

    def _computeAbsorptionXS(self):
        """
        Absorption = sum of all absorption reactions.

        Must be called after :py:meth:`_convertBasicXS`.
        """
        for absXS in self.macros.getAbsorptionXS():
            self.macros.absorption += absXS

    def _computeDiffusionConstants(self):
        self.macros.diffusionConstants = 1.0 / (3.0 * self.macros.transport)

    def _buildTotalScatterMatrix(self):
        self.macros.totalScatter = self.macros.getTotalScatterMatrix()

    def _computeRemovalXS(self):
        """
        Compute removal cross section (things that remove a neutron from this phase space)

        This includes all absorptions and outscattering.
        Outscattering is represented by columns of the total scatter matrix.
        Self-scattering (e.g. when g' == g) is not be included. This can be
        handled by summing the columns and then subtracting the diagonal.

        within-group n2n is accounted for by simply not including n2n in the removal xs.
        """
        self.macros.removal = self.macros.absorption - self.macros.n2n
        # columnSum = self.macros.totalScatter.columnSum(self.ng) # convert to ndarray
        columnSum = self.macros.totalScatter.sum(axis=0).getA1()  # convert to ndarray
        # diags = self.macros.totalScatter.diagonal(self.ng)
        diags = self.macros.totalScatter.diagonal()
        self.macros.removal += columnSum - diags


def computeBlockAverageChi(b, isotxsLib):
    r"""
    Return the block average total chi vector based on isotope chi vectors.
    
    This is defined by eq 3.4b in DIF3D manual [DIF3D]_, which corresponds to 1 in A.HMG4C card.

    .. math::
    
                
        \chi_g = \frac{\sum_{n} \chi_{g,n} N_n V \sum_{g'}(\nu_{g'}*\sigma_{f,g'})}{\sum_n N_n V \sum_{g'}(\nu_{g'}*\sigma_{f,g'} )}
                

    To evaluate efficiently, assume that if :math:`\chi_{g,n}=0`, there will be no contributions

    Volume is not used b/c it is already homogenized in the block.
    
    Parameters
    ----------
    b : object
        Block object
    
    isotxsLib : object
        ISOTXS library object
       
    Notes
    -----
    This methodology is based on option 1 in the HMG4C utility (named total 
    fission source weighting).
    """
    numGroups = isotxsLib.numGroups
    numerator = numpy.zeros(numGroups)
    denominator = 0.0
    numberDensities = b.getNumberDensities()
    for nucObj in isotxsLib.getNuclides(b.getMicroSuffix()):
        nucMicroXS = nucObj.micros
        nucNDens = numberDensities.get(nucObj.name, 0.0)
        nuFissionTotal = sum(nucMicroXS.neutronsPerFission * nucMicroXS.fission)
        numerator += nucMicroXS.chi * nucNDens * nuFissionTotal
        denominator += nucNDens * nuFissionTotal
    if denominator != 0.0:
        return numerator / denominator
    else:
        return numpy.zeros(numGroups)


def _getLibTypeSuffix(libType):
    if libType == "micros":
        libTypeSuffix = ""
    elif libType == "gammaXS":
        libTypeSuffix = "Gamma"
    else:
        libTypeSuffix = None
        runLog.warning(
            "ARMI currently supports only micro XS libraries of types "
            '"micros" (neutron) and "gammaXS" (gamma).'
        )

    return libTypeSuffix


def computeNeutronEnergyDepositionConstants(numberDensities, lib, microSuffix):
    """
    Compute the macroscopic neutron energy deposition group constants.

    These group constants can be multiplied by the flux to obtain energy deposition rates.

    Parameters
    ----------
    numberDensities : dict
        nucName keys, number density values (atoms/bn-cm) of all nuclides in the composite for which
        the macroscopic group constants are computed. See composite `getNuclideNumberDensities` method.

    lib : library object
        Microscopic cross section library.

    microSuffix : str
        Microscopic library suffix (e.g. 'AB') for this composite.
        See composite `getMicroSuffix` method.

    Returns
    -------
    energyDepositionConsts : numpy array
        Neutron energy deposition group constants. (J/cm)

    Notes
    -----
    PMATRX documentation says units will be eV/s when multiplied by flux but it's eV/s/cm^3.
    (eV/s/cm^3 = eV-bn * 1/cm^2/s * 1/bn-cm.)

    Converted here to obtain J/cm (eV-bn * 1/bn-cm * J / eV)
    """
    return (
        computeMacroscopicGroupConstants(
            "neutronHeating", numberDensities, lib, microSuffix
        )
        * units.JOULES_PER_eV
    )


def computeGammaEnergyDepositionConstants(numberDensities, lib, microSuffix):
    """
    Compute the macroscopic gamma energy deposition group constants.

    These group constants can be multiplied by the flux to obtain energy deposition rates.

    Parameters
    ----------
    numberDensities : dict
        nucName keys, number density values (atoms/bn-cm) of all nuclides in the composite for which
        the macroscopic group constants are computed. See composite `getNuclideNumberDensities` method.

    lib : library object
        Microscopic cross section library.

    microSuffix : str
        Microscopic library suffix (e.g. 'AB') for this composite.
        See composite `getMicroSuffix` method.

    Returns
    -------
    energyDepositionConsts : numpy array
        gamma energy deposition group constants. (J/cm)

    Notes
    -----
    PMATRX documentation says units will be eV/s when multiplied by flux but it's eV/s/cm^3.
    (eV/s/cm^3 = eV-bn * 1/cm^2/s * 1/bn-cm.)

    Convert here to obtain J/cm (eV-bn * 1/bn-cm * J / eV)
    """
    return (
        computeMacroscopicGroupConstants(
            "gammaHeating", numberDensities, lib, microSuffix
        )
        * units.JOULES_PER_eV
    )


def computeFissionEnergyGenerationConstants(numberDensities, lib, microSuffix):
    r"""
    Get the fission energy generation group constant of a block

    .. math::

        E_{generation_fission} = \kappa_f \Sigma_f

    Power comes from fission and capture reactions.

    Parameters
    ----------
    numberDensities : dict
        nucName keys, number density values (atoms/bn-cm) of all nuclides in the composite for which
        the macroscopic group constants are computed. See composite `getNuclideNumberDensities` method.

    lib : library object
        Microscopic cross section library.

    microSuffix : str
        Microscopic library suffix (e.g. 'AB') for this composite.
        See composite `getMicroSuffix` method.

    Returns
    -------
    fissionEnergyFactor: numpy.array
        Fission energy generation group constants (in Joules/cm)
    """
    fissionEnergyFactor = computeMacroscopicGroupConstants(
        FISSION_XS,
        numberDensities,
        lib,
        microSuffix,
        libType="micros",
        multConstant=E_FISSION,
    )

    return fissionEnergyFactor


def computeCaptureEnergyGenerationConstants(numberDensities, lib, microSuffix):
    r"""
    Get the energy generation group constant of a block

    .. math::

        E_{generation capture} = \kappa_c \Sigma_c


    Typically, one only cares about the flux* this XS (to find total power),
    but the XS itself is required in some sensitivity studies.

    Power comes from fission and capture reactions.

    Parameters
    ----------
    numberDensities : dict
        nucName keys, number density values (atoms/bn-cm) of all nuclides in the composite for which
        the macroscopic group constants are computed. See composite `getNumberDensities` method.

    lib : library object
        Microscopic cross section library.

    microSuffix : str
        Microscopic library suffix (e.g. 'AB') for this composite.
        See composite `getMicroSuffix` method.

    Returns
    -------
    captureEnergyFactor: numpy.array
        Capture energy generation group constants (in Joules/cm)
    """
    captureEnergyFactor = None
    for xs in CAPTURE_XS:
        if captureEnergyFactor is None:
            captureEnergyFactor = numpy.zeros(
                numpy.shape(
                    computeMacroscopicGroupConstants(
                        xs, numberDensities, lib, microSuffix, libType="micros"
                    )
                )
            )

        captureEnergyFactor += computeMacroscopicGroupConstants(
            xs,
            numberDensities,
            lib,
            microSuffix,
            libType="micros",
            multConstant=E_CAPTURE,
        )

    return captureEnergyFactor


def computeMacroscopicGroupConstants(
    constantName,
    numberDensities,
    lib,
    microSuffix,
    libType=None,
    multConstant=None,
    multLib=None,
):
    """
    Compute any macroscopic group constants given number densities and a microscopic library.

    Parameters
    ----------
    constantName : str
        Name of the reaction for which to obtain the group constants. This name should match a
        cross section name or an attribute in the collection.

    numberDensities : dict
        nucName keys, number density values (atoms/bn-cm) of all nuclides in the composite for which
        the macroscopic group constants are computed. See composite `getNuclideNumberDensities` method.

    lib : library object
        Microscopic cross section library.

    microSuffix : str
        Microscopic library suffix (e.g. 'AB') for this composite.
        See composite `getMicroSuffix` method.

    libType : str, optional
        The block attribute containing the desired microscopic XS for this block:
        either "micros" for neutron XS or "gammaXS" for gamma XS.

    multConstant : str, optional
        Name of constant by which the group constants will be multiplied. This name should match a
        cross section name or an attribute in the collection.

    multLib : library object, optional
        Microscopic cross section nuclide library to obtain the multiplier from.
        If None, same library as base cross section is used.

    Returns
    -------
    macroGroupConstant : numpy array
        Macroscopic group constants for the requested reaction.
    """
    skippedNuclides = []
    skippedMultNuclides = []
    macroGroupConstants = None

    # sort the numberDensities because a summation is being performed that may result in slight
    # differences based on the order.
    for nuclideName, numberDensity in sorted(numberDensities.items()):
        if not numberDensity:
            continue
        try:
            libNuclide = lib.getNuclide(nuclideName, microSuffix)
            multLibNuclide = libNuclide
        except KeyError:
            skippedNuclides.append(nuclideName)  # Nuclide does not exist in the library
            continue

        if multLib:
            try:
                multLibNuclide = multLib.getNuclide(nuclideName, microSuffix)
            except KeyError:
                skippedMultNuclides.append(
                    nuclideName
                )  # Nuclide does not exist in the library
                continue

        microGroupConstants = _getMicroGroupConstants(
            libNuclide, constantName, nuclideName, libType
        )

        multiplierVal = _getXsMultiplier(multLibNuclide, multConstant, libType)

        if macroGroupConstants is None:
            macroGroupConstants = numpy.zeros(microGroupConstants.shape)

        if (
            microGroupConstants.shape != macroGroupConstants.shape
            and not microGroupConstants.any()
        ):
            microGroupConstants = numpy.zeros(macroGroupConstants.shape)

        macroGroupConstants += (
            numpy.asarray(numberDensity) * microGroupConstants * multiplierVal
        )

    if skippedNuclides:
        msg = "The following nuclides are not in microscopic library {}: {}".format(
            lib, skippedNuclides
        )
        runLog.error(msg, single=True)
        raise ValueError(msg)

    if skippedMultNuclides:
        runLog.debug(
            "The following nuclides are not in multiplier library {}: {}".format(
                multLib, skippedMultNuclides
            ),
            single=True,
        )

    return macroGroupConstants


def _getXsMultiplier(libNuclide, multiplier, libType):
    if multiplier:
        try:
            microCollection = getattr(libNuclide, libType)
            multiplierVal = getattr(microCollection, multiplier)
        except:
            multiplierVal = libNuclide.isotxsMetadata[multiplier]
    else:
        multiplierVal = 1.0

    return numpy.asarray(multiplierVal)


def _getMicroGroupConstants(libNuclide, constantName, nuclideName, libType):
    if libType:
        microCollection = getattr(libNuclide, libType)
    else:
        microCollection = libNuclide

    microGroupConstants = numpy.asarray(getattr(microCollection, constantName))

    if not microGroupConstants.any():
        runLog.debug(
            "Nuclide {} does no have {} microscopic group constants.".format(
                nuclideName, constantName
            ),
            single=True,
        )

    return microGroupConstants

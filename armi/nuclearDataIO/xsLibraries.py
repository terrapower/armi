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
Cross section library objects. 

Cross section libraries, currently, contain neutron and/or gamma
cross sections, but are not necessarily intended to be only neutron and gamma data.
"""

import re
import os
import glob

from matplotlib import pyplot

from armi import runLog
from armi.localization.exceptions import CompxsError
from armi.nuclearDataIO.nuclearFileMetadata import NuclideXSMetadata, RegionXSMetadata
from armi.utils import properties
from armi.nucDirectory import nuclideBases
from armi.localization import exceptions

_ISOTXS_EXT = "ISO"


def compare(lib1, lib2):
    """Compare two XSLibraries, and return True if equal, or False if not."""
    from armi.nuclearDataIO import isotxs
    from armi.nuclearDataIO import gamiso
    from armi.nuclearDataIO import pmatrx

    equal = True
    # check the nuclides
    equal &= _checkLabels(lib1, lib2)
    equal &= _checkLabels(lib2, lib1)
    equal &= isotxs.compare(lib1, lib2)
    equal &= gamiso.compare(lib1, lib2)
    equal &= pmatrx.compare(lib1, lib2)
    return equal


def _checkLabels(llib1, llib2):
    mismatch = set(llib1.nuclideLabels) - set(llib2.nuclideLabels)
    if any(mismatch):
        runLog.important(
            "{} has nuclides that are not in {}: {}".format(llib1, llib2, mismatch)
        )
        return False
    return True


def compareXSLibraryAttribute(lib1, lib2, attributeName, tolerance=0.0):
    """Compare the values of an attribute in two libraries."""
    val1 = getattr(lib1, "_" + attributeName, None)
    val2 = getattr(lib2, "_" + attributeName, None)
    if not properties.areEqual(val1, val2, tolerance):
        runLog.important(
            "{} and {} have different `{}` attributes:\n{}\n{}".format(
                lib1, lib2, attributeName, val1, val2
            )
        )
        return False
    return True


def compareLibraryNeutronEnergies(lib1, lib2, tolerance=0.0):
    """Compare the neutron velocities and energy upper bounds for two libraries."""
    equals = True
    equals &= compareXSLibraryAttribute(
        lib1, lib2, "neutronEnergyUpperBounds", tolerance
    )
    equals &= compareXSLibraryAttribute(lib1, lib2, "neutronVelocities", tolerance)
    return equals


def getSuffixFromNuclideLabel(nucLabel):
    """
    Return the xs suffix for the nuclide label. 
    
    Parameters
    ----------
    nucLabel: str
        A string representing the nuclide and xs suffix, eg, "U235AA"
        
    Returns
    -------
    suffix: str
        The suffix of this string
    """
    return nucLabel[-2:]


def getISOTXSLibrariesToMerge(xsLibrarySuffix, xsLibFileNames):
    """
    Find ISOTXS libraries out of a list that should be merged based on the provided ``xsLibrarySuffix``

    Parameters
    ----------
    xsLibrarySuffix : str
        XS library suffix is used to determine which ISOTXS files should be merged together. This can be an
        empty string or be something like `-doppler`.

    xsLibFileNames : list
        A list of library names like ISOAA, ISOBA, ISOCA, etc.

    Notes
    -----
    Files that exist: ISOAA-n1, ISOAB-n1, ISOAA-n2, ISOAB-n2, ISOAA, ISOAB, ISODA, ISOBA.
    xsLibrarySuffix: 'n2'
    Results: ISOAA-n2, ISOAB-n2
    """
    isosToMerge = [
        iso
        for iso in xsLibFileNames
        if "ISOTXS" not in iso  # Skip merged ISOTXS file
        and ".ascii" not in iso  # Skip BCD/ascii files
        and "BCD" not in iso
    ]  # Skip BCD/ascii files
    if xsLibrarySuffix != "":
        isosWithSuffix = [
            iso
            for iso in isosToMerge
            if re.match("ISO[A-Z]{{2}}F?{}$".format(xsLibrarySuffix), iso)
        ]
        isosToMerge = [
            iso
            for iso in isosToMerge
            if "-" not in iso
            and not any(iso == iws.split("-")[0] for iws in isosWithSuffix)
        ]
        isosToMerge += isosWithSuffix
    else:
        isosToMerge = [iso for iso in isosToMerge if "-" not in iso]
    return isosToMerge


def mergeXSLibrariesInWorkingDirectory(lib, xsLibrarySuffix="", mergeGammaLibs=False):
    """
    Merge neutron (ISOTXS) and gamma (GAMISO/PMATRX) library data into the provided library.

    Parameters
    ----------
    lib : obj
        ISOTXS library object

    xsLibrarySuffix : str, optional
        XS library suffix used to determine which ISOTXS files are merged together,
        typically something like `-doppler`. If empty string, will merge everything
        without suffix (indicated by a `-`).

    mergeGammaLibs : bool, optional
        If True, the GAMISO and PMATRX files that correspond to the ISOTXS library will be merged. Note: if these
        files do not exist this will fail.
    """
    from armi import nuclearDataIO
    from armi.nuclearDataIO import isotxs
    from armi.nuclearDataIO import gamiso
    from armi.nuclearDataIO import pmatrx

    xsLibFiles = getISOTXSLibrariesToMerge(
        xsLibrarySuffix, [iso for iso in glob.glob(_ISOTXS_EXT + "*")]
    )
    librariesToMerge = []
    neutronVelocities = {}  # Dictionary of neutron velocities from each ISOTXS file
    for xsLibFilePath in sorted(xsLibFiles):
        xsID = re.search("ISO([A-Z0-9]{2})", xsLibFilePath).group(
            1
        )  # get XS ID from the cross section library name
        xsFileTypes = "ISOTXS" if not mergeGammaLibs else "ISOTXS, GAMISO, and PMATRX"
        runLog.info(
            "Retrieving {} data for XS ID {}{}".format(
                xsFileTypes, xsID, xsLibrarySuffix
            )
        )
        if xsLibFilePath in lib.isotxsMetadata.fileNames:
            runLog.extra(
                "Skipping merge of {} because data already exists in the library".format(
                    xsLibFilePath
                )
            )
            continue
        neutronLibrary = isotxs.readBinary(xsLibFilePath)
        neutronVelocities[xsID] = neutronLibrary.neutronVelocity
        librariesToMerge.append(neutronLibrary)
        if mergeGammaLibs:
            dummyNuclides = [
                nuc
                for nuc in neutronLibrary.nuclides
                if isinstance(nuc._base, nuclideBases.DummyNuclideBase)
            ]
            # GAMISO data
            gamisoLibraryPath = nuclearDataIO.getExpectedGAMISOFileName(xsID=xsID)
            gammaLibrary = gamiso.readBinary(gamisoLibraryPath)
            addedDummyData = gamiso.addDummyNuclidesToLibrary(
                gammaLibrary, dummyNuclides
            )  # Add DUMMY nuclide data not produced by MC2-3
            if addedDummyData:
                gamisoDummyPath = os.path.abspath(
                    os.path.join(os.getcwd(), gamisoLibraryPath)
                )
                gamiso.writeBinary(gammaLibrary, gamisoDummyPath)
                gammaLibraryDummyData = gamiso.readBinary(gamisoDummyPath)
                librariesToMerge.append(gammaLibraryDummyData)
            else:
                librariesToMerge.append(gammaLibrary)
            # PMATRX data
            pmatrxLibraryPath = nuclearDataIO.getExpectedPMATRXFileName(xsID=xsID)
            pmatrxLibrary = pmatrx.readBinary(pmatrxLibraryPath)
            addedDummyData = pmatrx.addDummyNuclidesToLibrary(
                pmatrxLibrary, dummyNuclides
            )  # Add DUMMY nuclide data not produced by MC2-3
            if addedDummyData:
                pmatrxDummyPath = os.path.abspath(
                    os.path.join(os.getcwd(), pmatrxLibraryPath)
                )
                pmatrx.writeBinary(pmatrxLibrary, pmatrxDummyPath)
                pmatrxLibraryDummyData = pmatrx.readBinary(pmatrxDummyPath)
                librariesToMerge.append(pmatrxLibraryDummyData)
            else:
                librariesToMerge.append(pmatrxLibrary)
    for library in librariesToMerge:
        lib.merge(library)

    return neutronVelocities


class _XSLibrary(object):
    """Parent class for Isotxs and Compxs library objects."""

    neutronEnergyUpperBounds = properties.createImmutableProperty(
        "neutronEnergyUpperBounds", "an ISOTXS", "Get or set the neutron energy groups."
    )

    neutronVelocity = properties.createImmutableProperty(
        "neutronVelocity", "an ISOTXS", "Get or set the mean neutron velocity in cm/s."
    )

    def __init__(self):
        # each element is a string such as U235AA
        self._orderedNuclideLabels = []

    def __contains__(self, key):
        return key in self._orderedNuclideLabels

    def __setitem__(self, key, value):
        if key in self._orderedNuclideLabels:
            raise exceptions.XSLibraryError("{} already contains {}".format(self, key))
        value.container = self
        self._orderedNuclideLabels.append(key)

    def __getitem__(self, key):
        raise NotImplementedError

    def __delitem__(self, key):
        self._orderedNuclideLabels.remove(key)

    def merge(self, other):
        raise NotImplementedError

    def __len__(self):
        return len(self._orderedNuclideLabels)

    def _mergeNeutronEnergies(self, other):
        self.neutronEnergyUpperBounds = other.neutronEnergyUpperBounds
        # neutron velocity changes, but just use the first one.
        if not hasattr(self, "_neutronVelocity"):
            self.neutronVelocity = other.neutronVelocity

    def items(self):
        for key in self._orderedNuclideLabels:
            yield (key, self[key])


class IsotxsLibrary(_XSLibrary):
    """
    IsotxsLibrary objects are a collection of cross sections (XS) for both neutron and gamma reactions.

    IsotxsLibrary objects must be initialized with data through one of the read methods within this package

    See Also
    --------
    :py:func:`armi.nuclearDataIO.isotxs.readBinary`
    :py:func:`armi.nuclearDataIO.gamiso.readBinary`
    :py:func:`armi.nuclearDataIO.pmatrx.readBinary`
    :py:class:`CompxsLibrary`

    Examples
    --------
    >>> lib = xsLibraries.IsotxsLibrary()
    >>> # this doesn't have any information yet, we can read ISOTXS information
    >>> libIsotxs = isotxs.readBinary('ISOAA')
    >>> # any number of XSLibraries can be merged
    >>> lib.merge(libIsotxs) # now the `lib` contains the ISOAA information.
    """

    def __init__(self):
        _XSLibrary.__init__(self)
        self.pmatrxMetadata = NuclideXSMetadata()
        self.isotxsMetadata = NuclideXSMetadata()
        self.gamisoMetadata = NuclideXSMetadata()

        # keys are nuclide labels such as U235AA
        # vals are XSNuclide objects
        self._nuclides = {}
        self._scatterWeights = {}

    gammaEnergyUpperBounds = properties.createImmutableProperty(
        "gammaEnergyUpperBounds",
        "a PMATRX or GAMISO",
        "Get or set the gamma energy groups.",
    )

    neutronDoseConversionFactors = properties.createImmutableProperty(
        "neutronDoseConversionFactors",
        "a PMATRX",
        "Get or set the neutron dose conversion factors.",
    )

    gammaDoseConversionFactors = properties.createImmutableProperty(
        "gammaDoseConversionFactors",
        "a PMATRX",
        "Get or set the gamma does conversion factors.",
    )

    @property
    def numGroups(self):
        """Get the number of neutron energy groups"""
        return len(self.neutronEnergyUpperBounds)

    @property
    def numGroupsGamma(self):
        """get the number of gamma energy groups"""
        return len(self.gammaEnergyUpperBounds)

    @property
    def xsIDs(self):
        """
        Get the XS ID's present in this library.

        Assumes the suffixes are the last 2 letters in the nucNames
        """
        return list(set(getSuffixFromNuclideLabel(name) for name in self.nuclideLabels))

    def __repr__(self):
        files = (
            self.isotxsMetadata.fileNames
            + self.pmatrxMetadata.fileNames
            + self.gamisoMetadata.fileNames
        )
        if not any(files):
            return "<IsotxsLibrary empty>"
        return "<IsotxsLibrary id:{} containing {} nuclides from {}>".format(
            id(self), len(self), ", ".join(files)
        )

    def __setitem__(self, key, value):
        _XSLibrary.__setitem__(self, key, value)
        self._nuclides[key] = value

    def __getitem__(self, key):
        return self._nuclides[key]

    def get(self, nuclideLabel, default):
        return self._nuclides.get(nuclideLabel, default)

    def getNuclide(self, nucName, suffix):
        """
        Get a nuclide object from the XS library or None.

        Parameters
        ----------
        nucName : str
            ARMI nuclide name, e.g. 'U235', 'PU239'
        suffix : str
            Restrict to a specific nuclide lib suffix e.g. 'AA'

        Returns
        -------
        nuclide : Nuclide object
            A nuclide from the library or None
        """

        libLabel = nuclideBases.byName[nucName].label + suffix
        try:
            return self[libLabel]
        except KeyError:
            runLog.error("Error in {}.\nSee stderr.".format(self))
            raise

    def __delitem__(self, key):
        _XSLibrary.__delitem__(self, key)
        del self._nuclides[key]

    @property
    def nuclideLabels(self):
        """Get the nuclide Names."""
        # need to create a new list so the _orderedNuclideLabels does not get modified.
        return list(self._orderedNuclideLabels)

    @property
    def nuclides(self):
        return [self[name] for name in self._orderedNuclideLabels]

    def getNuclides(self, suffix):
        """Returns a list of the nuclide objects in the library"""
        nucs = []
        # nucName is U235IA, etc.. nuc.name is U235, etc
        for nucLabel, nuc in self.items():
            # `in` used below for support of >26 xs groups
            if not suffix or suffix in getSuffixFromNuclideLabel(nucLabel):
                # accept things with the suffix if one is given
                if nuc not in nucs:
                    nucs.append(nuc)
        return nucs

    def merge(self, other):
        """Merge two XSLibraries"""
        runLog.debug("Merging XS library {} into XS library {}".format(other, self))
        self._mergeProperties(other)
        # merging meta data may raise an exception before knowing anything about the contained nuclides
        # if it raises an exception, nothing has been modified in two objects
        isotxsMeta, pmatrxMeta, gamisoMeta = self._mergeMetadata(other)
        self._mergeNuclides(other)
        # only vampire the __dict__ if successful
        other.__dict__ = {}
        # only reassign metadata if successful
        self.isotxsMetadata = isotxsMeta
        self.pmatrxMetadata = pmatrxMeta
        self.gamisoMetadata = gamisoMeta

    def _mergeProperties(self, other):
        properties.unlockImmutableProperties(other)
        try:
            self.neutronDoseConversionFactors = other.neutronDoseConversionFactors
            self._mergeNeutronEnergies(other)
            self.gammaEnergyUpperBounds = other.gammaEnergyUpperBounds
            self.gammaDoseConversionFactors = other.gammaDoseConversionFactors
        finally:
            properties.lockImmutableProperties(other)

    def _mergeMetadata(self, other):
        isotxsMeta = self.isotxsMetadata.merge(
            other.isotxsMetadata, self, other, "ISOTXS", exceptions.IsotxsError
        )
        pmatrxMeta = self.pmatrxMetadata.merge(
            other.pmatrxMetadata, self, other, "PMATRX", exceptions.PmatrxError
        )
        gamisoMeta = self.gamisoMetadata.merge(
            other.gamisoMetadata, self, other, "GAMISO", exceptions.GamisoError
        )
        return isotxsMeta, pmatrxMeta, gamisoMeta

    def _mergeNuclides(self, other):
        # these must be different
        for nuclideKey, nuclide in other.items():
            if nuclideKey in self:
                self[nuclideKey].merge(nuclide)
            else:
                self[nuclideKey] = nuclide

    def resetScatterWeights(self):
        self._scatterWeights = {}

    def getScatterWeights(self, scatterMatrixKey="elasticScatter"):
        """
        Build or retrieve pre-built scatter weight data

        This acts like a cache for _buildScatterWeights

        See Also
        --------
        _buildScatterWeights
        """

        if not self._scatterWeights.get(scatterMatrixKey):
            self._scatterWeights[scatterMatrixKey] = self._buildScatterWeights(
                scatterMatrixKey
            )

        return self._scatterWeights[scatterMatrixKey]

    def _buildScatterWeights(self, scatterMatrixKey):
        r"""
        Build a scatter-weight lookup table for the scatter matrix.

        Scatter "weights" are needed for sensitivity studies when deriviatives wrt the
        scatter XS are required. They are defined like:

        .. math::
            w_{g^{\prime} \leftarrow g} = \frac{\sigma_{s,g^{\prime} \leftarrow g}}
            {\sum_{g^{\prime\prime}=1}^G \sigma_{s, g^{\prime\prime} \leftarrow g}}

        Returns
        -------
        scatterWeights : dict
            (xsID, fromGroup) : weight column (sparse Gx1).

        See Also
        --------
        terrapower.physics.neutronics.uq.sensitivities.MeshMatrix.derivativeM

        """
        runLog.info(
            "Building {0} weights on cross section library".format(scatterMatrixKey)
        )
        scatterWeights = {}
        for nucName, nuc in self.items():
            nucScatterWeights = nuc.buildNormalizedScatterColumns(scatterMatrixKey)
            for fromG, scatterColumn in nucScatterWeights.items():
                scatterWeights[nucName, fromG] = scatterColumn
        return scatterWeights

    def plotNucXs(
        self, nucNames, xsNames, fName=None, label=None, noShow=False, title=None
    ):
        """
        generates a XS plot for a nuclide on the ISOTXS library


        nucName : str or list
            The nuclides to plot
        xsName : str or list
            the XS to plot e.g. n,g, n,f, nalph, etc. see xsCollections for actual names.
        fName : str, optional
            if fName is given, the file will be written rather than plotting to screen
        label : str, optional
            is an optional label for image legends, useful in ipython sessions.
        noShow : bool, optional
            Won't finalize plot. Useful for using this to make custom plots.

        Examples
        --------
        >>> l = ISOTXS()
        >>> l.plotNucXs('U238NA','fission')

        Plot n,g for all xenon and krypton isotopes
        >>> f = lambda name: 'XE' in name or 'KR' in name
        >>> l.plotNucXs(sorted(filter(f,l.nuclides.keys())),itertools.repeat('nGamma'))

        See Also
        --------
        armi.nucDirectory.nuclide.plotScatterMatrix

        """

        # convert all input to lists
        if isinstance(nucNames, str):
            nucNames = [nucNames]
        if isinstance(xsNames, str):
            xsNames = [xsNames]

        for nucName, xsName in zip(nucNames, xsNames):
            nuc = self[nucName]
            thisLabel = label or "{0} {1}".format(nucName, xsName)
            x = self.neutronEnergyUpperBounds / 1e6
            y = nuc.micros[xsName]
            pyplot.plot(x, y, "-", label=thisLabel, drawstyle="steps-post")

        ax = pyplot.gca()
        ax.set_xscale("log")
        ax.set_yscale("log")
        pyplot.grid(color="0.70")
        pyplot.title(title or " microscopic XS from {0}".format(self))
        pyplot.xlabel("Energy (MeV)")
        pyplot.ylabel("microscopic XS (barns)")
        pyplot.legend()
        if fName:
            pyplot.savefig(fName)
        elif not noShow:
            pyplot.show()

    def purgeFissionProducts(self, r):
        """
        Purge the fission products based on the active nuclides within the reactor.

        Parameters
        ----------
        r : py:class:`armi.reactors.reactor.Reactor`
            a reactor, or None

        .. warning:: Sometimes worker nodes do not have a reactor, fission products will not be purged.

        """
        runLog.info("Purging detailed fission products from {}".format(self))
        modeledNucs = r.blueprints.allNuclidesInProblem
        for key, nuc in list(self.items()):
            if nuc.name not in modeledNucs:
                del self[key]


class CompxsLibrary(_XSLibrary):
    """
    Library object used in reading/writing COMPXS files.

    Contains macroscopic cross sections for homogenized regions.

    See Also
    --------
    :py:class:`IsotxsLibrary`
    :py:func:`armi.nuclearDataIO.compxs.readBinary`

    Examples
    --------
    >>> lib = compxs.readBinary('COMPXS')
    >>> lib.regions
    """

    def __init__(self):
        _XSLibrary.__init__(self)
        self._regions = {}
        self.compxsMetadata = RegionXSMetadata()

    def __setitem__(self, key, value):
        _XSLibrary.__setitem__(self, key, value)
        self._regions[key] = value

    def __getitem__(self, key):
        return self._regions[key]

    def __delitem__(self, key):
        _XSLibrary.__delitem__(self, key)
        del self._regions[key]

    @property
    def regions(self):
        return [self[name] for name in self._orderedNuclideLabels]

    @property
    def regionLabels(self):
        return list(self._orderedNuclideLabels)

    def merge(self, other):
        """Merge two ``COMPXS`` libraries."""
        self._mergeProperties(other)
        self.compxsMetadata = self.compxsMetadata.merge(
            other.compxsMetadata, self, other, "COMPXS", CompxsError
        )
        self._appendRegions(other)

    def _mergeProperties(self, other):
        properties.unlockImmutableProperties(other)
        try:
            self._mergeNeutronEnergies(other)
        finally:
            properties.lockImmutableProperties(other)

    def _appendRegions(self, other):
        offset = len(self.regions)
        for region in other.regions:
            newNumber = region.regionNumber + offset
            self[newNumber] = region
        self.compxsMetadata["numComps"] = len(self.regions)

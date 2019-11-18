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
Some original nuclide directory code.

Notes
-----
This may be deprecated. Consider using the appropriate instance methods available through the
:py:class:`armi.nucDirectory.nuclideBases.INuclide` objects and/or the
:py:mod:`armi.nucDirectory.nuclideBases` module.
"""
import re

from armi import runLog
from armi.nucDirectory import elements, nuclideBases

nuclidePattern = re.compile(r"([A-Za-z]+)-?(\d{0,3})(\d*)(\S*)")
zaPat = re.compile(r"([A-Za-z]+)-?([0-9]+)")

# Partially from table 2.2 in Was
# See also: Table 2.4 in Primary Radiation Damage in Materials
# https://www.oecd-nea.org/science/docs/2015/nsc-doc2015-9.pdf
eDisplacement = {
    "H": 10.0,
    "C": 31.0,
    "N": 30.0,
    "NA": 25.0,
    "SI": 25.0,
    "V": 40.0,
    "CR": 40.0,
    "MN": 40.0,
    "NI": 40.0,
    "MO": 60.0,
    "FE": 40.0,
    "W": 90.0,
    "TI": 30.0,
    "NB": 60.0,
    "ZR": 40.0,
    "CU": 30.0,
    "CO": 40.0,
    "AL": 25.0,
    "PB": 25.0,
    "TA": 90.0,
}


def getNuclideFromName(name):
    actualName = name
    if "-" in name:
        actualName = name.replace("-", "")
    if "_" in name:
        actualName = name.replace("_", "")

    return nuclideBases.byName[actualName]


def getNuclidesFromInputName(name):
    """Convert nuclide specifier strings to isotopically-expanded nuclide bases"""
    name = name.upper()

    if name in elements.bySymbol:
        element = elements.bySymbol[name]
        if element.isNaturallyOccurring():
            # For things like Aluminum, just give natural isotopics.
            # This is likely what the user wants.
            return [
                nuc for nuc in element.nuclideBases if nuc.a > 0 and nuc.abundance > 0
            ]
        else:
            # For things like Pu: this is unusual, users should typically provide specific isotopes as input
            # Otherwise they get like 25 nuclides, most of which are never useful to track.
            raise NotImplementedError(
                "Expanding non-natural elements to all known nuclides is probably "
                "not what you want to do. Please specify isotopes of {} individually "
                "in the input file.".format(name)
            )
    else:
        raise ValueError(
            "Unrecognized nuclide/isotope/element in input: {}".format(name)
        )


def getNaturalIsotopics(elementSymbol=None, z=None):
    r"""
    determines the atom fractions of all natural isotopes

    Parameters
    ----------
    elementSymbol : str, optional
        The element symbol, e.g. Zr, U
    z : int, optional
        The atomic number of the element

    Returns
    -------
    abundances : list
        A list of (A,fraction) tuples where A is the mass number of the isotopes
    """
    element = None
    if z:
        element = elements.byZ[z]
    else:
        element = elements.bySymbol[elementSymbol]
    return [(nn.a, nn.abundance) for nn in element.getNaturalIsotopics()]


def getNaturalMassIsotopics(elementSymbol=None, z=None):
    r"""return mass fractions of all natural isotopes.
    To convert number fractions to mass fractions, we multiply by A
    """
    numIso = getNaturalIsotopics(elementSymbol, z)
    terms = []
    for a, frac in numIso:
        terms.append(a * frac)
    s = sum(terms)

    massIso = []
    for i, (a, frac) in enumerate(numIso):
        massIso.append((a, terms[i] / s))

    return massIso


def getMc2Label(name):
    r"""
    Return a MC2 prefix label without a xstype suffix

    MC**2 has labels and library names. The labels are like
    U235IA, ZIRCFB, etc. and the library names are references
    to specific data sets on the MC**2 libraries (e.g. U-2355, etc.)

    This method returns the labels without the xstype suffixes (IA, FB).
    Rather than maintaining a lookup table, this simply converts
    the ARMI nuclide names to MC**2 names.

    Parameters
    ----------
    name : str
        ARMI nuclide name of the nuclide

    Returns
    -------
    mc2LibLabel : str
        The MC**2 prefix for this nuclide.

    Examples
    --------
    >>> nucDir.getMc2Label('U235')
    'U235'
    >> nucDir.getMc2Label('FE')
    'FE'
    >>> nucDir.getMc2Label('IRON')
    'FE'
    >>> nucDir.getMc2Label('AM242')
    A242

    """
    # First translate to the proper nuclide. CARB->C
    nuc = getNuclide(name)
    return nuc.label


def getMc2LibName(name):
    r"""
    returns a MC2 library name given an ARMI nuclide name

    These are all 6 characters 'U-2355', 'ZR   S', etc.

    Parameters
    ----------
    name : str
        ARMI nuclide name of the nuclide

    Returns
    -------
    mc2LibLabel : str
        The 6-character MC**2 library ID for this nuclide

    See Also
    --------
    readMc2Nuclides : reads a data file containing all the mc2 labels
        and chooses the proper library extension for each.

    """
    nuc = getNuclide(name)  # converts ZIRC to ZR, etc.
    return nuc.mc2id


def getRebusLabel(name):
    r"""
    Return a REBUS label for the rebus input file.

    This should have no intermediate spaces and should be 5 characters long
    Examples: "U235 ", "B10  ", etc.

    Technically, this should be in the rebusInterface. No need to
    put specifics in this general module.

    Parameters
    ----------
    name : str
        ARMI nuclide name like U235, B10, ZR, CU, etc.
    """
    return "{0:5s}".format(name[:5])


def getMc2LabelFromRebusLabel(rebusLabel):
    r"""
    """
    return getMc2Label(rebusLabel)


def getRebusLabelFromMc2Label(mc2Label):
    r"""
    """
    return getRebusNameFromMC2(mc2Label)


def getElementName(z=None, symbol=None):
    r"""
    Returns element name

    Parameters
    ----------
    z : int
        Atomic number
    symbol : str
        Element abbreviation e.g. 'Zr'

    Examples
    --------
    >>> nucDir.getElementName(10)
    'Neon'
    >>> nucDir.getElementName(symbol='Zr')
    'Neon'

    """
    element = None
    if z:
        element = elements.byZ[z]
    else:
        element = elements.byName[symbol.upper()]
    return element.name


def getElementSymbol(z=None, name=None):
    r"""
    Returns element abbreviation given atomic number Z

    Parameters
    ----------
    z : int
        Atomic number
    name : str
        Element name E.g. Zirconium

    Examples
    --------
    >>> nucDir.getElementSymbol(10)
    'Ne'
    >>> nucDir.getElementSymbol(name='Neon')
    'Ne'

    """
    element = None
    if z:
        element = elements.byZ[z]
    else:
        element = elements.byName[name.lower()]
    return element.symbol


def getNuclide(nucName):
    r"""
    Looks up the ARMI nuclide object that has this name

    Parameters
    ----------
    nucName : str
        A nuclide name like U-235 or AM241, AM242M, AM242M

    Returns
    -------
    nuc : Nuclide
        An armi nuclide object.

    """
    nuc = nuclideBases.byName.get(nucName, None)
    if nucName and not nuc:
        nuc = getNuclideFromName(nucName)
    if not nuc:
        raise KeyError("Nuclide name {} is invalid.".format(nucName))
    return nuc


def getNuclides(nucName=None, elementSymbol=None):
    r"""
    returns a list of nuclide names in a particular nuclide or element

    If no arguments, returns all nuclideBases in the directory

    Used to convert things to DB name, to adjustNuclides, etc.

    Parameters
    ----------
    nucName : str
        ARMI nuclide label
    elementSymbol : str
        Element symbol e.g. 'Zr'
    """
    if nucName:
        # just spit back the nuclide if it's in here. Useful when iterating over the result.
        nucList = [getNuclide(nucName)]
    elif elementSymbol:
        nucList = elements.bySymbol[elementSymbol].nuclideBases
    else:
        # all nuclideBases, including shortcut nuclideBases ('CARB')
        nucList = [nuc for nuc in nuclideBases.instances if nuc.mc2id is not None]

    return nucList


def getNuclideNames(nucName=None, elementSymbol=None):
    r"""
    returns a list of nuclide names in a particular nuclide or element

    If no arguments, returns all nuclideBases in the directory.

    .. warning:: You will get both isotopes and NaturalNuclideBases for each element.

    Parameters
    ----------
    nucName : str
        ARMI nuclide label
    elementSymbol : str
        Element symbol e.g. 'Zr'
    """
    nucList = getNuclides(nucName, elementSymbol)
    return [nn.name for nn in nucList]


def getAtomicWeight(lab=None, z=None, a=None):
    r"""
    returns atomic weight in g/mole

    Parameters
    ----------
    lab : str, optional
        nuclide label, like U235
    z : int, optional
        atomic number
    a : int, optional
        mass number

    Returns
    -------
    aMass : float
        Atomic weight in grams /mole from NIST, or just mass number if not in library (U239 gives 239)

    Examples
    --------

    >>> from armi.nucDirectory import nucDir
    >>> nucDir.getAtomicWeight('U235')
    235.0439299

    >>> nucDir.getAtomicWeight('U239')
    239

    >>> nucDir.getAtomicWeight('U238')
    238.0507882

    >>> nucDir.getAtomicWeight(z=94,a=239)
    239.0521634

    """
    if lab:
        nuclide = None
        if lab in nuclideBases.byLabel:
            nuclide = nuclideBases.byLabel[lab]
        elif lab in nuclideBases.byMccId:
            nuclide = nuclideBases.byMccId[lab]
        if "DUMP1" in lab:
            return 10.0  # small dump.
        elif "DUMP2" in lab:
            return 240.0  # large dump.
        elif "FP35" in lab:
            return 233.2730
        elif "FP38" in lab:
            return 235.78
        elif "FP39" in lab:
            return 236.898
        elif "FP40" in lab:
            return 237.7
        elif "FP41" in lab:
            return 238.812
        elif "MELT" in lab:
            # arbitrary melt refined.
            return 238
        else:
            nuclide = getNuclideFromName(lab)
        return nuclide.weight
    elif z == 0 and a == 0:
        # dummy nuclide
        return 0.0
    if a == 0 and z:
        # natural abundance sent. Figure it out.
        element = elements.byZ[z]
        return element.standardWeight
    else:
        nuclide = nuclideBases.single(lambda nn: nn.a == a and nn.z == z)
        return nuclide.weight


def getRebusNameFromMC2(mc2LibLabel=None, mc2Label=None):
    r"""
    maps an MC2 label to a rebus label

    Parameters
    ----------
    mc2LibLabel : str
        THe library ID on the MC**2 binary file (e.g. U-235S)
    mc2Label : str
        The mc**2 prefix to look up (e.g. U235)
    """
    name = getNameFromMC2(mc2LibLabel, mc2Label)
    return getRebusLabel(name)

    runLog.warning("MC2 label {0}/{1} had no Rebus Name".format(mc2LibLabel, mc2Label))


def getNameFromMC2(mc2LibLabel=None, mc2Label=None):
    r"""
    maps an MC2 label to an ARMI label

    Tries to maintain some backwards compatibility with old ISOTXS libs
    with B-10AA, CARBAA, etc.

    Parameters
    ----------
    mc2LibLabel : str
        THe library ID on the MC**2 binary file (e.g. U-235S)
    mc2Label : str
        The mc**2 prefix to look up (e.g. U235)
    """
    nuclide = None
    if mc2LibLabel:
        nuclide = nuclideBases.byMccId[mc2LibLabel]
    else:
        nuclide = nuclideBases.byLabel[mc2Label]
    return nuclide.name
    # TODO: Not sure if this is the desired behaviour.
    # if not a warning, this fails on checking the LFP components to see if they're already
    # in the problem.
    runLog.warning(
        "Nuclide with mc2LibName/mc2Label {}/{} had no corresponding ARMI nuclide Name"
        "".format(mc2LibLabel, mc2Label)
    )
    return None


def getStructuralElements():
    r""" return list of element symbol in structure """
    return ["MN", "W", "HE", "C", "CR", "FE", "MO", "NI", "SI", "V"]


def isHeavyMetal(name):
    try:
        return getNuclide(name).isHeavyMetal()
    except AttributeError:
        AttributeError(
            "The nuclide {0} is not found in the nuclide directory".format(name)
        )


def isFissile(name):
    try:
        return getNuclide(name).isFissile()
    except AttributeError:
        AttributeError(
            "The nuclide {0} is not found in the nuclide directory".format(name)
        )


def getThresholdDisplacementEnergy(nuc):
    r"""
    return the Lindhard cutoff; the energy required to displace an atom

    From SPECTER.pdf Table II
    Greenwood, "SPECTER: Neutron Damage Calculations for Materials Irradiations",
    ANL.FPP/TM-197, Argonne National Lab., (1985).

    Parameters
    ----------
    nuc : str
        nuclide name

    Returns
    -------
    Ed : float
        The cutoff energy in eV
    """

    nuc = getNuclide(nuc)
    el = getElementSymbol(nuc.z)
    try:
        ed = eDisplacement[el]
    except KeyError:
        print(
            "The element {0} of nuclide {1} does not have a displacement energy in the library. Please add one."
            "".format(el, nuc)
        )
        raise
    return ed

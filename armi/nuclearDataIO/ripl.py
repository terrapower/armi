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
Read data from the Reference Input Parameter Library (RIPL-3)

https://www-nds.iaea.org/RIPL-3/
"""
import math
import os
import glob

import six

from armi.utils.textProcessors import SequentialStringIOReader, SequentialReader
from armi.nucDirectory import elements
from armi import runLog
from armi.utils import units
from armi.settings.caseSettings import Settings

DECAY_CONSTANTS = {}
MINIMUM_HALFLIFE = 1.0e-7
STABLE_FLAG = -1
UNKNOWN_HALFLIFE = -2
EXIT_DATA_FILE = -3


def getNuclideDecayConstants(fileName):
    """
    Read the halflifes and makes decay constants for the nuclides in this file.

    Returns
    -------
    nuclideDecayConstants : dict
        decay constants (1/s) indexed to nuclideBases
    """
    from armi.nucDirectory import nuclideBases

    if isinstance(fileName, six.StringIO):
        readerClass = SequentialStringIOReader
    else:
        readerClass = SequentialReader

    with readerClass(fileName) as reader:
        nuclideDecayConstants = {}
        while reader.searchForPattern(r"\d+[A-Z]{1,1}[a-z]{0,1}\s+\d+\s+\d+\s+\d+"):
            _, a, z, nol, _Nog, _Nmax, _Nc, _Sn, _Sp = reader.line.split()

            level = 0
            numLevels = int(nol)
            m = 0
            while (
                reader.searchForPatternOnNextLine(r"^\s*\d+\s+") and level < numLevels
            ):
                try:
                    level = float(reader.line[:3])
                    halflife = float(reader.line[24:34])
                    numDecays = int(reader.line[65:66])
                except ValueError:
                    if level == 1:
                        # RIPL files have empty halflifes for isotopes with
                        # exceptionally long halflifes like XE136 and EU151
                        halflife = STABLE_FLAG
                    else:
                        halflife = UNKNOWN_HALFLIFE

                if halflife == STABLE_FLAG:
                    aaazzzs = "{}{}{}".format(a, z.zfill(3), m)
                    try:
                        nb = nuclideBases.byAAAZZZSId[aaazzzs]
                        nuclideDecayConstants[nb] = 0
                        m += 1
                    except KeyError:
                        level += numLevels + 1

                elif (
                    MINIMUM_HALFLIFE < halflife and numDecays > 0
                ):  # radioactive isotope
                    aaazzzs = "{}{}{}".format(a, z.zfill(3), m)
                    if m <= 1:
                        nb = nuclideBases.byAAAZZZSId.get(aaazzzs, False)
                        if not nb:
                            nb = nuclideBases.NuclideBase(
                                elements.byZ[int(z)], int(a), float(a), 0, int(m), None
                            )

                        nuclideDecayConstants[nb] = math.log(2.0) / halflife
                        m += 1

                    else:
                        level += numLevels + 1

                elif numDecays == 0 or halflife == UNKNOWN_HALFLIFE:
                    # skip to next level
                    pass

                else:
                    level += numLevels + 1

                reader.consumeLine()

        return nuclideDecayConstants


def readFRDMMassFile(fname):
    """
    Read file from RIPL containing experimental mass excess evaluations.

    This file contains experimental mass excesses as well as theoretical masses from
    models. This class for the time being only reads the experimental values and skips
    all others.

    The values of interest are defined in the README as::

        Z    : charge number
        A    : mass number
        s    : element symbol
        fl   : flag corresponding to 0 if no experimental data available
                                     1 for a mass excess recommended by Audi et al. (2007)
                                     2 for a measured mass from Audi et al. (2007)
        Mexp : experimental or recommended atomic mass excess in MeV of Audi et al. (2007)
        Err  : error on the experimental or recommended atomic mass excess in MeV of Audi et al. (2007)
        Mth  : calculated FRDM atomic mass excess in MeV
        Emic : calculated FRDM microscopic energy in MeV
        beta2: calculated quadrupole deformation of the nuclear ground-state
        beta3: calculated octupole deformation of the nuclear ground-state
        beta4: calculated hexadecapole deformation of the nuclear ground-state
        beta6: calculated hexacontatetrapole deformation of the nuclear ground-state


    The format is ``(2i4,1x,a2,1x,i1,4f10.3,4f8.3)``.
    """
    if isinstance(fname, six.StringIO):
        readerClass = SequentialStringIOReader
    else:
        readerClass = SequentialReader

    with readerClass(fname) as reader:
        while reader.searchForPattern(
            r"^\s+(\d+)\s+(\d+)\s+(\S+)\s+(\d)\s+([-]?\d+\.\d+)\s+([-]?\d+\.\d+)"
        ):
            z, a, element, flag, massExcess, err = reader.match.groups()
            if flag == "2":
                # massExcess in MeV / (MeV/amu) = mass in amu
                mass = float(massExcess) / units.ATOMIC_MASS_CONSTANT_MEV
                a = int(a)
                yield int(z), a, element, a + float(mass), float(err)
            reader.consumeLine()


def readAbundanceFile(stream):
    """Read RIPL natural abundance subfile."""
    for line in stream:
        if line.startswith("#"):
            continue
        z, a, sym, percent, err = line.split()
        yield int(z), int(a), sym.upper(), float(percent), float(err)


def discoverRiplDecayFiles(directory):
    """
    Discover the RIPL decay/level files in the specified directory.

    RIPL decay/level files are like z001.dat where the number represents
    the atomic number of the nuclides within.

    Parameters
    ----------
    directory : str
        file path

    Returns
    -------
    riplDecayFiles : list
        file names of the RIPL decay files
    """
    riplDecayFiles = []
    for fileName in glob.glob(os.path.join(directory, "z???.dat")):
        riplDecayFiles.append(os.path.join(directory, fileName))

    return riplDecayFiles


def makeDecayConstantTable(directory=None, cs=None):
    """
    Make decay constants of the nuclides from the RIPL files.

    Parameters
    ----------
    directory : str
        file path to read
    cs : dict
        case settings

    Returns
    -------
    nuclideDecayConstants : dict
        decay constants indexed to nuclideBases
    """

    if directory is None:
        if cs is None:
            cs = Settings()
        directory = cs["nuclideHalflifeLibraryPath"]

    DECAY_CONSTANTS.clear()
    for riplDecayFile in discoverRiplDecayFiles(directory):
        riplDecay = getNuclideDecayConstants(riplDecayFile)
        DECAY_CONSTANTS.update(riplDecay)

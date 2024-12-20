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

"""Read and/or write data files associated with nuclear data and reactor physics data."""
# ruff: noqa: F401

# export the cccc modules here to keep external clients happy,
# though prefer full imports in new code
from armi.nuclearDataIO.cccc import (
    compxs,
    dif3d,
    dlayxs,
    fixsrc,
    gamiso,
    geodst,
    isotxs,
    labels,
    nhflux,
    pmatrx,
    pwdint,
    rtflux,
    rzflux,
)
from armi.physics import neutronics


def getExpectedISOTXSFileName(cycle=None, node=None, suffix=None, xsID=None):
    """
    Return the ISOTXS file that matches either the current cycle or xsID with a suffix.

    See Also
    --------
    getExpectedCOMPXSFileName
    getExpectedGAMISOFileName
    getExpectedPMATRXFileName
    """
    if xsID is not None and cycle is not None:
        raise ValueError("Both `xsID` and `cycle` cannot be specified together.")

    if suffix is not None and cycle is not None:
        raise ValueError("Both `suffix` and ``cycle cannot be specified together.")

    if xsID is not None:
        neutronFileName = neutronics.ISOTXS[:3]
    else:
        neutronFileName = neutronics.ISOTXS
    return _findExpectedNeutronFileName(
        neutronFileName, _getNeutronKeywords(cycle, node, suffix, xsID)
    )


def getExpectedCOMPXSFileName(cycle=None, node=None):
    """
    Return the COMPXS file that matches either the current cycle.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedGAMISOFileName
    getExpectedPMATRXFileName
    """
    return _findExpectedNeutronFileName(
        neutronics.COMPXS, _getNeutronKeywords(cycle, node, suffix=None, xsID=None)
    )


def _findExpectedNeutronFileName(fileType, fileNameKeywords):
    return fileType + "".join(fileNameKeywords)


def _getNeutronKeywords(cycle, node, suffix, xsID):
    if cycle is not None and xsID is not None:
        raise ValueError("Keywords are over-specified. Choose `cycle` or `xsID` only")

    # If neither cycle or xsID are provided there are no additional keywords to add
    # to the file name
    if cycle is None and xsID is None:
        keywords = []
    else:
        # example: ISOTXS-c0
        if cycle is not None:
            keywords = [f"-c{cycle}n{node}"] if node is not None else ["-c", str(cycle)]
        # example: ISOAA-test
        elif xsID is not None:
            keywords = [xsID]
            if suffix not in [None, ""]:
                keywords.append("-" + suffix)
    return keywords


def getExpectedGAMISOFileName(cycle=None, node=None, suffix=None, xsID=None):
    """
    Return the GAMISO file that matches either the ``cycle`` or ``xsID`` and ``suffix``.

    For example:
        If ``cycle`` is set to 0, then ``cycle0.gamiso`` will be returned.
        If ``xsID`` is set to ``AA`` with a ``suffix`` of ``test``, then
        ``AA-test.gamiso`` will be returned.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedCOMPXSFileName
    getExpectedPMATRXFileName
    """
    if any(i is not None for i in (cycle, suffix, xsID)):
        # file path extensions are lower case
        gamiso0 = neutronics.GAMISO_EXT
    else:
        # GAMISO as a file is upper case
        gamiso0 = neutronics.GAMISO

    return _findExpectedGammaFileName(
        gamiso0, _getGammaKeywords(cycle, node, suffix, xsID)
    )


def getExpectedPMATRXFileName(cycle=None, node=None, suffix=None, xsID=None):
    """
    Return the PMATRX file that matches either the ``cycle`` or ``xsID`` and ``suffix``.

    For example:
        If ``cycle`` is set to 0 d, then ``cycle0.pmatrx`` will be returned.
        If ``xsID`` is set to ``AA`` with a ``suffix`` of ``test``, then
        ``AA-test.pmatrx`` will be returned.

    See Also
    --------
    getExpectedISOTXSFileName
    getExpectedCOMPXSFileName
    getExpectedGAMISOFileName
    """
    if any(i is not None for i in (cycle, suffix, xsID)):
        # file path extensions are lower case
        pmatrx0 = neutronics.PMATRX_EXT
    else:
        # PMATRX as a file is upper case
        pmatrx0 = neutronics.PMATRX

    return _findExpectedGammaFileName(
        pmatrx0, _getGammaKeywords(cycle, node, suffix, xsID)
    )


def _findExpectedGammaFileName(fileType, fileNameKeywords):
    return "".join(fileNameKeywords) + fileType


def _getGammaKeywords(cycle, node, suffix, xsID):
    if cycle is not None and xsID is not None:
        raise ValueError("Keywords are over-specified. Choose `cycle` or `xsID` only")

    # If neither cycle or xsID are provided there are no additional keywords to add
    # to the file name
    if cycle is None and xsID is None:
        keywords = []
    else:
        # example: cycle0.gamiso
        if cycle is not None:
            keywords = (
                [f"cycle{cycle}node{node}"] if node is not None else [f"cycle{cycle}"]
            )

        elif xsID is not None:
            keywords = [xsID]
            if suffix not in [None, ""]:
                if not suffix.startswith("-"):
                    suffix = "-" + suffix
                keywords.append(suffix)
        else:
            raise ValueError("The cycle or XS ID must be specified.")
        keywords.append(".")
    return keywords

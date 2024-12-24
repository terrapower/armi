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
Assists in reconstruction/rewriting nuclear data files. 

One might
refer to the information stored in these files as the scaffolding or blueprints.
Some of it can/could be derived based on data within the overall file; however, not all of it could be
and it is always necessary to retain this type of data while reading the file.
"""

from armi import runLog
from armi.utils import properties

COMPXS_POWER_CONVERSION_FACTORS = ["fissionWattSeconds", "captureWattSeconds"]
REGIONXS_POWER_CONVERT_DIRECTIONAL_DIFF = [
    "powerConvMult",
    "d1Multiplier",
    "d1Additive",
    "d1Multiplier",
    "d2Additive",
    "d3Multiplier",
    "d3Additive",
]


class _Metadata:
    """Simple dictionary wrapper, that returns :code:`None` if the key does not exist.

    Notes
    -----
    Cannot use a dictionary directly because it is difficult to subclass and broadcast them with MPI.
    """

    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        return self._data.get(key, None)

    def __setitem__(self, key, value):
        self._data[key] = value

    def __iter__(self):
        return iter(self._data)

    def items(self):
        """Returns items similar to the dict implementation."""
        return self._data.items()

    def __len__(self):
        return len(self._data)

    def keys(self):
        """Returns keys similar to the dict implementation."""
        return self._data.keys()

    def values(self):
        return self._data.values()

    def update(self, other):
        """Updates the underlying dictionary, similar to the dict implementation."""
        self._data.update(other._data)

    def merge(self, other, selfContainer, otherContainer, fileType, exceptionClass):
        """
        Merge the contents of two metadata instances.

        Parameters
        ----------
        other: Similar Metadata class as self
            Metadata to be compared against
        selfContainer: class
        otherContainer: class
            Objects that hold the two metadata instances
        fileType: str
            File type that created this metadata. Examples: ``'ISOTXS', 'GAMISO', 'COMPXS'```
        exceptionClass: Exception
            Type of exception to raise in the event of dissimilar metadata values

        Returns
        -------
        mergedData: Metadata
            Returns a metadata instance of similar type as ``self`` and ``other``
            containing the correctly merged data of the two
        """
        mergedData = self.__class__()
        if not (any(self.keys()) and any(other.keys())):
            mergedData.update(self)
            mergedData.update(other)
            return mergedData
        self._mergeLibrarySpecificData(other, selfContainer, otherContainer, mergedData)
        skippedKeys = self._getSkippedKeys(
            other, selfContainer, otherContainer, mergedData
        )
        for key in set(list(self.keys()) + list(other.keys())) - skippedKeys:
            selfVal = self[key]
            otherVal = other[key]
            mergedVal = None
            if not properties.numpyHackForEqual(selfVal, otherVal):
                raise exceptionClass(
                    "{libType} {key} metadata differs between {lib1} and {lib2}; Cannot Merge\n"
                    "{key} has values of {val1} and {val2}".format(
                        libType=fileType,
                        lib1=selfContainer,
                        lib2=otherContainer,
                        key=key,
                        val1=selfVal,
                        val2=otherVal,
                    )
                )
            else:
                mergedVal = selfVal
            mergedData[key] = mergedVal
        return mergedData

    def _getSkippedKeys(self, other, selfContainer, otherContainer, mergedData):
        return set()

    def _mergeLibrarySpecificData(
        self, other, selfContainer, otherContainer, mergedData
    ):
        pass

    def compare(self, other, selfContainer, otherContainer, tolerance=0.0):
        """
        Compare the metadata for two libraries.

        Parameters
        ----------
        other: Similar Metadata class as self
            Metadata to be compared against
        selfContainer: class
        otherContainer: class
            Objects that hold the two metadata instances
        tolerance: float
            Acceptable difference between two metadata values

        Returns
        -------
        equal: bool
            If the metadata are equal or not.
        """
        equal = True
        for propName in set(list(self.keys()) + list(other.keys())):
            selfVal = self[propName]
            otherVal = other[propName]
            if not properties.areEqual(selfVal, otherVal, tolerance):
                runLog.important(
                    "{} and {} {} have different {}:\n{}\n{}".format(
                        selfContainer,
                        otherContainer,
                        self.__class__.__name__,
                        propName,
                        selfVal,
                        otherVal,
                    )
                )
                equal = False
        return equal


class FileMetadata(_Metadata):
    """
    Metadata description for a file.

    Attributes
    ----------
    fileNames : list
        string list of file names
    """

    def __init__(self):
        _Metadata.__init__(self)
        self.fileNames = []

    def update(self, other):
        """Update this metadata with metadata from another file."""
        _Metadata.update(self, other)
        self.fileNames += other.fileNames

    def _mergeLibrarySpecificData(
        self, other, selfContainer, otherContainer, mergedData
    ):
        mergedData.fileNames = self.fileNames + other.fileNames


class NuclideXSMetadata(FileMetadata):
    """Metadata for library files containing nuclide cross sections, e.g. ``ISOTXS``."""

    def _getSkippedKeys(self, other, selfContainer, otherContainer, mergedData):
        skippedKeys = set(["chi", "libraryLabel"])
        if self["chi"] is not None or other["chi"] is not None:
            runLog.warning(
                "File-wide chi is removed merging libraries {lib1} and {lib2}.\n"
                "This should not impact the calculation, as the file-wide chi is used as"
                " the nuclide-specific chi.\n The nuclides in {lib2} may be modified as well.".format(
                    lib1=selfContainer, lib2=otherContainer
                )
            )
            mergedData["fileWideChiFlag"] = 0
            skippedKeys.add("fileWideChiFlag")
            mergedData["chi"] = None
            for nuc in [nn for nn in selfContainer.nuclides + otherContainer.nuclides]:
                if nuc.isotxsMetadata["fisFlag"] > 0:
                    nuc.isotxsMetadata["chiFlag"] = 1
        return skippedKeys

    def _mergeLibrarySpecificData(
        self, other, selfContainer, otherContainer, mergedData
    ):
        FileMetadata._mergeLibrarySpecificData(
            self, other, selfContainer, otherContainer, mergedData
        )
        mergedData["libraryLabel"] = self["libraryLabel"] or other["libraryLabel"]


class RegionXSMetadata(FileMetadata):
    """Metadata for library files containing region cross sections, e.g. ``COMPXS``."""

    def _mergeLibrarySpecificData(
        self, other, selfContainer, otherContainer, mergedData
    ):
        FileMetadata._mergeLibrarySpecificData(
            self, other, selfContainer, otherContainer, mergedData
        )
        for datum in COMPXS_POWER_CONVERSION_FACTORS:
            mergedData[datum] = self[datum] + other[datum]
        mergedData["compFamiliesWithPrecursors"] = (
            self["compFamiliesWithPrecursors"] + other["compFamiliesWithPrecursors"]
        )
        mergedData["numFissComps"] = self["numFissComps"] + other["numFissComps"]

    def _getSkippedKeys(self, other, selfContainer, otherContainer, mergedData):
        return set(
            ["numComps", "compFamiliesWithPrecursors", "numFissComps"]
            + COMPXS_POWER_CONVERSION_FACTORS
        )


class NuclideMetadata(_Metadata):
    """Simple dictionary for providing metadata about how to read/write a nuclide to/from a file."""

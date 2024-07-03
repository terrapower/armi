# Copyright 2024 TerraPower, LLC
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
Tooling to help flatten jagged (non rectangular) data into rectangular arrays.

The goal here is to support jagged data for NumPy arrays to be written into the ARMI databases.
"""

from typing import List, Optional

import numpy as np

from armi import runLog


class JaggedArray:
    """
    Take a list of numpy arrays or lists and flatten them into a single 1D array.

    This implementation can preserve the structure of a multi-dimensional numpy array
    by storing the dimensions in self.shapes and then re-populating a numpy array of
    that shape from the flattened 1D array. However, it can only preserve one layer of
    jaggedness in a list of lists (or other iterables). For example, a list of tuples
    with varying lengths can be flattened and reconstituted exactly. But, if a list of
    lists of tuples is passed in, the tuples in that final layer of nesting will all be
    flattened to a single 1D numpy array after a round trip. No structure is retained
    from nested lists of jagged lists or tuples.
    """

    def __init__(self, jaggedData, paramName):
        """
        JaggedArray constructor.

        Parameters
        ----------
        jaggedData: list of np.ndarray
            A list of numpy arrays (or lists or tuples) to be flattened into a single array
        paramName: str
            The name of the parameter represented by this data
        """
        offset = 0
        flattenedArray = []
        offsets = []
        shapes = []
        for arr in jaggedData:
            offsets.append(offset)
            if isinstance(arr, np.ndarray):
                shapes.append(arr.shape)
                offset += arr.size
                flattenedArray.extend(arr.flatten())
            elif isinstance(arr, (int, float, list, tuple)):
                try:
                    numpyArray = np.array(arr)
                    shapes.append(numpyArray.shape)
                    offset += numpyArray.size
                    flattenedArray.extend(numpyArray.flatten())
                except:  # noqa: E722
                    # numpy might fail if it's jagged
                    flattenedList = self.flatten(arr)
                    shapes.append(
                        len(flattenedList),
                    )
                    offset += len(flattenedList)
                    flattenedArray.extend(flattenedList)
            elif arr is None:
                flattenedArray.append(None)
                offset += 1

        self.flattenedArray = np.array(flattenedArray)
        self.offsets = np.array(offsets)
        try:
            self.shapes = np.array(shapes)
        except ValueError as ee:
            runLog.error(
                "Error! It seems like ARMI may have tried to flatten a jagged array "
                "where the elements have different numbers of dimensions. `shapes` "
                "attribute of the JaggedArray for {} cannot be made into a numpy "
                "array; it might be jagged.".format(paramName)
            )
            raise ValueError(ee)
        self.nones = np.array(
            [i for i, val in enumerate(flattenedArray) if val is None]
        )
        self.dtype = self.flattenedArray.dtype
        self.paramName = paramName

    def __iter__(self):
        """Iterate over the unpacked list."""
        return iter(self.unpack())

    def __contains__(self, other):
        return other in self.flattenedArray

    @staticmethod
    def flatten(x):
        """
        Recursively flatten an iterable (list, tuple, or numpy.ndarray).

        x : list, tuple, np.ndarray
            An iterable. Can be a nested iterable in which the elements
            themselves are also iterable.
        """
        if isinstance(x, (list, tuple, np.ndarray)):
            if len(x) == 0:
                return []
            first, rest = x[0], x[1:]
            return JaggedArray.flatten(first) + JaggedArray.flatten(rest)
        else:
            return [x]

    @classmethod
    def fromH5(cls, data, offsets, shapes, nones, dtype, paramName):
        """
        Create a JaggedArray instance from an HDF5 dataset.

        The JaggedArray is stored in HDF5 as a flat 1D array with accompanying
        attributes of "offsets" and "shapes" to define how to reconstitute the
        original data.

        Parameters
        ----------
        data: np.ndarray
            A flattened 1D numpy array read in from an HDF5 file
        offsets: np.ndarray
            Offset indices for the zeroth element of each constituent array
        shapes: np.ndarray
            The shape of each constituent array
        nones: np.ndarray
            The location of Nones
        dtype: np.dtype
            The data type for the array
        paramName: str
            The name of the parameter represented by this data

        Returns
        -------
        obj: JaggedArray An instance of JaggedArray populated with the input data
        """
        obj = cls([], paramName)
        obj.flattenedArray = np.array(data)
        obj.offsets = np.array(offsets)
        obj.shapes = np.array(shapes)
        obj.nones = np.array(nones)
        obj.dtype = dtype
        obj.paramName = paramName
        return obj

    def tolist(self):
        """Alias for unpack() to make this class respond like a np.ndarray."""
        return self.unpack()

    def unpack(self):
        """
        Unpack a JaggedArray object into a list of arrays.

        Returns
        -------
        unpackedJaggedData: list of np.ndarray
            List of numpy arrays with varying dimensions (i.e., jagged arrays)
        """
        unpackedJaggedData: List[Optional[np.ndarray]] = []
        for offset, shape in zip(self.offsets, self.shapes):
            unpackedJaggedData.append(
                np.ndarray(shape, dtype=self.dtype, buffer=self.flattenedArray[offset:])
            )

        return self.replaceNonsenseWithNones(unpackedJaggedData)

    def replaceNonsenseWithNones(self, unpackedData):
        """Replace None markers in the unpacked array with an actual None."""
        unpackedObject = []
        for i, data in enumerate(unpackedData):
            if np.issubdtype(self.dtype, np.floating):
                isNone = np.isnan(data)
            elif np.issubdtype(self.dtype, np.integer):
                isNone = data == np.iinfo(self.dtype).min + 2
            elif np.issubdtype(self.dtype, np.str_):
                isNone = data == "<!None!>"
            elif np.issubdtype(self.dtype, np.object_):
                # object type means Nones are probably already present
                isNone = data == None  # noqa: E711
            else:
                raise TypeError(
                    "Unable to resolve values that should be None for `{}`. dtype = `{}`".format(
                        self.paramName, self.dtype
                    )
                )

            if data.ndim > 1 and isNone.all():
                replacedData = None
            else:
                replacedData = np.array(data, dtype=np.dtype("O"))
                replacedData[isNone] = None

            unpackedObject.append(replacedData)

        return unpackedObject

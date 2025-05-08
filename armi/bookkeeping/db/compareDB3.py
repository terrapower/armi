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
Use the generic database class to compare two ARMI databases.

This assumes some intimate knowledge about how the database is structured internally.
For instance, it knows that the database is composed of HDF5 data (the attrs of a
dataset are used, and h5py Groups are indexed), and it knows how special data is
structured within the HDF5 dataset and what the corresponding attributes are used for.
Some of this could be easily pulled up to the public interfaces of the Database class,
which may allow for cross-version database checking, but there is probably little value
in doing so if one is able to convert between versions.

Speaking of conversions, there are some common issues that may arise from comparing
against databases that were converted from an old version. The process of reading in the
old database values can sometimes lead to more parameters being written out to the new
database than were in the original database (set to the parameter's default value). That
means that one generally should not be worried about a converted database having more
parameters in it that the one produced directly may not, assuming that the extra
converted parameters are the default. Also, especially at the Component level, some of
the parameters are expected to be different. Specifically the following:

* temperatures: The old database format simply did not store these on the component
  level, so when converting a database, the components in a block will uniformly get
  whatever the Block temperature was.
* serial numbers: At all levels, we cannot really expect the serial numbers to line
  up from object to object. These are not really supposed to be the same.
* volume: Component volumes also are not stored on the database, and come from
  temperatures
* memory usage: Relatively self-evident. Resource usage will vary from run to run,
  even if the code hasn't changed.

"""
import collections
import os
import re
import traceback
from typing import Optional, Pattern, Sequence, Tuple

import h5py
import numpy as np

from armi import runLog
from armi.bookkeeping.db import database
from armi.bookkeeping.db.database import Database
from armi.bookkeeping.db.factory import databaseFactory
from armi.bookkeeping.db.permissions import Permissions
from armi.reactor.composites import ArmiObject
from armi.utils.tabulate import tabulate


class OutputWriter:
    """Basically a tee to writeln to runLog and the output file."""

    def __init__(self, fname):
        self.fname = fname
        self._stream = None

    def __enter__(self):
        self._stream = open(self.fname, "w")
        return self

    def __exit__(self, *args):
        self._stream.close()

    def writeln(self, msg: str) -> None:
        runLog.info(msg)
        self._stream.write(msg)
        self._stream.write("\n")


class DiffResults:
    """Utility class for storing differences between database data.

    This class is used to store the differences between reference data and other
    ("source") data. It is configured with a tolerance, below which differences are
    ignored. Differences that exceed the tolerance are stored in a collection of
    differences, organized by time step to be outputted later. It also keeps track of
    the number of issues that may have been encountered in attempting to compare two
    databases. For instance, missing datasets on one database or the other, or datasets
    with incompatible dimensions and the like.

    All differences are based on a weird type of relative difference, which uses the
    mean of the reference and source data elements as the normalization value:
    2*(C-E)/(C+E). This is somewhat strange, in that if the two are very different, the
    reported relative difference will be smaller than expected. It does have the useful
    property that if the reference value is zero and the source value is non-zero, the
    diff will not be infinite. We do not typically report these in any rigorous manner,
    so this should be fine, though we may wish to revisit this in the future.
    """

    def __init__(self, tolerance):
        self._columns = []
        self._structureDiffs = []
        self.tolerance = tolerance
        # diffs is a dictionary, keyed on strings describing the object to which the
        # diffs apply, and the different diff metrics that we use (e.g. mean(abs(diff)),
        # max(abs(diff))), with the values being a list of diffs by time step. If the
        # diff doesn't exceed the tolerance, a None is inserted instead.
        self.diffs = collections.defaultdict(self._getDefault)

    def addDiff(
        self, compType: str, paramName: str, absMean: float, mean: float, absMax: float
    ) -> None:
        """Add a collection of diffs to the diff dictionary if they exceed the tolerance."""
        absMean = absMean if absMean > self.tolerance else None
        self.diffs["{}/{} mean(abs(diff))".format(compType, paramName)].append(absMean)

        mean = mean if abs(mean) > self.tolerance else None
        self.diffs["{}/{} mean(diff)".format(compType, paramName)].append(mean)

        absMax = absMax if absMax > self.tolerance else None
        self.diffs["{}/{} max(abs(diff))".format(compType, paramName)].append(absMax)

    def addStructureDiffs(self, nDiffs: int) -> None:
        if not self._structureDiffs:
            self._structureDiffs = [0]

        self._structureDiffs[-1] += nDiffs

    def addTimeStep(self, tsName: str) -> None:
        self._structureDiffs.append(0)
        self._columns.append(tsName)

    def _getDefault(self) -> list:
        return [None] * (len(self._columns) - 1)

    def reportDiffs(self, stream: OutputWriter) -> None:
        """Print out a well-formatted table of the non-zero diffs."""
        # filter out empty rows
        diffsToPrint = {
            key: value
            for key, value in self.diffs.items()
            if not all(v is None for v in value)
        }
        stream.writeln(
            tabulate(
                [k.split() + val for k, val in sorted(diffsToPrint.items())],
                headers=self._columns,
            )
        )

    def nDiffs(self) -> int:
        """Return the number of differences that exceeded the tolerance."""
        return sum(
            1 for _, value in self.diffs.items() if any(v is not None for v in value)
        ) + sum(self._structureDiffs)


def compareDatabases(
    refFileName: str,
    srcFileName: str,
    exclusions: Optional[Sequence[str]] = None,
    tolerance: float = 0.0,
    timestepCompare: Optional[Sequence[Tuple[int, int]]] = None,
) -> Optional[DiffResults]:
    """High-level method to compare two ARMI H5 files, given file paths."""
    compiledExclusions = None
    if exclusions is not None:
        compiledExclusions = [re.compile(ex) for ex in exclusions]

    outputName = (
        os.path.basename(refFileName) + "_vs_" + os.path.basename(srcFileName) + ".txt"
    )

    diffResults = DiffResults(tolerance)
    with OutputWriter(outputName) as out:
        ref = databaseFactory(refFileName, Permissions.READ_ONLY_FME)
        src = databaseFactory(srcFileName, Permissions.READ_ONLY_FME)
        if not isinstance(ref, Database) or not isinstance(src, Database):
            raise TypeError(
                "This database comparer only knows how to deal with database version "
                "3; received {} and {}".format(type(ref), type(src))
            )

        with ref, src:
            if not timestepCompare:
                _, nDiff = _compareH5Groups(out, ref, src, "timesteps")

                if nDiff > 0:
                    runLog.warning(
                        "{} and {} have differing timestep groups, and are "
                        "probably not safe to compare. This is likely due to one of "
                        "the cases having failed to complete.".format(ref, src)
                    )
                    return None

            for refGroup, srcGroup in zip(
                ref.genTimeStepGroups(timeSteps=timestepCompare),
                src.genTimeStepGroups(timeSteps=timestepCompare),
            ):
                runLog.info(
                    f"Comparing ref time step {refGroup.name.split('/')[1]} to src time "
                    f"step {srcGroup.name.split('/')[1]}"
                )
                diffResults.addTimeStep(refGroup.name)
                _compareTimeStep(
                    out, refGroup, srcGroup, diffResults, exclusions=compiledExclusions
                )

        diffResults.reportDiffs(out)

    return diffResults


def _compareH5Groups(
    out: OutputWriter, ref: h5py.Group, src: h5py.Group, name: str
) -> Tuple[Sequence[str], int]:
    refGroups = set(ref.keys())
    srcGroups = set(src.keys())

    n = _compareSets(srcGroups, refGroups, out, name)

    return sorted(refGroups & srcGroups), n


def _compareTimeStep(
    out: OutputWriter,
    refGroup: h5py.Group,
    srcGroup: h5py.Group,
    diffResults: DiffResults,
    exclusions: Optional[Sequence[Pattern]] = None,
):
    groupNames, structDiffs = _compareH5Groups(
        out, refGroup, srcGroup, "composite objects/auxiliary data"
    )
    diffResults.addStructureDiffs(structDiffs)

    componentTypes = {gn for gn in groupNames if gn in ArmiObject.TYPES}
    auxData = set(groupNames) - componentTypes
    auxData.discard("layout")

    for componentType in componentTypes:
        refTypeGroup = refGroup[componentType]
        srcTypeGroup = srcGroup[componentType]

        _compareComponentData(
            out, refTypeGroup, srcTypeGroup, diffResults, exclusions=exclusions
        )

    for aux in auxData:
        _compareAuxData(out, refGroup[aux], srcGroup[aux], diffResults)


def _compareAuxData(
    out: OutputWriter,
    refGroup: h5py.Group,
    srcGroup: h5py.Group,
    diffResults: DiffResults,
):
    """
    Compare auxiliary datasets, which aren't stored as Parameters on the Composite model.

    Some parts of ARMI directly create HDF5 groups under the time step group to store
    arbitrary data. These still need to be compared. Missing datasets will be treated as
    structure differences and reported.
    """
    data = dict()

    def visitor(name, obj):
        if isinstance(obj, h5py.Dataset):
            data[name] = obj

    refGroup.visititems(visitor)
    refData = data

    data = dict()
    srcGroup.visititems(visitor)
    srcData = data

    n = _compareSets(
        set(srcData.keys()), set(refData.keys()), out, name="auxiliary dataset"
    )
    diffResults.addStructureDiffs(n)
    matchedSets = set(srcData.keys()) & set(refData.keys())
    for name in matchedSets:
        _diffSimpleData(refData[name], srcData[name], diffResults)


def _compareSets(
    src: set, ref: set, out: OutputWriter, name: Optional[str] = None
) -> int:
    nDiffs = 0
    printName = "" if name is None else name + " "
    if ref - src:
        nDiffs += len(ref - src)
        out.writeln("ref has {}not in src: {}".format(printName, list(ref - src)))

    if src - ref:
        nDiffs += len(src - ref)
        out.writeln("src has {}not in ref: {}".format(printName, list(src - ref)))

    return nDiffs


def _diffSpecialData(
    refData: h5py.Dataset,
    srcData: h5py.Dataset,
    out: OutputWriter,
    diffResults: DiffResults,
):
    """
    Compare specially-formatted datasets.

    This employs the pack/unpackSpecialData functions to reconstitute complicated
    datasets for comparison. These usually don't behave well as giant numpy arrays, so
    we go element-by-element to calculate the diffs, then concatenate them.
    """
    name = refData.name
    paramName = refData.name.split("/")[-1]
    compName = refData.name.split("/")[-2]

    nDiffs = _compareSets(
        set(srcData.attrs.keys()), set(refData.attrs.keys()), out, "formatting data"
    )
    keysMatch = nDiffs == 0
    diffResults.addStructureDiffs(nDiffs)

    if not keysMatch:
        diffResults.addDiff(name, name, np.inf, np.inf, np.inf)
        return

    if srcData.attrs.get("dict", False):
        # not bothering with dictionaries yet, though we will need to for things like
        # number densities
        return

    attrsMatch = True
    for k, srcAttr in srcData.attrs.items():
        refAttr = refData.attrs[k]

        if isinstance(srcAttr, np.ndarray) and isinstance(refAttr, np.ndarray):
            srcFlat = srcAttr.flatten()
            refFlat = refAttr.flatten()
            if len(srcFlat) != len(refFlat):
                same = False
            else:
                same = all(srcFlat == refFlat)
        else:
            same = srcAttr == refAttr

        if not same:
            attrsMatch = False
            out.writeln(
                "Special formatting parameters for {} do not match for {}. Src: {} "
                "Ref: {}".format(name, k, srcData.attrs[k], refData.attrs[k])
            )
            break

    if not attrsMatch:
        return

    try:
        src = database.unpackSpecialData(srcData[()], srcData.attrs, paramName)
        ref = database.unpackSpecialData(refData[()], refData.attrs, paramName)
    except Exception:
        runLog.error(
            f"Unable to unpack special data for paramName {paramName}. "
            f"{traceback.format_exc()}",
        )
        return

    diff = []
    for dSrc, dRef in zip(src.tolist(), ref.tolist()):
        if isinstance(dSrc, np.ndarray) and isinstance(dRef, np.ndarray):
            if dSrc.shape != dRef.shape:
                out.writeln("Shapes did not match for {}".format(refData))
                diffResults.addDiff(compName, paramName, np.inf, np.inf, np.inf)
                return

            # Make sure not to try to compare empty arrays. Numpy is mediocre at these;
            # they are super degenerate and cannot participate in concatenation.
            if 0 not in dSrc.shape:
                # Use the mean of the two to calc relative error. This is more robust to
                # changes that cause one of the values to be zero, while the other is
                # non-zero, leading to infinite relative error
                dMean = (dSrc + dRef) / 2
                diff.append((dSrc - dRef) / dMean)
            continue

        if (dSrc is None) ^ (dRef is None):
            out.writeln("Mismatched Nones for {} in {}".format(paramName, compName))
            diff.append([np.inf])
            continue

        if dSrc is None:
            diff.append([0.0])
            continue

        try:
            # Use mean to avoid some infinities; see above
            dMean = (dSrc + dRef) / 2
            diff.append([(dSrc - dRef) / dMean])
        except ZeroDivisionError:
            if dSrc == dRef:
                diff.append([0.0])
            else:
                diff.append([np.inf])

    if diff:
        try:
            diff = [np.array(d).flatten() for d in diff]
            diff = np.concatenate(diff)
        except ValueError as e:
            out.writeln(
                "Failed to concatenate diff data for {} in {}: {}".format(
                    paramName, compName, diff
                )
            )
            out.writeln("Because: {}".format(e))
            return
        absDiff = np.abs(diff)
        mean = np.nanmean(diff)
        absMax = np.nanmax(absDiff)
        absMean = np.nanmean(absDiff)

        diffResults.addDiff(compName, paramName, absMean, mean, absMax)


def _diffSimpleData(ref: h5py.Dataset, src: h5py.Dataset, diffResults: DiffResults):
    paramName = ref.name.split("/")[-1]
    compName = ref.name.split("/")[-2]

    try:
        # use mean to avoid some unnecessary infinities
        mean = (src[()] + ref[()]) / 2.0
        diff = (src[()] - ref[()]) / mean
    except TypeError:
        # Strings are persnickety
        if src.dtype.kind == ref.dtype.kind and src.dtype.kind in {"U", "S"}:
            return
        else:
            runLog.error("Failed to compare {} in {}".format(paramName, compName))
            runLog.error("source: {}".format(src))
            runLog.error("reference: {}".format(ref))
            diff = np.array([np.inf])
    except ValueError:
        runLog.error("Failed to compare {} in {}".format(paramName, compName))
        runLog.error("source: {}".format(src))
        runLog.error("reference: {}".format(ref))
        diff = np.array([np.inf])

    if 0 in diff.shape:
        # Empty list, no diff
        return

    absDiff = np.abs(diff)
    mean = np.nanmean(diff)
    absMax = np.nanmax(absDiff)
    absMean = np.nanmean(absDiff)

    diffResults.addDiff(compName, paramName, absMean, mean, absMax)


def _compareComponentData(
    out: OutputWriter,
    refGroup: h5py.Group,
    srcGroup: h5py.Group,
    diffResults: DiffResults,
    exclusions: Optional[Sequence[Pattern]] = None,
):
    exclusions = exclusions or []
    compName = refGroup.name
    paramNames, nDiff = _compareH5Groups(
        out, refGroup, srcGroup, "{} parameters".format(compName)
    )
    diffResults.addStructureDiffs(nDiff)

    for paramName in paramNames:
        fullName = "/".join((refGroup.name, paramName))
        if any(pattern.match(fullName) for pattern in exclusions):
            runLog.debug(
                "Skipping comparison of {} since it is being ignored.".format(fullName)
            )
            continue
        refDataset = refGroup[paramName]
        srcDataset = srcGroup[paramName]

        srcSpecial = srcDataset.attrs.get("specialFormatting", False)
        refSpecial = refDataset.attrs.get("specialFormatting", False)

        if srcSpecial ^ refSpecial:
            out.writeln(
                "Could not compare data for parameter {} because one uses special "
                "formatting, and the other does not. Ref: {} Src: {}".format(
                    paramName, refSpecial, srcSpecial
                )
            )
            diffResults.addDiff(refGroup.name, paramName, np.inf, np.inf, np.inf)
            continue

        if srcSpecial or refSpecial:
            _diffSpecialData(refDataset, srcDataset, out, diffResults)
        else:
            _diffSimpleData(refDataset, srcDataset, diffResults)

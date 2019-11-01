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
Use the generic API of the database class to compare two ARMI databases
"""
import time
import copy
import collections
import numbers
from typing import Optional, Sequence

import numpy

from six.moves import zip_longest

from armi import runLog
from armi.utils import iterables
from armi.utils import exceptions


class DMNames(object):
    """Common names for aspects of the data model in ARMI"""

    TIMESTEPS = "timesteps"
    REACTORS = "reactors"
    ASSEMBLIES = "assemblies"
    BLOCKS = "blocks"


class DatabaseComparer(object):
    """This class facilitates the comparison of two databases"""

    def __init__(
        self,
        ref,
        src,
        exclusion: Optional[Sequence[str]] = None,
        weights=None,
        tolerance=0.01,
        selection=None,
        timestepMatchup=None,
    ):

        self.src = src
        self.ref = ref

        self.differences = _DifferencesOutputer()
        # What key names to ignore in the evaluation of differences
        self.exclusion = exclusion or set()
        # DMNames.object : key, to weight by
        self.weights = weights or {DMNames.BLOCKS: "flux"}
        # [-4,-3,-2,-1], indices to select of the timesteps
        self.selection = selection or []
        # how small the percentage change can be to be ignored
        self.tolerance = tolerance
        # what timesteps in src to compare in ref {src : ref}
        self.timestepMatchup = timestepMatchup or {}

    def hasDifferences(self):
        return self.differences.hasDifferences()

    def output(self):
        """Format the resulting differences as best as possible for human comprehension"""
        output = [
            " - - - DATABASE COMPARISON RESULTS - - - ",
            "-----------------------------------------",
            "-----------------------------------------",
            ":REF:  {}".format(repr(self.ref)),
            ":SRC:  {}".format(repr(self.src)),
            "{}".format(time.asctime()),
            "{:<11} - {} %".format("Tolerance", self.tolerance),
        ]
        if self.exclusion:
            output.append("{:<11} - {}".format("Exclusion", self.exclusion))
        if self.weights:
            output.append("{:<11} - {}".format("Weights", self.weights))
        if self.selection:
            output.append("{:<11} - {}".format("Selection", self.selection))
        if any(k != v for k, v in self.timestepMatchup.items()):
            output.append("{:<11} - {}".format("TS Matchup", self.timestepMatchup))
        output.append("")

        output.extend(Comparisons.Errors.outputErrorKey())
        output.append("")
        output.extend(self.differences.output())

        return "\n".join(output)

    def write(self, fname=""):
        """Output the results of the database comparison to a file"""
        fname = fname or "{}_{}_dbcomparison.txt".format(
            self.src.shortname, self.ref.shortname
        )

        with open(fname, "w") as f:
            f.write(self.output())
        runLog.important(
            "Differences written between \n:REF: {} and \n:SRC: {} \nto {}".format(
                repr(self.ref), repr(self.src), fname
            )
        )
        return fname

    def compare(self) -> int:
        """Compare the source to the reference database, updating self.results with the findings"""
        runLog.important(
            "Comparing databases \n:REF: {} \n:SRC: {}"
            "".format(repr(self.ref), repr(self.src))
        )

        self.differences = _DifferencesOutputer()

        try:
            srcTS, refTS = self._compareTimeSteps()
            self._compareReactorStates(srcTS, refTS)
            self._compareAssemblyStates(srcTS, refTS)
            self._compareBlockStates(srcTS, refTS)
        except exceptions.NoDataModelInDatabaseException:
            msg = "Missing or incomplete data model in one or both databases."
            runLog.important(msg)
            self.differences.errors.append(msg)

        self._compareMiscData()

        return self.differences.nDifferences()

    def _compareTimeSteps(self):
        """Find the appropriate time steps to compare on"""
        runLog.important("Timestep comparisons...")
        name = DMNames.TIMESTEPS

        srcTS = self.src.getAllTimesteps()
        refTS = self.ref.getAllTimesteps()

        times = iterables.Overlap(srcTS, refTS)
        self.differences.add(name, structure=times)

        if self.timestepMatchup:
            if any(ts not in srcTS for ts in self.timestepMatchup.keys()):
                raise ValueError(
                    "Supplied timestep matchup keys not valid. DB contains {}, received {}".format(
                        srcTS, self.timestepMatchup.keys()
                    )
                )
            if any(ts not in refTS for ts in self.timestepMatchup.values()):
                raise ValueError(
                    "Supplied timestep matchup keys not valid. DB contains {}, received {}".format(
                        refTS, self.timestepMatchup.values()
                    )
                )
        else:
            self.timestepMatchup = {ts: ts for ts in times.matched}

        matches = self.timestepMatchup.items()
        if self.selection:
            matches = [matches[i] for i in self.selection]

        if not matches:
            # zip gives us the shortest, so it is possible one will have more timenodes.
            matches = [(sts, rts) for sts, rts in zip(srcTS, refTS)]

        srcTS, refTS = zip(*matches)
        return list(srcTS), list(refTS)

    def _compareReactorStates(self, srcTS, refTS):
        """Generates difference information for the reactor states in the src & ref"""
        runLog.important("Reactor state comparisons...")
        name = DMNames.REACTORS

        params = iterables.Overlap(
            self.src.getReactorParamNames(), self.ref.getReactorParamNames()
        )

        param_matched = list(params.matched)
        src_state_data = self.src.readReactorParams(param=param_matched, ts=srcTS)
        ref_state_data = self.ref.readReactorParams(param=param_matched, ts=refTS)

        diffs = self._compareSingularStateData(
            params, src_state_data, ref_state_data, weightKey=self.weights.get(name, "")
        )

        self.differences.add(name, structure=params, diffs=diffs)

    def _compareAssemblyStates(self, srcTS, refTS):
        """Generates difference information for the assembly states in the src & ref"""
        runLog.important("Assembly state comparisons...")
        name = DMNames.ASSEMBLIES

        params = iterables.Overlap(
            self.src.getAssemblyParamNames(), self.ref.getAssemblyParamNames()
        )

        param_matched = list(params.matched)
        src_state_data = self.src.readAssemblyParams(param=param_matched, ts=srcTS)
        ref_state_data = self.ref.readAssemblyParams(param=param_matched, ts=refTS)

        diffs = self._compareNestedStateData(
            params, src_state_data, ref_state_data, weightKey=self.weights.get(name, "")
        )

        self.differences.add(name, structure=params, diffs=diffs)

    def _compareBlockStates(self, srcTS, refTS):
        """Generates difference information for the block states in the src & ref"""
        runLog.important("Block state comparisons...")
        name = DMNames.BLOCKS

        params = iterables.Overlap(
            self.src.getBlockParamNames(), self.ref.getBlockParamNames()
        )

        param_matched = list(params.matched)
        src_state_data = self.src.readBlockParams(param=param_matched, ts=srcTS)
        ref_state_data = self.ref.readBlockParams(param=param_matched, ts=refTS)

        diffs = self._compareNestedStateData(
            params, src_state_data, ref_state_data, weightKey=self.weights.get(name, "")
        )

        self.differences.add(name, structure=params, diffs=diffs)

    def _compareMiscData(self):
        """Generates difference information for the registered misc data storages in the src & ref"""
        runLog.important("Misc. data comparisons...")
        names = iterables.Overlap(
            self.src._getDataNamesToCompare(),  # pylint: disable=protected-access
            self.ref._getDataNamesToCompare(),  # pylint: disable=protected-access
        )

        self.differences.add("Known Misc Data", structure=names)

        names_matched = sorted(list(names.matched))
        for name in names_matched:
            try:
                src_state_data = self.src.readDataFromDB(name)
                ref_state_data = self.ref.readDataFromDB(name)
            except KeyError:
                runLog.warning(
                    "Table {} is listed as common between DB but is not "
                    "actually in both databases. This indicates an inconsistent "
                    "DB structure.".format(name)
                )
                continue

            keys = iterables.Overlap(src_state_data.keys(), ref_state_data.keys())

            diffs = self._compareSingularStateData(
                keys,
                src_state_data,
                ref_state_data,
                weightKey=self.weights.get(name, ""),
            )

            self.differences.add(name, structure=keys, diffs=diffs)

    # ------------------------------------------

    def _compareSingularStateData(self, keys, src, ref, weightKey=""):
        """Generates difference information from two dictionaries

        General format of dictionary is { key : [ [data for ts 0], [data for ts 1], ... ] }

        """
        state_differences = {}

        for key in list(keys.matched):  # pylint: disable=too-many-nested-blocks
            if key in self.exclusion:
                runLog.important(
                    "skipping comparison of {} as it was excluded".format(key)
                )
                continue
            src_data = src[key]
            ref_data = ref[key]
            try:
                weights = [1.0] * len(src_data) if not weightKey else src[weightKey]
            except TypeError as error:
                runLog.error(
                    "Something went wrong with db comparison for {} (weightKey: {})".format(
                        key, weightKey
                    )
                )
                raise error

            final_labels = Comparisons.Labels.SINGULAR

            diff_data = []
            for s, r, w in zip(  # pylint: disable=invalid-name
                src_data, ref_data, weights
            ):
                try:
                    # Reactor data is passed out in nested lists despite really being
                    # single values. This was done for API consistency
                    s = s[0]  # pylint: disable=invalid-name
                    r = r[0]  # pylint: disable=invalid-name
                    w = w[0]  # pylint: disable=invalid-name
                except (TypeError, IndexError):
                    pass

                if isinstance(s, (list, numpy.ndarray)):
                    if not isinstance(r, (list, numpy.ndarray)):
                        diff_data.append([Comparisons.Errors.MISMATCHED_TYPES])
                        final_labels = Comparisons.Labels.ERROR
                    else:  # TODO: weighting on this
                        final_labels = Comparisons.Labels.LISTS_MDIFFONLY

                        if len(src_data) != len(ref_data):
                            diff_data.append([Comparisons.Errors.MISMATCHED_LENGTHS])
                            final_labels = Comparisons.Labels.ERROR
                        else:
                            for s2, r2 in zip(src_data, ref_data):
                                weight = [1.0 for _ in s2]
                                labels, data = self._diffListValues(s2, r2, weight)
                                diff_data.append(data)
                                if labels:
                                    final_labels = labels
                elif isinstance(r, (list, numpy.ndarray)):  # just r is a list. problem!
                    diff_data.append([Comparisons.Errors.MISMATCHED_TYPES])
                    final_labels = Comparisons.Labels.ERROR
                else:
                    labels, data = self._diffSingleValues(s, r, w)
                    diff_data.append(data)
                    if labels:
                        final_labels = labels

            state_differences[key] = (diff_data, final_labels)

        return state_differences

    def _diffSingleValues(self, src, ref, weight):
        """Differences between two values"""
        try:
            change = compare(src, ref, weight)
        except ValueError:
            return Comparisons.Labels.ERROR, [Comparisons.Errors.MISMATCHED_TYPES]

        if abs(change) <= self.tolerance:
            return None, []

        return None, [ref, src, change]

    def _compareNestedStateData(self, keys, src, ref, weightKey=""):
        """Generates difference information from two dictionaries

        General format of dictionary is { key : [ [data for ts 0], [data for ts 1], ... ] }

        """
        state_differences = {}

        for key in list(keys.matched):
            if key in self.exclusion:
                runLog.important(
                    "skipping comparison of {} as it was excluded".format(key)
                )
                continue
            src_data = src[key]
            ref_data = ref[key]

            if weightKey:
                weights = src[weightKey]
            else:
                weights = [[1.0 for _composite in timeStep] for timeStep in src_data]

            diff_data = []
            final_labels = Comparisons.Labels.LISTS_MDIFFONLY

            if len(src_data) == len(ref_data) == len(weights):
                for srcVal, refVal, weight in zip(src_data, ref_data, weights):
                    labels, data = self._diffListValues(srcVal, refVal, weight)
                    diff_data.append(data)
                    if labels:
                        final_labels = labels
            else:
                diff_data.append(Comparisons.Errors.MISMATCHED_LENGTHS)
                final_labels = Comparisons.Labels.ERROR

            state_differences[key] = (diff_data, final_labels)

        return state_differences

    def _diffListValues(self, src, ref, weights):
        """Comparison of the differences between two lists of values"""
        diffs = []
        labels = None

        weights = [_numericalClean(v) for v in weights]

        try:
            if not (len(src) == len(ref) == len(weights)):
                diffs.append(Comparisons.Errors.MISMATCHED_LENGTHS)
                return Comparisons.Labels.ERROR, diffs
        except TypeError:
            if src is None and ref is None:
                return labels, []
            diffs.append(Comparisons.Errors.MISMATCHED_TYPES)
            return Comparisons.Labels.ERROR, diffs

        if any(isinstance(s, (list, numpy.ndarray)) for s in src):
            try:
                weights = numpy.array(weights)
                weight_sum = weights.sum()
                src = numpy.array(list(zip(*src))) * weights
                ref = numpy.array(list(zip(*ref))) * weights

                src = numpy.array([i.sum() / weight_sum for i in src])
                ref = numpy.array([i.sum() / weight_sum for i in ref])
                # stop weights from re-weighting in later operation
                weights = [1.0 for _ in src]
            except:  # pylint: disable=bare-except
                return Comparisons.Labels.ERROR, diffs

        labels, diffs = self._diffSingleListHelper(src, ref, weights)

        return labels, diffs

    def _diffSingleListHelper(self, src, ref, weights):
        """
        Return the max diff and average diffs if they meet the tolerance

        Notes
        -----
        There will be 1 item in the list if only max diff meets the threshold.
        If the average meets the tolerance, both average and abs average will be
        returned. Extra labels are also returned if the average meets the threshold.
        """
        diffs = []
        labels = None

        total_weight = 0.0

        change_sum = 0.0
        abs_change_sum = 0.0
        max_diff = 0.0

        try:
            for srcVal, refVal, weight in zip(src, ref, weights):
                if weight == 0:
                    # sometimes flux is zero and then weight is zero
                    weight = 1.0e-10
                total_weight += weight
                change = compare(srcVal, refVal, weight)
                change_sum += change
                abs_change_sum += abs(change)
                mdiff_change = change / weight
                if abs(mdiff_change) > abs(max_diff):
                    # max_diff respects the sign of the differences
                    max_diff = mdiff_change
        except (ValueError, TypeError):
            diffs.append(Comparisons.Errors.MISMATCHED_TYPES)
            return Comparisons.Labels.ERROR, diffs

        avg = change_sum / total_weight
        abs_avg = abs_change_sum / total_weight

        if abs(max_diff) > self.tolerance:
            diffs.append(max_diff)

        if abs_avg > self.tolerance:
            diffs.extend([abs_avg, avg])
            labels = Comparisons.Labels.LISTS_FULL
        return labels, diffs


def _numericalClean(value):
    try:
        if value is None or numpy.isnan(value):
            return 0.0
    except (ValueError, TypeError):
        pass
    return value


def areComparable(src, ref):
    if src.__class__ == ref.__class__:
        return True

    try:  # faster than checking types, turns out
        float(src)
        float(ref)
        return True
    except (ValueError, TypeError):
        return False


def _assessChange(src, ref):
    if src == 0.0 and ref == 0.0:
        return 0.0
    if src == 0.0:
        change = -100.0 if ref > 0.0 else 100.0
    elif ref == 0.0:
        change = 100.0 if src > 0.0 else -100.0
    else:
        change = ((src - ref) / float(ref)) * 100.0
    return change


def compare(src, ref, weight):
    """Compare two values, with a leaning towards treating them as numbers

    Returns the % difference between the two.
    Currently treats non-numeric values very naively as all-or-nothing similarities

    """
    if weight == 0.0:
        # RuntimeError so it is not able to be caught
        raise RuntimeError(
            "Cannot compare values with a weight of zero since "
            "this would always return zero."
        )
    src = _numericalClean(src)
    ref = _numericalClean(ref)
    if areComparable(src, ref):
        if isinstance(src, numbers.Number):
            return _assessChange(src, ref) * weight

        # non-numericals might need to be received a bit better than this.
        if isinstance(src, numpy.ndarray):
            same = (src == ref).all()
        else:
            same = src == ref
        if same:
            return 0.0
        return 100.0 * weight
    raise ValueError("Incompatible value types: {} vs {}".format(src, ref))


class Comparisons(object):  # pylint: disable=too-few-public-methods
    """Simple enumeration of different comparison issues"""

    class Errors(object):  # pylint: disable=too-few-public-methods
        """Cell entries possible for failures in the comparison"""

        MISMATCHED_TYPES = "ERR1"
        MISMATCHED_LENGTHS = "ERR2"

        @staticmethod
        def outputErrorKey():
            """Return a textual representation of the error"""
            output = [
                "+ Error Codes Key +",
                "{} = entries of incomparable data types".format(
                    Comparisons.Errors.MISMATCHED_TYPES
                ),
                "{} = entries of mismatched data list lengths".format(
                    Comparisons.Errors.MISMATCHED_LENGTHS
                ),
            ]

            return output

    class Labels(object):  # pylint: disable=too-few-public-methods
        """Row labels indicating what the given cell entry values denote"""

        LISTS_FULL = ["%  AVG", "% AAVG", "%MDIFF"]
        LISTS_MDIFFONLY = ["%MDIFF", "-", "-"]
        SINGULAR = [" %CHA ", " :SRC:", " :REF:"]
        ERROR = ["ERROR", "ERROR", "ERROR"]


class _DifferencesOutputer(object):
    """Store the added difference data, knows how to represent it cleanly"""

    def __init__(self):
        self._comparisons = collections.OrderedDict([])
        self.errors = []

    def add(self, name, structure=None, diffs=None):
        self._comparisons[name] = _DifferenceOutputer(
            name, structure=structure, diffs=diffs
        )

    def output(self):
        """Lists of strings to join to form the readable summary of differences between src & ref"""
        output = []

        if self.errors:
            output.extend(["", "!! COMPARISON ERRORS !!", "------------------------"])
            for error in self.errors:
                output.append(error)
            output.append("")

        for difference in self._comparisons.values():
            output.extend(difference.output())
        return output

    def hasDifferences(self):
        regdiffs = any(diff.hasDifferences() for diff in self._comparisons.values())
        errordiffs = bool(self.errors)
        return regdiffs or errordiffs

    def nDifferences(self):
        return sum(d.nDifferences() for d in self._comparisons.values())


class _DifferenceOutputer(object):
    """"Helper to the plural-collection manager class _DifferencesOutputer"""

    # only ignores currently for the hasDifferences evaluation.
    # not general outputting of differences.
    ignorableStructureDifferences = set(["RowID", "TimeStep"])

    def __init__(self, name, structure=None, diffs=None):
        self.name = name

        self.structure = structure
        self.diffs = diffs

        self.header = (
            None  # could pass in the header but it's so far always been 0-9etc
        )
        if self.diffs:
            self.header = ["Params", "Labels"] + [
                i for i in range(len(self.diffs[list(self.diffs.keys())[0]][0]))
            ]

        self.cellwidths = 12

    def hasDifferences(self):
        """Return whether differences exist between the DBs being compared"""
        return self.nDifferences() > 0

    def _nStructDifferences(self):
        if self.structure is not None:
            structure = copy.deepcopy(self.structure)
            for falsepositive in _DifferenceOutputer.ignorableStructureDifferences:
                structure.src_missed.discard(falsepositive)
                structure.ref_missed.discard(falsepositive)
            return len(structure.src_missed) + len(structure.ref_missed)
        else:
            return 0

    def nDifferences(self):
        """Return the number of differences found."""
        nDiffs = self._nStructDifferences()
        if self.diffs:
            # This one is pretty nasty... essentially sums up how many differences are
            # found for all parameters, for all different metrics. It's pretty crude,
            # but gives a decent idea of how different two cases are.
            nDiffs += sum(
                sum(len(timeDiffs) for timeDiffs in diffType)
                for diffType in (paramDiff[0] for paramDiff in self.diffs.values())
            )
        return nDiffs

    def output(self):
        """Return textual output describing the difference between data"""

        output = [
            "",
            "- {}".format(self.name.upper()),
            "-----------------------------------------",
        ]

        if self.structure:
            output.extend(["Structure perceived as a perfect match", ""])
        elif self.structure is not None:
            output.append("Structure differs between databases!")
            output.append(
                ":SRC: has the following not in :REF: {}".format(
                    sorted(list(self.structure.src_missed))
                )
            )
            output.append(
                ":REF: has the following not in :SRC: {}".format(
                    sorted(list(self.structure.ref_missed))
                )
            )
            output.append("")
        else:
            pass  # no structural information was provided, keep silent

        if not self.diffs:
            pass  # no differences were provided, keep silent
        else:
            output.extend(self._tabularizeDictOfDifferences())
            output.append("")

        return output

    def _formatValue(self, value, labels):
        floatCellFormat = "{{:.{}F}}".format(self.cellwidths + 5)
        if isinstance(value, float):
            if abs(value) >= 1000.0 and labels != Comparisons.Labels.SINGULAR:
                if value > 0:
                    return "> 999.9"
                return "<-999.9"
            # float precision loss
            return floatCellFormat.format(value)[: self.cellwidths - 1]
        return str(value)[: self.cellwidths - 1]

    def _tabularizeDictOfDifferences(self):
        table = []

        paramColWidth = len(max(self.diffs.keys(), key=len)) + 1
        rowFormat = self._generateTableRowStringFormat(paramColWidth)
        closingBorder = self._generateTableRowClosingBorder(paramColWidth)

        # create header
        table.append(closingBorder)
        table.append(rowFormat.format(*self.header))
        table.append(closingBorder)

        # create body
        for param, (diffs, labels) in sorted(self.diffs.items(), key=lambda x: x[0]):
            if not any(diffs):
                continue

            rows = list(zip_longest(*diffs, fillvalue="~"))

            for i, row in enumerate(reversed(rows)):

                cleanRow = []
                for value in row:
                    cleanRow.append(self._formatValue(value, labels))

                try:
                    fittedRow = [param, labels[i]] + list(cleanRow)
                except IndexError:
                    # happens when number of blocks/assems changed.
                    fittedRow = [param, "??"] + list(cleanRow)

                try:
                    table.append(rowFormat.format(*fittedRow))
                except IndexError:
                    runLog.error(
                        "Failed to tabularize `{}` with the format string `{}`".format(
                            fittedRow, rowFormat
                        )
                    )
                    raise

            table.append(closingBorder)

        if len(table) == 3:  # only the header exists, databases match
            return ["Content perceived as a perfect match"]

        return table

    def _generateTableRowStringFormat(self, paramColWidth):
        fmt = ["{{:<{}}}".format(paramColWidth), "{:^6}"]
        for _ in range(len(self.header) - 2):
            fmt.append("{{:>{}}}".format(self.cellwidths))
        return "|" + "|".join(fmt) + "|"

    def _generateTableRowClosingBorder(self, paramColWidth):
        border = ["-" * paramColWidth, "-" * 6]
        for _ in range(len(self.header) - 2):
            border.append("-" * self.cellwidths)
        return "+" + "+".join(border) + "+"

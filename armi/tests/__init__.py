# Copyright 2021 TerraPower, LLC
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
General framework-wide testing functions and files.

This package contains some input files that can be used across
a wide variety of unit tests in other lower-level subpackages.
"""
import datetime
import itertools
import os
import re
import shutil
import unittest
from typing import Optional

from armi import context
from armi import runLog
from armi.reactor import geometry
from armi.reactor import grids
from armi.reactor import reactors

TEST_ROOT = os.path.dirname(os.path.abspath(__file__))
ARMI_RUN_PATH = os.path.join(TEST_ROOT, "armiRun.yaml")
ISOAA_PATH = os.path.join(TEST_ROOT, "ISOAA")
COMPXS_PATH = os.path.join(TEST_ROOT, "COMPXS.ascii")


def getEmptyHexReactor():
    """Make an empty hex reactor used in some tests."""
    from armi.reactor import blueprints

    bp = blueprints.Blueprints()
    reactor = reactors.Reactor("Reactor", bp)
    reactor.add(reactors.Core("Core"))
    reactor.core.spatialGrid = grids.HexGrid.fromPitch(1.0)
    reactor.core.spatialGrid.symmetry = geometry.SymmetryType(
        geometry.DomainType.THIRD_CORE, geometry.BoundaryType.PERIODIC
    )
    reactor.core.spatialGrid.geomType = geometry.HEX
    reactor.core.spatialGrid.armiObject = reactor.core
    return reactor


def getEmptyCartesianReactor(pitch=(10.0, 16.0)):
    """Return an empty Cartesian reactor used in some tests."""
    from armi.reactor import blueprints

    bp = blueprints.Blueprints()
    reactor = reactors.Reactor("Reactor", bp)
    reactor.add(reactors.Core("Core"))
    reactor.core.spatialGrid = grids.CartesianGrid.fromRectangle(*pitch)
    reactor.core.spatialGrid.symmetry = geometry.SymmetryType(
        geometry.DomainType.QUARTER_CORE,
        geometry.BoundaryType.REFLECTIVE,
        throughCenterAssembly=True,
    )
    reactor.core.spatialGrid.geomType = geometry.CARTESIAN
    reactor.core.spatialGrid.armiObject = reactor.core
    return reactor


class Fixture:
    """
    Fixture for presenting a consistent data source for testing.

    A Fixture is a class that wraps a function which generates resources needed by one
    or more tests that doesn't need to be updated every time tests are run.

    Do not use this class directly, instead use the :code:`@fixture` and :code:`@requires_fixture`
    decorators.
    """

    def __init__(self, refDirectory, targets, dependencies, function):
        def resolvePath(relativePath):
            absolutePath = os.path.abspath(relativePath)
            if absolutePath != relativePath:
                absolutePath = os.path.join(refDirectory, relativePath)
            return absolutePath

        self.targets = [resolvePath(t) for t in targets]
        self.dependencies = [resolvePath(d) for d in dependencies]
        self._function = function
        self._isUpToDate = None
        self.__name__ = function.__name__
        self.__doc__ = function.__doc__
        self._error = None
        self._success = False
        self.status = None

    def __repr__(self):
        return "{}.{}".format(self._function.__module__, self.__name__)

    def __call__(self):
        if self._error is not None:
            raise self._error  # pylint: disable=E0702
        elif not self._success:
            missingDependencies = [
                d for d in self.dependencies if not os.path.exists(d)
            ]
            if any(missingDependencies):
                self._error = EnvironmentError(
                    "Missing dependencies:\n    {}".format(
                        "\n    ".join(missingDependencies)
                    )
                )
                raise self._error  # pylint: disable=E0702
            # at this point we need to update because
            # 1) there are missing targets that need to be generated, or
            # 2) targets are older than the dependencies.
            missingTargets = [t for t in self.targets if not os.path.exists(t)]
            needToUpdate = any(missingTargets)
            if any(missingTargets):
                runLog.important(
                    "Fixture is missing targets {}\n    {}".format(
                        self, "\n    ".join(missingTargets)
                    )
                )
            if not needToUpdate:
                # this doesn't need to run if there are any missing targets.
                oldestTarget = sorted((os.path.getmtime(t), t) for t in self.targets)[0]
                newestDependency = sorted(
                    (os.path.getmtime(d), d) for d in self.dependencies
                )[-1]
                needToUpdate = newestDependency[0] > oldestTarget[0]
                if needToUpdate:
                    targetTime = datetime.datetime.fromtimestamp(oldestTarget[0])
                    dependencyTime = datetime.datetime.fromtimestamp(
                        newestDependency[0]
                    )
                    runLog.important(
                        "Fixture is out of date {}\n"
                        "oldest target:     {} {}\n"
                        "newest dependency: {} {}".format(
                            self,
                            targetTime,
                            oldestTarget[1],
                            dependencyTime,
                            newestDependency[1],
                        )
                    )
            if needToUpdate:
                runLog.important("Running test fixture: {}".format(self))
                try:
                    self._function()
                except Exception as ee:
                    self._error = ee
                    raise
            else:
                runLog.important("Skipping test fixture: {}".format(self))
        runLog.important("Fixture is up to date: {}".format(self))
        self._success = True


def fixture(refDirectory=None, targets=None, dependencies=None):
    r"""
    Decorator to run function based on targets and dependencies similar to GNU Make.

    Parameters
    ==========
    refDirectory : str
        String reference directory for all targets/dependencies. This makes it possible to simplify file paths.
        If ``os.path.abspath(<path>) == <path>``, then refDirectory is not used.

    targets : iterable(str)
        List of targets that the function generates.

    dependencies : iterable(str)
        List of dependencies that the ``targets`` require.

    """

    def _decorator(makeFunction):
        return Fixture(refDirectory, targets, dependencies, makeFunction)

    return _decorator


def requires_fixture(fixtureFunction):
    r"""
    Decorator to require a fixture to have been completed.

    Parameters
    ==========
    fixtureFunction : function without any parameters
        Fixture function is a function that has been decorated with ``fixture`` and is called prior to running
        the decorated function.

    Notes
    =====
    This cannot be used on classes.
    """

    def _decorator(func):
        def _callWrapper(*args, **kwargs):
            fixtureFunction()
            func(*args, **kwargs)

        return _callWrapper

    return _decorator


class ArmiTestHelper(unittest.TestCase):
    """Class containing common testing methods shared by many tests."""

    def compareFilesLineByLine(
        self, expectedFilePath, actualFilePath, falseNegList=None, eps=None
    ):
        """
        Compare the contents of two files line by line.

        .. warning:: The file located at actualFilePath will be deleted if they do match.

        Some tests write text files that should be compared line-by-line with reference files.
        This method performs the comparison.

        This class of test is not ideal but does cover a lot of functionality quickly. To assist
        in the maintenance burden, the following standards are expected and enforced:

        * The reference file compared against will be called either ``[name]-ref.[ext]`` or ``[name].expected``.
        * The file that the test creates will be called ``[name]-test.[ext]`` or ``[name]``.

        Rebaselining the reference files upon large, expected, hand-verified changes is accomodated by
        :py:meth:`rebaselineTextComparisons`.

        Parameters
        ----------
        expectedFilePath: str
            Path to the reference or expected file
        actualFilePath: str
            Path to the file that will be compared to ``expectedFilePath``
        falseNegList: None or Iterable
            Optional argument. If two lines are not equal, then check if any values
            from ``falseNegList`` are in this line. If so, do not fail the test.
        eps: float, optional
            If provided, try to determine if the only difference between compared lines
            is in the value of something that can be parsed into a float, and the
            relative difference between the two floats is below the passed epsilon.
        """

        if falseNegList is None:
            falseNegList = []
        elif isinstance(falseNegList, str):
            falseNegList = [falseNegList]

        with open(expectedFilePath, "r") as expected, open(
            actualFilePath, "r"
        ) as actual:
            for lineIndex, (expectedLine, actualLine) in enumerate(
                itertools.zip_longest(expected, actual)
            ):
                if expectedLine is None:
                    raise AssertionError(
                        "The test-generated file is longer than expected file"
                    )
                if actualLine is None:
                    raise AssertionError(
                        "The test-generated file is shorter than expected file"
                    )

                if not self.compareLines(actualLine, expectedLine, eps):
                    if any(
                        falseNeg in line
                        for falseNeg in falseNegList
                        for line in (actualLine, expectedLine)
                    ):
                        pass
                    else:
                        raise AssertionError(
                            "Error on line {}:\nE>{}\nA<{}".format(
                                lineIndex, expectedLine.rstrip(), actualLine.rstrip()
                            )
                        )

        os.remove(actualFilePath)

    @staticmethod
    def compareLines(actual: str, expected: str, eps: Optional[float] = None):
        """
        Impl of line comparison for compareFilesLineByLine.

        if rstripped lines are equal -> Good. Otherwise, split on whitespace and try to
        parse element pairs as floats. if they are both parsable, compare with relative
        eps, if provided. A side effect of the epsilon comparison is that differing
        whitespace **between** words is treated as irrelevant.
        """
        actual = actual.rstrip()
        expected = expected.rstrip()

        if actual == expected:
            return True

        if eps is None:
            # no more in-depth comparison is allowed
            return False

        actualWords = actual.split()
        expectedWords = expected.split()

        if len(actualWords) != len(expectedWords):
            # different number of words cant possibly be the same enough
            return False

        for actualWord, expectedWord in zip(actualWords, expectedWords):
            actualVal = _tryFloat(actualWord)
            expectedVal = _tryFloat(expectedWord)

            if (actualVal is None) ^ (expectedVal is None):
                # could not coerce both words into a float, so they cannot possibly
                # match
                return False

            if actualVal is not None:
                # we have two floats and can compare them
                if abs(actualVal - expectedVal) / expectedVal > eps:
                    return False
            else:
                # strings, compare directly
                if actualWord != expectedWord:
                    return False

        # if we got to the end without pitching a fit, the lines should match
        return True


def _tryFloat(val: str) -> Optional[float]:
    try:
        return float(val)

    except ValueError:
        return None


def rebaselineTextComparisons(root):
    """
    Rebaseline test line-by-line comparison files.

    This scans the source tree for failed unit test file comparisons
    (indicated by the presence of, for example, a ``-test.inp`` and a ``-ref.inp`` file)
    and moves the test one to the reference one. The work done can be reviewed/approved
    in source management.

    This is convenient when a large-scope change is made, such as updating the properties
    of a commonly-used material.
    """
    runLog.info(f"Rebaselining all unit test file comparisons under {root}...")
    for dirname, _dirs, files in os.walk(root):
        if "tests" not in dirname:
            continue
        for refFileName in files:
            match = re.search(r"^(\S+?)-ref\.(\S+)$", refFileName)
            if refFileName.endswith(".expected"):
                testFileName = refFileName.replace(".expected", "")
            elif match:
                testFileName = match.group(1) + "-test." + match.group(2)
            else:
                continue
            refFileName = os.path.join(dirname, refFileName)
            testFileName = os.path.join(dirname, testFileName)
            if not os.path.exists(testFileName):
                testFileName += ".inp"  # cover some edge cases
            if os.path.exists(testFileName):
                runLog.info("Overwriting {} with {}".format(refFileName, testFileName))
                shutil.move(testFileName, refFileName)


if __name__ == "__main__":
    # Calling this directly runs the test rebaseline function (could/should be an entrypoint)
    import sys

    if len(sys.argv) == 1:
        rebaselineTextComparisons(context.ROOT)
    else:
        rebaselineTextComparisons(sys.argv[1])

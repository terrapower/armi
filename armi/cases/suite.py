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

r"""
The ``CaseSuite`` object is responsible for running, and executing a set of user inputs.  Many
entry points redirect into ``CaseSuite`` methods, such as ``clone``, ``compare``, and ``submit``.

Used in conjunction with the :py:class:`~armi.cases.case.Case` object, ``CaseSuite`` can be used to
collect a series of cases and submit them to a cluster for execution. Furthermore, a ``CaseSuite``
can be used to gather executed cases for post-analysis.

``CaseSuite``\ s should allow ``Cases`` to be added from totally separate directories. This is
useful for plugin-informed testing as well as other things.

See Also
--------
armi.cases.case : An individual item of a case suite.
"""

import os
import traceback
from typing import Optional, Sequence

from armi import runLog, settings
from armi.cases import case as armicase
from armi.utils import directoryChangers, tabulate


class CaseSuite:
    """
    A CaseSuite is a collection of possibly related Case objects.

    .. impl:: CaseSuite allows for one case to start after another completes.
        :id: I_ARMI_CASE_SUITE
        :implements: R_ARMI_CASE_SUITE

        The CaseSuite object allows multiple, often related,
        :py:class:`~armi.cases.case.Case` objects to be run sequentially. A CaseSuite
        is intended to be both a pre-processing or a post-processing tool to facilitate
        case generation and analysis. Under most circumstances one may wish to subclass
        a CaseSuite to meet the needs of a specific calculation. A CaseSuite is a
        collection that is keyed off Case titles.
    """

    def __init__(self, cs):
        self._cases = list()
        self.cs = cs

    def add(self, case):
        """
        Add a Case object to the CaseSuite.

        Case objects within a CaseSuite must have unique ``title`` attributes, a
        KeyError will be raised
        """
        existing = next((c for c in self if case == c), None)
        if existing is not None:
            raise ValueError(
                "CaseSuite already contains case with title `{}`\nFirst case:  {}\nSecond case: {}".format(
                    case.title, existing, case
                )
            )
        self._cases.append(case)
        case._caseSuite = self

    def remove(self, case):
        """Remove a case from a suite."""
        self._cases.remove(case)
        case._caseSuite = None

    def __iter__(self):
        return iter(self._cases)

    def __len__(self):
        return len(self._cases)

    def discover(
        self,
        rootDir=None,
        patterns=None,
        ignorePatterns=None,
        recursive=True,
        skipInspection=False,
    ):
        """
        Finds case objects by searching for a pattern of file paths, and adds them to
        the suite.

        This searches for Settings input files and loads them to create Case objects.

        Parameters
        ----------
        rootDir : str, optional
            root directory to search for settings files
        patterns : list of str, optional
            file pattern to use to filter file names
        ignorePatterns : list of str, optional
            file patterns to exclude matching file names
        recursive : bool, optional
            if True, recursively search for settings files
        skipInspection : bool, optional
            if True, skip running the check inputs
        """
        csFiles = settings.recursivelyLoadSettingsFiles(
            rootDir or os.path.abspath(os.getcwd()),
            patterns or ["*.yaml"],
            recursive=recursive,
            ignorePatterns=ignorePatterns,
            handleInvalids=False,
        )

        for cs in csFiles:
            case = armicase.Case(cs=cs, caseSuite=self)
            if not skipInspection:
                case.checkInputs()
            self.add(case)

    def echoConfiguration(self):
        """
        Print information about this suite to the run log.

        Notes
        -----
        Some of these printouts won't make sense for all users, and may make sense to
        be delegated to the plugins/app.
        """
        for setting in self.cs.environmentSettings:
            runLog.important("{}: {}".format(self.cs.getSetting(setting).label, self.cs[setting]))

        runLog.important("Test inputs will be taken from test case results when they have finished")
        runLog.important(
            tabulate.tabulate(
                [
                    (
                        c.title,
                        "T" if c.enabled else "F",
                        ",".join(d.title for d in c.dependencies),
                    )
                    for c in self
                ],
                headers=["Title", "Enabled", "Dependencies"],
                tableFmt="armi",
            )
        )

    def clone(self, oldRoot=None, writeStyle="short"):
        """
        Clone a CaseSuite to a new place.

        Creates a clone for each case within a CaseSuite. If ``oldRoot`` is not
        specified, then each case clone is made in a directory with the title of the
        case. If ``oldRoot`` is specified, then a relative path from ``oldRoot`` will
        be used to determine a new relative path to the current directory ``oldRoot``.

        Parameters
        ----------
        oldRoot : str (optional)
            root directory of original case suite used to help filter when a suite
            contains one or more cases with the same case title.
        writeStyle : str (optional)
            Writing style for which settings get written back to the settings files
            (short, medium, or full).

        Notes
        -----
        By design, a CaseSuite has no location dependence; this allows any set of cases
        to compose a CaseSuite. The thought is that the post-analysis capabilities
        without restricting a root directory could be beneficial. For example, this
        allows one to perform analysis on cases analyzed by Person A and Person B, even
        if the analyses were performed in completely different locations. As a
        consequence, when you want to clone, we need to infer a "root" of the original
        cases to attempt to mirror whatever existing directory structure there may have
        been.
        """
        clone = CaseSuite(self.cs.duplicate())

        modifiedSettings = {ss.name: ss.value for ss in self.cs.values() if ss.offDefault}
        for case in self:
            if oldRoot:
                newDir = os.path.dirname(os.path.relpath(case.cs.path, oldRoot))
            else:
                newDir = case.title
            with directoryChangers.ForcedCreationDirectoryChanger(newDir, dumpOnException=False):
                clone.add(case.clone(modifiedSettings=modifiedSettings, writeStyle=writeStyle))
        return clone

    def run(self):
        """
        Run each case, one after the other.

        Warning
        -------
        Suite running may not work yet if the cases have interdependencies. We typically run on a
        HPC but are still working on a platform independent way of handling HPCs.
        """
        for ci, case in enumerate(self):
            runLog.important(f"Running case {ci + 1}/{len(self)}: {case}")
            with directoryChangers.DirectoryChanger(case.directory):
                try:
                    case.run()
                except Exception:
                    # allow all errors and continue to next run
                    runLog.error(f"{case} failed during execution.")
                    traceback.print_exc()

    def compare(
        self,
        that,
        exclusion: Optional[Sequence[str]] = None,
        weights=None,
        tolerance=0.01,
        timestepCompare=None,
    ) -> int:
        """
        Compare one case suite with another.

        Returns
        -------
        The number of problem differences encountered.
        """
        runLog.important("Comparing case suites.")

        nIssues = 0

        refTitles = set(c.title for c in self)
        cmpTitles = set(c.title for c in that)
        suiteHasMissingFiles = False
        tableResults = {}
        for caseTitle in refTitles.union(cmpTitles):
            refCase = next((c for c in self if c.title == caseTitle), None)
            cmpCase = next((c for c in that if c.title == caseTitle), None)
            caseStatus = []
            for case in (refCase, cmpCase):
                status = "Found"
                if case is None or not os.path.exists(case.dbName):
                    status = "Missing"
                caseStatus.append(status)
            refFile, userFile = caseStatus
            if any(stat != "Found" for stat in caseStatus):
                # Case was not run, or failed to produce a database.
                # In either case, this is an issue.
                # It could possibly be a new test, but there is no way to tell this
                # versus a reference file being missing so when a new test is made
                # it will be an issue. After the first push with the new tests the files
                # will be copied over and future tests will be fine.
                caseIssues = 1
                suiteHasMissingFiles = False
            else:
                caseIssues = refCase.compare(
                    cmpCase,
                    exclusion=exclusion,
                    tolerance=tolerance,
                    timestepCompare=timestepCompare,
                )
            nIssues += caseIssues
            tableResults[caseTitle] = (userFile, refFile, caseIssues)

        self.writeTable(tableResults)
        if suiteHasMissingFiles:
            runLog.warning((UNMISSABLE_FAILURE.format(", ".join(t for t in refTitles - cmpTitles))))

        return nIssues

    def writeInputs(self, writeStyle="short"):
        """
        Write inputs for all cases in the suite.

        writeStyle : str (optional)
            Writing style for which settings get written back to the settings files
            (short, medium, or full).

        See Also
        --------
        clone
            Similar to this but doesn't let you write out new geometry or blueprints objects.
        """
        for case in self:
            case.writeInputs(sourceDir=self.cs.inputDirectory, writeStyle=writeStyle)

    @staticmethod
    def writeTable(tableResults):
        """Write a table summarizing the test differences."""
        fmt = "psql"
        print(
            (
                tabulate.tabulate(
                    [["Integration test directory: {}".format(os.getcwd())]],
                    ["SUMMARIZED INTEGRATION TEST DIFFERENCES:"],
                    tableFmt=fmt,
                )
            )
        )
        header = ["Test", "User File", "Reference File", "# Problem Diff Lines"]
        totalDiffs = 0
        data = []
        for testName in sorted(tableResults.keys()):
            userFile, refFile, caseIssues = tableResults[testName]
            data.append((testName, userFile, refFile, caseIssues))
            totalDiffs += caseIssues

        print(tabulate.tabulate(data, header, tableFmt=fmt))
        print(tabulate.tabulate([["Total number of differences: {}".format(totalDiffs)]], tableFmt=fmt))


UNMISSABLE_FAILURE = '''
!! THESE TESTS HAVE UNEXPECTED ABSENT RESULTS !!

                     uuuuuuu
                 uu$$$$$$$$$$$uu
              uu$$$$$$$$$$$$$$$$$uu
             u$$$$$$$$$$$$$$$$$$$$$u
            u$$$$$$$$$$$$$$$$$$$$$$$u
           u$$$$$$$$$$$$$$$$$$$$$$$$$u
           u$$$$$$$$$$$$$$$$$$$$$$$$$u
           u$$$$$$"   "$$$"   "$$$$$$u
           "$$$$"      u$u       $$$$"
            $$$u       u$u       u$$$
            $$$u      u$$$u      u$$$
             "$$$$uu$$$   $$$uu$$$$"
              "$$$$$$$"   "$$$$$$$"
                u$$$$$$$u$$$$$$$u
                 u$"$"$"$"$"$"$u
      uuu        $$u$ $ $ $ $u$$       uuu
     u$$$$        $$$$$u$u$u$$$       u$$$$
      $$$$$uu      "$$$$$$$$$"     uu$$$$$$
    u$$$$$$$$$$$uu    """""    uuuu$$$$$$$$$$
    $$$$"""$$$$$$$$$$uuu   uu$$$$$$$$$"""$$$"
     """      ""$$$$$$$$$$$uu ""$"""
               uuuu ""$$$$$$$$$$uuu
      u$$$uuu$$$$$$$$$uu ""$$$$$$$$$$$uuu$$$
      $$$$$$$$$$""""           ""$$$$$$$$$$$"
       "$$$$$"                      ""$$$$""
         $$$"                         $$$$"

Comparison suite is missing the following case titles: {}

'''

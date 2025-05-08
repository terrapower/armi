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

import os
import sys

from armi import runLog
from armi.cli.entryPoint import EntryPoint

# Params that are well-known to vary from run to run. In the future we should probably
# derive this from a parameter category so that it is extensible
DEFAULT_EXCLUSIONS = (
    "^.*/minutesSinceStart$",
    "^.*/maxProcessMemoryInMB$",
    "^.*/minProcessMemoryInMB$",
)

# Parameters that under normal circumstances would be the same, but may not be
# faithfully represented by an old database format.
CONVERTED_EXCLUSIONS = DEFAULT_EXCLUSIONS + (
    "^.*/serialNum$",
    "^.*/temperatureInC$",
    "^.*/volume$",
    "^.*/layout/temperatures$",
)


class CompareCases(EntryPoint):
    """Compare the databases from two ARMI cases."""

    name = "compare"

    def _addComparisonOptions(self):
        parser = self.parser
        parser.add_argument(
            "--tolerance",
            default=0.01,
            action="store",
            type=float,
            help=(
                "If a test database entry differs by more than this percent "
                "from the reference database, then it will be marked "
                "as a difference between the two databases."
            ),
        )
        parser.add_argument(
            "--weights",
            nargs="*",
            action="store",
            help="Period separated key/value pairs for database table weights",
        )
        parser.add_argument(
            "--exclude",
            default=CONVERTED_EXCLUSIONS,
            action="store",
            nargs="+",
            help=("Patterns for parameters to ignore in comparisons"),
        )
        parser.add_argument(
            "--timestepCompare",
            default=None,
            action="store",
            nargs="+",
            help=(
                "List of timesteps to compare. Note that any timestep not listed will "
                "not be compared. Format the cycle and node separated by a period. E.g. "
                "0.0 0.1 1.2 3.3 will compare c0n0, c0n1, c1n2, c3n3 and skip all others"
            ),
        )

    def addOptions(self):
        self._addComparisonOptions()
        parser = self.parser
        parser.add_argument(
            "refDB",
            type=str,
            help="The database to be used as the reference, baseline case.",
        )
        parser.add_argument(
            "cmpDB",
            type=str,
            help="The database to be used as the comparison, evaluated case.",
        )
        parser.add_argument(
            "--output", "-o", type=str, default="", help="Output file name."
        )

    def parse(self, args):
        EntryPoint.parse(self, args)

        if self.args.timestepCompare:
            self.args.timestepCompare = list(
                tuple(map(int, step.split("."))) for step in self.args.timestepCompare
            )

        if self.args.weights:
            self.args.weights = dict(w.split(".") for w in self.args.weights)

    def invoke(self):
        from armi.bookkeeping.db import compareDatabases

        diffs = compareDatabases(
            self.args.refDB,
            self.args.cmpDB,
            tolerance=self.args.tolerance,
            exclusions=self.args.exclude,
            timestepCompare=self.args.timestepCompare,
        )
        return diffs.nDiffs()


class CompareSuites(CompareCases):
    """Do a case-by-case comparison between two CaseSuites."""

    name = "compare-suites"

    def addOptions(self):
        self._addComparisonOptions()
        self.parser.add_argument(
            "reference",
            type=str,
            help="The root directory of the reference, or baseline, suite.",
        )
        self.parser.add_argument(
            "comparison",
            type=str,
            help="The root directory of the comparison, or evaluated, suite.",
        )
        self.parser.add_argument(
            "--patterns",
            "-p",
            nargs="*",
            type=str,
            default=["*.yaml"],
            help="Pattern to use while searching for ARMI settings files.",
        )

        self.parser.add_argument(
            "--additional_comparisons",
            nargs="*",
            type=str,
            default=[],
            help="Pattern tests that were not run but should appear in table.",
        )

        self.parser.add_argument(
            "--ignore",
            "-i",
            nargs="*",
            type=str,
            default=[],
            help="Pattern to search for inputs to ignore.",
        )
        self.parser.add_argument(
            "--skip-inspection",
            "-I",
            action="store_true",
            default=False,
            help="Skip inspection. By default, setting files are checked for integrity and consistency. These "
            "checks result in needing to manually resolve a number of differences. Using this option will "
            "suppress the inspection step.",
        )

    def invoke(self):
        from armi import cases

        if not os.path.exists(self.args.reference):
            runLog.error(
                "Could not find reference directory {}".format(self.args.reference)
            )
            sys.exit(1)

        if not os.path.exists(self.args.comparison):
            runLog.error(
                "Could not find comparison directory {}".format(self.args.comparison)
            )
            sys.exit(1)

        refSuite = cases.CaseSuite(self.cs)

        # contains all tests that user had access to
        allTests = []
        for pat in self.args.patterns + self.args.additional_comparisons:
            allTests.append(pat)
        refSuite.discover(
            rootDir=self.args.reference,
            patterns=allTests,
            ignorePatterns=self.args.ignore,
            skipInspection=self.args.skip_inspection,
        )

        cmpSuite = cases.CaseSuite(self.cs)
        cmpSuite.discover(
            rootDir=self.args.comparison,
            patterns=self.args.patterns,
            ignorePatterns=self.args.ignore,
            skipInspection=self.args.skip_inspection,
        )

        nIssues = refSuite.compare(
            cmpSuite,
            weights=self.args.weights,
            tolerance=self.args.tolerance,
            exclusion=self.args.exclude,
            timestepCompare=self.args.timestepCompare,
        )

        if nIssues > 0:
            sys.exit(1)

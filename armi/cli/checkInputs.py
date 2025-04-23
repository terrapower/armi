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

"""Entry point into ARMI to check inputs of a case or a whole folder of cases."""

import pathlib
import sys

from armi import runLog
from armi.cli.entryPoint import EntryPoint
from armi.utils.textProcessors import resolveMarkupInclusions


class ExpandBlueprints(EntryPoint):
    """
    Perform expansion of !include directives in a blueprint file.

    This is useful for testing inputs that make heavy use of !include directives.
    """

    name = "expand-bp"

    splash = False

    def addOptions(self):
        self.parser.add_argument(
            "blueprints", type=str, help="Path to root blueprints file"
        )

    def invoke(self):
        p = pathlib.Path(self.args.blueprints)
        if not p.exists():
            runLog.error("Blueprints file `{}` does not exist".format(str(p)))
            return 1
        stream = resolveMarkupInclusions(p)
        sys.stdout.write(stream.read())

        return None


class CheckInputEntryPoint(EntryPoint):
    """
    Check ARMI inputs for errors, inconsistencies, and the ability to initialize a reactor.

    Also has functionality to generate a summary report of the input design. This can be run on
    multiple cases and creates a table detailing the results of the input check.
    """

    name = "check-input"

    def addOptions(self):
        self.parser.add_argument(
            "--recursive",
            "-r",
            action="store_true",
            default=False,
            help="Recursively check directory structure for valid settings files",
        )
        self.parser.add_argument(
            "--skip-checks",
            "-C",
            action="store_true",
            default=False,
            help="Skip checking inputs (might be useful if you only want to generate a report).",
        )
        self.parser.add_argument(
            "patterns",
            type=str,
            nargs="*",
            default=["*.yaml"],
            help="File names or patterns",
        )

    def invoke(self):
        from armi import cases
        from armi.utils import tabulate

        suite = cases.CaseSuite(self.cs)
        suite.discover(patterns=self.args.patterns, recursive=self.args.recursive)

        table = []  # tuples (case, hasIssues, hasErrors)
        for case in suite:
            hasIssues = "UNKNOWN"
            if not self.args.skip_checks:
                hasIssues = "PASSED" if case.checkInputs() else "HAS ISSUES"

            canStart = "UNKNOWN"
            table.append((case.cs.path, case.title, canStart, hasIssues))

        runLog.important(
            tabulate.tabulate(
                table,
                headers=["case", "can start", "input is self consistent"],
                tableFmt="armi",
            )
        )

        if any(t[3] == "HAS ISSUES" for t in table):
            runLog.error("The case is not self consistent")

        if any(t[2] == "FAILED" for t in table):
            runLog.error("The case can not start")

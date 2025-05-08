# Copyright 2020 TerraPower, LLC
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

"""Run multiple ARMI cases one after the other on the local machine."""
import os

from armi import cases
from armi.cli.run import RunEntryPoint
from armi.utils import directoryChangers


class RunSuiteCommand(RunEntryPoint):
    """
    Recursively run all the cases in a suite one after the other on the local machine.

    Invoke with ``mpirun`` or ``mpiexec`` to activate parallelism within each individual case.
    """

    name = "run-suite"

    def addOptions(self):
        RunEntryPoint.addOptions(self)
        self.parser.add_argument(
            "patterns",
            nargs="*",
            type=str,
            default=["*.yaml"],
            help="Pattern to use while searching for ARMI settings files.",
        )
        self.parser.add_argument(
            "--ignore",
            "-i",
            nargs="+",
            type=str,
            default=[],
            help="Pattern to search for inputs to ignore.",
        )
        self.parser.add_argument(
            "--list",
            "-l",
            action="store_true",
            default=False,
            help="Just list the settings files found, don't actually run them.",
        )
        self.parser.add_argument(
            "--suiteDir",
            type=str,
            default=os.getcwd(),
            help=(
                "The path containing the case suite to run. Default current "
                "working directory."
            ),
        )

    def invoke(self):
        with directoryChangers.DirectoryChanger(
            self.args.suiteDir, dumpOnException=False
        ):
            suite = cases.CaseSuite(self.cs)
            suite.discover(patterns=self.args.patterns, ignorePatterns=self.args.ignore)
            if self.args.list:
                suite.echoConfiguration()
            else:
                suite.run()

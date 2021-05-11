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

from armi.cli.entryPoint import EntryPoint


class CloneArmiRunCommandBatch(EntryPoint):
    """
    Clone existing ARMI settings input, and associated files, to the current
    directory and modify it according to the supplied settings (on the
    command line).
    """

    name = "clone-batch"
    settingsArgument = "required"

    def addOptions(self):
        for settingName in self.cs.settings.keys():
            # verbosity and branchVerbosity already have command line options in the default parser
            # adding them again would result in an error from argparse.
            if settingName not in ["verbosity", "branchVerbosity"]:
                self.createOptionFromSetting(settingName)
        self.parser.add_argument(
            "--additional-files",
            nargs="*",
            default=[],
            help="Additional files from the source directory to copy into the target directory",
        )

    def invoke(self):
        # get the case title.
        from armi import cases

        inputCase = cases.Case(cs=self.cs)
        inputCase.clone(additionalFiles=self.args.additional_files)


class CloneArmiRunCommandInteractive(CloneArmiRunCommandBatch):
    """
    Interactively clone existing ARMI settings input, and associated files, to the current
    directory and modify it according to the supplied settings (on the command line).
    """

    name = "clone"
    settingsArgument = "required"


class CloneSuiteCommand(EntryPoint):
    """Clone existing ARMI cases as a new suite."""

    name = "clone-suite"

    def addOptions(self):
        for settingName in self.cs.environmentSettings:
            # verbosity and branchVerbosity already have command line options in the default parser
            # adding them again would result in an error from argparse.
            if settingName not in {"verbosity", "branchVerbosity"}:
                self.createOptionFromSetting(settingName)
        self.parser.add_argument(
            "--directory",
            "-d",
            type=str,
            default=os.getcwd(),
            help="Root directory to search for cases",
        )
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
            help="Just list the settings files found, don't actually submit them.",
        )

    def invoke(self):
        from armi import cases

        suite = cases.CaseSuite(self.cs)
        suite.discover(
            patterns=self.args.patterns,
            rootDir=self.args.directory,
            ignorePatterns=self.args.ignore,
        )
        suite.clone(oldRoot=self.args.directory)

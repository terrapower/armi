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
Search through a directory tree and modify ARMI settings in existing input
file(s). All valid settings may be used as keyword arguments.
"""

from armi import operators
from armi import runLog
from armi import settings
from armi.cli.entryPoint import EntryPoint
from armi.localization import exceptions


class ModifyCaseSettingsCommand(EntryPoint):
    """
    Search through a directory tree and modify ARMI settings in existing input file(s).
    All valid settings may be used as keyword arguments.

    Example
    -------
    $ python -m armi modify --numProcessors=3 *.xml
    """

    name = "modify"

    def addOptions(self):
        self.parser.add_argument(
            "--list-setting-files",
            "-l",
            action="store_true",
            help=(
                "Just list the settings files found and the proposed changes to make. "
                "Don't actually modify them."
            ),
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
        self.parser.add_argument(
            "patterns",
            type=str,
            nargs="*",
            default=["*.yaml"],
            help="Pattern(s) to use to find match file names (e.g. *.xml)",
        )
        for settingName in self.cs.settings.keys():
            # verbosity and branchVerbosity already have command line options in the default parser
            # adding them again would result in an error from argparse.
            if settingName not in ["verbosity", "branchVerbosity"]:
                # can't modify case title.., just use clone
                self.createOptionFromSetting(settingName, suppressHelp=True)

    def invoke(self):
        csInstances = settings.recursivelyLoadSettingsFiles(".", self.args.patterns)
        messages = (
            ("found", "listing")
            if self.args.list_setting_files
            else ("writing", "modifying")
        )
        for cs in csInstances:
            runLog.important("{} settings file {}".format(messages[0], cs.path))
            for settingName in self.settingsProvidedOnCommandLine:
                if cs[settingName] != self.cs[settingName]:
                    runLog.info(
                        "  changing `{}` from : {}\n"
                        "           {} to  -> {}".format(
                            settingName,
                            cs[settingName],
                            " " * (2 + len(settingName)),
                            self.cs[settingName],
                        )
                    )
                cs[settingName] = self.cs[settingName]
            # if we are only listing setting files, don't write them; it is OK that we modified them in memory :-)
            if not self.args.skip_inspection:
                inspector = operators.getOperatorClassFromSettings(cs).inspector(cs)
                inspector.run()
            if not self.args.list_setting_files:
                cs.writeToYamlFile(cs.path)
        runLog.important(
            "Finished {} {} settings files.".format(messages[1], len(csInstances))
        )

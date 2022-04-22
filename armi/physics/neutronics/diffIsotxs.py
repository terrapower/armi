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
This script is used to compare ISOTXS files.
"""
from armi import runLog
from armi.cli.entryPoint import EntryPoint


class CompareIsotxsLibraries(EntryPoint):
    """Compare two ISOTXS files"""

    name = "diff-isotxs"

    def addOptions(self):
        self.parser.add_argument(
            "reference",
            help="Reference ISOTXS for comparison. Percent differences are given in "
            "relation to this file.",
        )
        self.parser.add_argument(
            "comparisonFiles",
            nargs="+",
            help="ISOTXS files to compare to the reference",
        )
        self.parser.add_argument(
            "--nuclidesNames",
            "-n",
            nargs="+",
            help="For the interaction types identified only compare these nuclides.",
        )
        self.parser.add_argument(
            "--interactions",
            "-i",
            nargs="+",
            help="Compare the cross sections for these interactins and specified nuclides.",
        )
        self.parser.add_argument(
            "--fluxFile",
            "-f",
            help="Mcc3 file containing flux_bg (broad group flux) for single-group comparison.",
        )

    def invoke(self):
        from armi.nuclearDataIO import isotxs
        from armi.nuclearDataIO import xsLibraries

        runLog.setVerbosity(0)
        refIsotxs = isotxs.readBinary(self.args.reference)

        for fname in self.args.comparisonFiles:
            cmpIsotxs = isotxs.readBinary(fname)
            xsLibraries.compare(refIsotxs, cmpIsotxs)

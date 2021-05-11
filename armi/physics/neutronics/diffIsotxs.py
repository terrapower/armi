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
        # flux = read_broad_group_flux(refIsotxs.neutronEnergyGroups)
        for fname in self.args.comparisonFiles:
            cmpIsotxs = isotxs.readBinary(fname)
            xsLibraries.compare(refIsotxs, cmpIsotxs)  # , flux)


# This commented out code is being retained, because, at one point, it worked. It is valuable for reducing cross sections to
# 1-group condensed cross sections, which are easier to grasp.
# def read_broad_group_flux(energy_groups):
#     flux = []
#     try:
#         flux_pattern = re.compile(r'^\s*\d+ +(?P<energy>{0}) +{0} +(?P<flux>{0})'
#                                   .format(strings.SCIENTIFIC_PATTERN))
#         energy_iter = iter(energy_groups)
#         with open(args.flux_file) as flux_bg:
#             for line in flux_bg:
#                 mm = flux_pattern.match(line)
#                 if mm:
#                     flux.append(float(mm.group('flux')))
#                     energy = float(mm.group('energy'))
#                     iso_energy = next(energy_iter)
#                     ratio =  energy / iso_energy
#                     if 1.001 < ratio < 0.999:
#                          runLog.warning('Flux energy does not match ISOTXS (ratio:{}).\nISOTXS: {}\n{}: {}'
#                                         .format(ratio, iso_energy, args.flux_file, energy))
#                 if len(flux) == len(energy_groups):
#                     break
#         runLog.important('Read flux from {}:\n{}'
#                          .format(args.flux_file, flux))
#     except (TypeError, StopIteration):
#         pass
#     return numpy.array(flux)

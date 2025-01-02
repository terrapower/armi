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
"""Entry point for producing visualization files."""
import pathlib
import re
import sys

from armi import runLog
from armi.cli import entryPoint


class VisFileEntryPoint(entryPoint.EntryPoint):
    """Create visualization files from database files."""

    name = "vis-file"
    description = "Convert ARMI databases in to visualization files"

    _FORMAT_VTK = "vtk"
    _FORMAT_XDMF = "xdmf"
    _SUPPORTED_FORMATS = {_FORMAT_VTK, _FORMAT_XDMF}

    def __init__(self):
        entryPoint.EntryPoint.__init__(self)

    def addOptions(self):
        self.parser.add_argument("h5db", help="Input database path", type=str)
        self.parser.add_argument(
            "--output-name",
            "-o",
            help="Base name for output file(s). File extensions will be added as "
            "appropriate",
            type=str,
            default=None,
        )
        self.parser.add_argument(
            "--format",
            "-f",
            help="Output format. Supported formats: `vtk` and `xdmf`",
            default="vtk",
        )
        self.parser.add_argument(
            "--nodes",
            help="An optional list of time nodes to include. Should look like "
            "`(1,0)(1,1)(1,2)`, etc",
            type=str,
            default=None,
        )
        self.parser.add_argument(
            "--max-node",
            help="An optional (cycle,timeNode) tuple to specify the latest time step "
            "that should be included",
            type=str,
            default=None,
        )
        self.parser.add_argument(
            "--min-node",
            help="An optional (cycle,timeNode) tuple to specify the earliest time step "
            "that should be included",
            type=str,
            default=None,
        )

    def parse(self, args):
        """
        Process user input.

        Strings are parsed against some regular expressions and saved back to their
        original locations in the ``self.args`` namespace for later use.
        """
        entryPoint.EntryPoint.parse(self, args)

        cycleNodePattern = r"\((\d+),(\d+)\)"

        if self.args.nodes is not None:
            self.args.nodes = [
                (int(cycle), int(node))
                for cycle, node in re.findall(cycleNodePattern, self.args.nodes)
            ]

        if self.args.max_node is not None:
            nodes = re.findall(cycleNodePattern, self.args.max_node)
            if len(nodes) != 1:
                runLog.error(
                    "Bad --max-node: `{}`. Should look like (c,n).".format(
                        self.args.max_node
                    )
                )
                sys.exit(1)
            cycle, node = nodes[0]
            self.args.max_node = (int(cycle), int(node))

        if self.args.min_node is not None:
            nodes = re.findall(cycleNodePattern, self.args.min_node)
            if len(nodes) != 1:
                runLog.error(
                    "Bad --min-node: `{}`. Should look like (c,n).".format(
                        self.args.min_node
                    )
                )
                sys.exit(1)
            cycle, node = nodes[0]
            self.args.min_node = (int(cycle), int(node))

        if self.args.format not in self._SUPPORTED_FORMATS:
            runLog.error(
                "Requested format `{}` not among the supported options: {}".format(
                    self.args.format, self._SUPPORTED_FORMATS
                )
            )
            sys.exit(1)

        if self.args.output_name is None:
            # infer name from input
            inp = pathlib.Path(self.args.h5db)
            self.args.output_name = inp.stem

    def invoke(self):
        # late imports so that we dont have to import the world to do anything
        from armi.bookkeeping.db import databaseFactory
        from armi.bookkeeping.visualization import vtk, xdmf

        # a little baroque, but easy to extend with future formats
        formatMap = {
            self._FORMAT_VTK: vtk.VtkDumper,
            self._FORMAT_XDMF: xdmf.XdmfDumper,
        }

        dumper = formatMap[self.args.format](self.args.output_name, self.args.h5db)

        nodes = self.args.nodes
        db = databaseFactory(self.args.h5db, "r")
        with db:
            dbNodes = list(db.genTimeSteps())

            if nodes is not None and any(node not in dbNodes for node in nodes):
                raise RuntimeError(
                    "Some of the requested nodes are not in the source database.\n"
                    "Requested: {}\n"
                    "Present: {}".format(nodes, dbNodes)
                )

            with dumper:
                for cycle, node in dbNodes:
                    if nodes is not None and (cycle, node) not in nodes:
                        continue

                    if (
                        self.args.min_node is not None
                        and (cycle, node) < self.args.min_node
                    ):
                        continue

                    if (
                        self.args.max_node is not None
                        and (cycle, node) > self.args.max_node
                    ):
                        continue

                    runLog.info(
                        "Creating visualization file for cycle {}, time node {}...".format(
                            cycle, node
                        )
                    )
                    r = db.load(cycle, node)
                    dumper.dumpState(r)

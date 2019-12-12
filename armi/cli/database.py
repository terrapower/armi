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
Entry point into ARMI for manipulating output databases.
"""
import os
import re

import armi
from armi import runLog
from armi.cli.entryPoint import EntryPoint


class ConvertDB(EntryPoint):
    """Convert databases between different versions"""

    name = "convert-db"
    mode = armi.Mode.Batch

    def addOptions(self):
        self.parser.add_argument("h5db", help="Input database path", type=str)
        self.parser.add_argument(
            "--output-name", "-o", help="output database name", type=str, default=None
        )
        self.parser.add_argument(
            "--output-version",
            help=(
                "output database version. '2' or 'xtview' for older XTView database; '3' "
                "for new format."
            ),
            type=str,
            default=None,
        )

        self.parser.add_argument(
            "--nodes",
            help="An optional list of time nodes to migrate. Should look like "
            "`(1,0)(1,1)(1,2)`, etc",
            type=str,
            default=None,
        )

    def parse_args(self, args):
        EntryPoint.parse_args(self, args)
        if self.args.output_version is None:
            self.args.output_version = "3"
        elif self.args.output_version.lower() == "xtview":
            self.args.output_version = "2"

        if self.args.nodes is not None:
            self.args.nodes = [
                (int(cycle), int(node))
                for cycle, node in re.findall(r"\((\d+),(\d+)\)", self.args.nodes)
            ]

    def invoke(self):
        from armi.bookkeeping.db import convertDatabase

        if self.args.nodes is not None:
            runLog.info(
                "Converting the following time nodes: {}".format(self.args.nodes)
            )

        convertDatabase(
            self.args.h5db,
            outputDBName=self.args.output_name,
            outputVersion=self.args.output_version,
            nodes=self.args.nodes,
        )


class ExtractInputs(EntryPoint):
    """
    Recover input files from a database file.

    This can come in handy when input files need to be hand-migrated to facilitate
    loading or migration of the database file itself, or when attempting to re-run a
    slightly-modified version of a case.
    """

    name = "extract-inputs"
    mode = armi.Mode.Batch

    def addOptions(self):
        self.parser.add_argument("h5db", help="Path to input database", type=str)
        self.parser.add_argument(
            "--output-base",
            "-o",
            help="Base name for extracted inputs. If not provided, base name is "
            "implied from the database name.",
            type=str,
            default=None,
        )

    def parse_args(self, args):
        EntryPoint.parse_args(self, args)

        if self.args.output_base is None:
            self.args.output_base = os.path.splitext(self.args.h5db)[0]

    def invoke(self):
        from armi.bookkeeping.db.database3 import Database3

        db = Database3(self.args.h5db, "r")

        with db:
            settings, geom, bp = db.readInputsFromDB()

        settingsExt = ".yaml"
        if settings.lstrip()[0] == "<":
            settingsExt = ".xml"

        geomExt = ".xml" if geom.lstrip()[0] == "<" else ".yaml"

        settingsPath = self.args.output_base + "_settings" + settingsExt
        bpPath = self.args.output_base + "_blueprints.yaml"
        geomPath = self.args.output_base + "_geom" + geomExt

        bail = False
        for path in [settingsPath, bpPath, geomPath]:
            if os.path.exists(settingsPath):
                runLog.error("`{}` already exists. Aborting.".format(path))
                bail = True
        if bail:
            return -1

        for path, data, inp in [
            (settingsPath, settings, "settings"),
            (bpPath, bp, "blueprints"),
            (geomPath, geom, "geometry"),
        ]:
            runLog.info("Writing {} to `{}`".format(inp, path))
            if isinstance(data, bytes):
                data = data.decode()
            with open(path, "w") as f:
                f.write(data)


class InjectInputs(EntryPoint):
    """
    Insert new inputs into a database file, overwriting any existing inputs.

    This is useful for performing hand migrations of inputs to facilitate database
    migrations.
    """

    name = "inject-inputs"
    mode = armi.Mode.Batch

    def addOptions(self):
        self.parser.add_argument("h5db", help="Path to affected database", type=str)
        self.parser.add_argument(
            "--blueprints", help="Path to blueprints file", type=str, default=None
        )
        self.parser.add_argument(
            "--geom", help="Path to geometry file", type=str, default=None
        )
        self.parser.add_argument(
            "--settings", help="Path to settings file", type=str, default=None
        )

    def invoke(self):
        from armi.bookkeeping.db.database3 import Database3

        if all(
            li is None
            for li in [self.args.blueprints, self.args.geom, self.args.settings]
        ):
            runLog.error(
                "No settings, blueprints, or geometry files specified; "
                "nothing to do."
            )
            return -1

        bp = None
        settings = None
        geom = None

        if self.args.blueprints is not None:
            with open(self.args.blueprints, "r") as f:
                bp = f.read()

        if self.args.geom is not None:
            with open(self.args.geom, "r") as f:
                geom = f.read()

        if self.args.settings is not None:
            with open(self.args.settings, "r") as f:
                settings = f.read()

        db = Database3(self.args.h5db, "a")

        with db:
            # Not calling writeInputsToDb, since it makes too many assumptions about
            # where the inputs are coming from, and which ones we want to write.
            # Instead, we assume that we know where to store them, and do it ourselves.
            for data, key in [
                (bp, "blueprints"),
                (geom, "geomFile"),
                (settings, "settings"),
            ]:
                if data is not None:
                    del db.h5db["inputs/" + key]
                    db.h5db["inputs/" + key] = data

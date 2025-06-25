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

"""Entry point into ARMI for manipulating output databases."""

import os
import pathlib

from armi import context, runLog
from armi.cli.entryPoint import EntryPoint
from armi.utils.textProcessors import resolveMarkupInclusions


class ExtractInputs(EntryPoint):
    """
    Recover input files from a database file.

    This can come in handy when input files need to be hand-migrated to facilitate loading or
    migration of the database file itself, or when attempting to re-run a slightly-modified version
    of a case.
    """

    name = "extract-inputs"
    mode = context.Mode.BATCH

    def addOptions(self):
        self.parser.add_argument("h5db", help="Path to input database", type=str)
        self.parser.add_argument(
            "--output-base",
            "-o",
            help="Base name for extracted inputs. If not provided, base name is implied from the database name.",
            type=str,
            default=None,
        )

    def parse_args(self, args):
        EntryPoint.parse_args(self, args)

        if self.args.output_base is None:
            self.args.output_base = os.path.splitext(self.args.h5db)[0]

    def invoke(self):
        from armi.bookkeeping.db.database import Database

        db = Database(self.args.h5db, "r")

        with db:
            settings, bp = db.readInputsFromDB()

        settingsPath = self.args.output_base + "_settings.yaml"
        bpPath = self.args.output_base + "_blueprints.yaml"

        bail = False
        for path in [settingsPath, bpPath]:
            if os.path.exists(settingsPath):
                runLog.error("`{}` already exists. Aborting.".format(path))
                bail = True
        if bail:
            return

        for path, data, inp in [
            (settingsPath, settings, "settings"),
            (bpPath, bp, "blueprints"),
        ]:
            if path is None:
                continue
            runLog.info("Writing {} to `{}`".format(inp, path))
            if isinstance(data, bytes):
                data = data.decode()
            with open(path, "w") as f:
                f.write(data)


class InjectInputs(EntryPoint):
    """
    Insert new inputs into a database file, overwriting any existing inputs.

    This is useful for performing hand migrations of inputs to facilitate database migrations.
    """

    name = "inject-inputs"
    mode = context.Mode.BATCH

    def addOptions(self):
        self.parser.add_argument("h5db", help="Path to affected database", type=str)
        self.parser.add_argument("--blueprints", help="Path to blueprints file", type=str, default=None)
        self.parser.add_argument("--settings", help="Path to settings file", type=str, default=None)

    def invoke(self):
        from armi.bookkeeping.db.database import Database

        if all(li is None for li in [self.args.blueprints, self.args.settings]):
            runLog.error("No settings, blueprints, or geometry files specified; nothing to do.")
            return

        bp = None
        settings = None

        if self.args.blueprints is not None:
            bp = resolveMarkupInclusions(pathlib.Path(self.args.blueprints)).read()

        if self.args.settings is not None:
            settings = resolveMarkupInclusions(pathlib.Path(self.args.settings)).read()

        db = Database(self.args.h5db, "a")

        with db:
            # Not calling writeInputsToDb, since it makes too many assumptions about where the
            # inputs are coming from, and which ones we want to write. Instead, we assume that we
            # know where to store them, and do it ourselves.
            for data, key in [
                (bp, "blueprints"),
                (settings, "settings"),
            ]:
                if data is not None:
                    dSetName = "inputs/" + key
                    if dSetName in db.h5db:
                        del db.h5db[dSetName]
                    db.h5db[dSetName] = data

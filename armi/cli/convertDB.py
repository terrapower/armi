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
Entry point into ARMI to migrate inputs to the latest version of ARMI.
"""

import armi
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

    def parse_args(self, args):
        EntryPoint.parse_args(self, args)
        if self.args.output_version is None:
            self.args.output_version = "3"
        elif self.args.output_version.lower() == "xtview":
            self.args.output_version = "2"

    def invoke(self):
        from armi.bookkeeping.db import convertDatabase

        convertDatabase(self.args.h5db, self.args.output_name, self.args.output_version)

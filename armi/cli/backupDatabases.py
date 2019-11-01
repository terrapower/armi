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

"""Script to back up the in-use test databases."""
import armi
from armi import settings
from armi.bookkeeping import db
from armi.utils import directoryChangers
from armi.cli.entryPoint import EntryPoint


class BackUpInUseTestDabases(EntryPoint):
    """Back up the test databases."""

    name = "back-up-db"
    settingsArgument = "optional"

    def invoke(self):
        from armi.inUseTestCases import inUseTestSuite

        suite = inUseTestSuite.InUseTestSuite(self.cs)
        suite.populate()
        suite.backUpDatabases()


class CopyDB(EntryPoint):
    """Copy the contents of one ARMI database to another."""

    name = "copy-db"

    def addOptions(self):
        parser = self.parser

        parser.add_argument(
            "csPath",
            action="store",
            help="The path to the input CS file to construct the data source's reactor.",
        )
        parser.add_argument(
            "srcDB", action="store", help="The database to be used the data source."
        )
        parser.add_argument(
            "tarDB", action="store", help="The database to receive the data."
        )

    def invoke(self):
        srcDB = db.databaseFactory(
            dbName=self.args.srcDB, permission=db.Permissions.READ_ONLY_FME
        )
        tarDB = db.databaseFactory(
            dbName=self.args.tarDB, permission=db.Permissions.CREATE_FILE_TIE
        )

        cs = settings.Settings(fName=self.args.csPath)

        with directoryChangers.DirectoryChanger(cs.inputDirectory):
            o = armi.init(cs=cs)
            db.copyDatabase(o.r, srcDB, tarDB)

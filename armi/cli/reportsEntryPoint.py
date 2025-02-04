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
import webbrowser

from armi import getPluginManagerOrFail
from armi.bookkeeping.db import databaseFactory
from armi.bookkeeping.report import newReports as reports
from armi.cli import entryPoint
from armi.reactor import blueprints, reactors
from armi.utils.directoryChangers import ForcedCreationDirectoryChanger


class ReportsEntryPoint(entryPoint.EntryPoint):
    """Create a report from a database file."""

    name = "report"
    settingsArgument = "optional"
    description = "Convert ARMI databases into a report"
    report_out_dir = "reportsOutputFiles"

    def __init__(self):
        entryPoint.EntryPoint.__init__(self)

    def addOptions(self):
        self.parser.add_argument("-h5db", help="Input database path", type=str)
        self.parser.add_argument(
            "--bp", help="Input blueprint (optional)", type=str, default=None
        )
        self.parser.add_argument(
            "--settings", help="Settings File (optional)", type=str, default=None
        )
        self.parser.add_argument(
            "--output-name",
            "-o",
            help="Base name for output file(s). File extensions will be added as appropriate",
            type=str,
            default=None,
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
            help="An optional (cycle,timeNode) tuple to specify the latest time step that should "
            "be included",
            type=str,
            default=None,
        )
        self.parser.add_argument(
            "--min-node",
            help="An optional (cycle,timeNode) tuple to specify the earliest time step that should "
            "be included",
            type=str,
            default=None,
        )

        self.parser.add_argument(
            "--view",
            help="An optional argument to allow automatic pop up of the webpage",
            action="store_true",
            default=False,
        )

    def invoke(self):
        if self.args.h5db is None:
            # Just do BOL stuff, no database is given.
            site = createReportFromSettings(self.cs)
            if self.args.view:
                webbrowser.open(site)
        else:
            self._cleanArgs()
            nodes = self.args.nodes
            blueprint = self.args.bp

            report = reports.ReportContent("Overview")
            pm = getPluginManagerOrFail()
            db = databaseFactory(self.args.h5db, "r")

            with db:
                with ForcedCreationDirectoryChanger(self.report_out_dir):
                    dbNodes = list(db.genTimeSteps())
                    cs = db.loadCS()
                    if self.args.bp is None:
                        blueprint = db.loadBlueprints()
                    r = reactors.factory(cs, blueprint)
                    report.title = r.name
                    _pc = getPluginManagerOrFail().hook.getReportContents(
                        r=r,
                        cs=cs,
                        report=report,
                        stage=reports.ReportStage.Begin,
                        blueprint=blueprint,
                    )
                    stage = reports.ReportStage.Standard
                    for cycle, node in dbNodes:
                        # check to see if we should skip this time node
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

                        r = db.load(cycle, node)
                        cs = db.loadCS()

                        _pluginContent = pm.hook.getReportContents(
                            r=r, cs=cs, report=report, stage=stage, blueprint=blueprint
                        )

                    stage = reports.ReportStage.End
                    _pluginContent = pm.hook.getReportContents(
                        r=r, cs=cs, report=report, stage=stage, blueprint=blueprint
                    )
                    site = report.writeReports()
                    if self.args.view:
                        webbrowser.open(site)

    @staticmethod
    def toTwoTuple(strInput):
        """Convert a string to a two-tuple of integers.

        Parameters
        ----------
        strInput : str
            Representing a simple two-tuple of integers: '(1,3)'.

        Returns
        -------
        tuple
            A tuple of two integers.
        """
        s = strInput.replace("(", "").replace(")", "").split(",")
        return tuple([int(s[0]), int(s[1])])

    def _cleanArgs(self):
        """The string arguments passed to this entry point, on the command line, need to be
        converted to integers.
        """
        if self.args.min_node is not None and type(self.args.min_node) is str:
            self.args.min_node = ReportsEntryPoint.toTwoTuple(self.args.min_node)

        if self.args.max_node is not None and type(self.args.max_node) is str:
            self.args.max_node = ReportsEntryPoint.toTwoTuple(self.args.max_node)

        if self.args.nodes is not None and type(self.args.nodes) is str:
            self.args.nodes = [
                ReportsEntryPoint.toTwoTuple(n) for n in self.args.nodes.split(")")[:-1]
            ]


def createReportFromSettings(cs):
    """
    Create BEGINNING reports, given a settings file.

    This will construct a reactor from the given settings and create BOL reports for that
    reactor/settings.

    Parameters
    ----------
    cs : Settings
        A standard ARMI Settings object, to define a run.

    Returns
    -------
    str
        A string representing the HTML for a web page.
    """
    if cs is None:
        raise RuntimeError(
            "No Settings with Blueprint or Database, cannot gerenate a report"
        )

    blueprint = blueprints.loadFromCs(cs)
    r = reactors.factory(cs, blueprint)
    report = reports.ReportContent("Overview")
    pm = getPluginManagerOrFail()
    report.title = r.name

    with ForcedCreationDirectoryChanger("{}-reports".format(cs.caseTitle)):
        _ = pm.hook.getReportContents(
            r=r,
            cs=cs,
            report=report,
            stage=reports.ReportStage.Begin,
            blueprint=blueprint,
        )
        site = report.writeReports()

    return site

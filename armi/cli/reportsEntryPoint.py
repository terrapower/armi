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
import pathlib
import webbrowser

from armi import getPluginManagerOrFail
from armi import settings
from armi.bookkeeping import newReports as reports
from armi.bookkeeping.db import databaseFactory
from armi.cli import entryPoint
from armi.reactor import blueprints
from armi.reactor import reactors
from armi.utils import directoryChangers
from armi.utils import runLog


class ReportsEntryPoint(entryPoint.EntryPoint):
    """Create report from database files."""

    name = "report"
    settingsArgument = "optional"
    description = "Convert ARMI databases into a report"

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
            help="Base name for output file(s). File extensions will be added as "
            "appropriate",
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

        self.parser.add_argument(
            "--view",
            help="An optional argument to allow automatic pop up of the webpage",
            action="store_true",
            default=False,
        )
        # self.createOptionFromSetting("imperialunits", "-i")

    def invoke(self):

        nodes = self.args.nodes

        if self.args.h5db is None:
            # Just do begining stuff, no database is given...
            if self.cs is not None:
                site = createReportFromSettings(cs)
                if self.args.view:
                    webbrowser.open(site)
            else:
                raise RuntimeError(
                    "No Settings with Blueprint or Database, cannot gerenate a report"
                )

        else:
            report = reports.ReportContent("Overview")
            pm = getPluginManagerOrFail()
            db = databaseFactory(self.args.h5db, "r")
            if self.args.bp is not None:
                blueprint = self.args.bp

            with db:
                with directoryChangers.ForcedCreationDirectoryChanger(
                    "reportsOutputFiles"
                ):

                    dbNodes = list(db.genTimeSteps())
                    cs = db.loadCS()
                    if self.args.bp is None:
                        blueprint = db.loadBlueprints()
                    r = reactors.factory(cs, blueprint)
                    report.title = r.name
                    pluginContent = getPluginManagerOrFail().hook.getReportContents(
                        r=r,
                        cs=cs,
                        report=report,
                        stage=reports.ReportStage.Begin,
                        blueprint=blueprint,
                    )
                    stage = reports.ReportStage.Standard
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

                        r = db.load(cycle, node)
                        cs = db.loadCS()

                        pluginContent = pm.hook.getReportContents(
                            r=r, cs=cs, report=report, stage=stage, blueprint=blueprint
                        )
                    stage = reports.ReportStage.End
                    pluginContent = pm.hook.getReportContents(
                        r=r, cs=cs, report=report, stage=stage, blueprint=blueprint
                    )
                    site = report.writeReports()
                    if self.args.view:
                        webbrowser.open(site)


def createReportFromSettings(cs):
    """
    Create BEGINNING reports, given a settings file.

    This will construct a reactor from the given settings and create BOL reports for
    that reactor/settings.
    """
    # not sure if this is necessary, but need to investigate more to understand possible
    # side-effects before removing. Probably better to get rid of all uses of
    # getMasterCs(), then we can remove all setMasterCs() calls without worrying.
    settings.setMasterCs(cs)

    blueprint = blueprints.loadFromCs(cs)
    r = reactors.factory(cs, blueprint)
    report = reports.ReportContent("Overview")
    pm = getPluginManagerOrFail()
    report.title = r.name

    with directoryChangers.ForcedCreationDirectoryChanger(
        "{}-reports".format(cs.caseTitle)
    ):
        _ = pm.hook.getReportContents(
            r=r,
            cs=cs,
            report=report,
            stage=reports.ReportStage.Begin,
            blueprint=blueprint,
        )
        site = report.writeReports()

    return site

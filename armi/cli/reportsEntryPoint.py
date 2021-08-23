from enum import Enum
from enum import auto
import webbrowser

import armi
from armi.cli import entryPoint
from armi.reactor.reactors import factory
from armi.utils import runLog


class ReportsEntryPoint(entryPoint.EntryPoint):
    """
    Create report from database files.
    """

    name = "report"
    settingsArgument = "optional"
    description = "Convert ARMI databases into a report"

    def __init__(self):
        entryPoint.EntryPoint.__init__(self)

    def addOptions(self):
        self.parser.add_argument("-h5db", help="Input database path", type=str)
        self.parser.add_argument(
            "-bp", help="Input blueprint (optional)", type=str, default=None
        )
        self.parser.add_argument(
            "-settings", help="Settings File (optional", type=str, default=None
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
        from armi import settings
        from armi.reactor import blueprints
        from armi.bookkeeping.newReports import ReportContent
        from armi.bookkeeping.db import databaseFactory
        from armi.utils import directoryChangers

        nodes = self.args.nodes
        report = ReportContent("Overview")
        app = armi.getApp()
        if app is None:
            raise RuntimeError("NEED APP!")
        pm = app._pm

        if self.args.h5db is None:
            # Just do begining stuff, no database is given...
            if self.cs is not None:
                cs = self.cs
                settings.setMasterCs(self.cs)
                blueprint = blueprints.loadFromCs(cs)
                r = factory(cs, blueprint)
                report.title = r.name
            else:
                raise RuntimeError(
                    "No Settings with Blueprint or Database, cannot gerenate a report"
                )

            with directoryChangers.ForcedCreationDirectoryChanger("reportsOutputFiles"):
                _ = pm.hook.getReportContents(
                    r=r,
                    cs=cs,
                    report=report,
                    stage=ReportStage.Begin,
                    blueprint=blueprint,
                )
                site = report.writeReports()
                if self.args.view:
                    webbrowser.open(site)

        else:
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
                    r = factory(cs, blueprint)
                    report.title = r.name
                    pluginContent = (
                        armi.getPluginManagerOrFail().hook.getReportContents(
                            r=r,
                            cs=cs,
                            report=report,
                            stage=ReportStage.Begin,
                            blueprint=blueprint,
                        )
                    )
                    stage = ReportStage.Standard
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
                    stage = ReportStage.End
                    pluginContent = pm.hook.getReportContents(
                        r=r, cs=cs, report=report, stage=stage, blueprint=blueprint
                    )
                    site = report.writeReports()
                    if self.args.view:
                        webbrowser.open(site)


class ReportStage(Enum):
    Begin = auto()
    Standard = auto()
    End = auto()

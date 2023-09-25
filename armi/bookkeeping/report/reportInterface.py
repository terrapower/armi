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
This interface serves the reporting needs of ARMI.

If there is any information that a user desires to show in PDF form to
others this is the place to do it.
"""
import re

from armi import interfaces
from armi import runLog
from armi.bookkeeping import report
from armi.bookkeeping.report import reportingUtils
from armi.physics import neutronics
from armi.physics.neutronics.settings import CONF_NEUTRONICS_TYPE
from armi.reactor.flags import Flags
from armi.utils import directoryChangers
from armi.utils import reportPlotting

ORDER = interfaces.STACK_ORDER.BEFORE + interfaces.STACK_ORDER.BOOKKEEPING


def describeInterfaces(cs):
    """Function for exposing interface(s) to other code."""
    if cs["genReports"]:
        return (ReportInterface, {})
    return None


class ReportInterface(interfaces.Interface):
    """An interface to manage the use of the report system."""

    name = "report"

    reports = set()

    def __init__(self, r, cs):
        interfaces.Interface.__init__(self, r, cs)
        self.fuelCycleSummary = {"bocFissile": 0.0}

    def distributable(self):
        """Disables distributing of this report by broadcast MPI."""
        return self.Distribute.SKIP

    def interactBOL(self):
        interfaces.Interface.interactBOL(self)
        runLog.important("Beginning of BOL Reports")
        reportingUtils.makeCoreAndAssemblyMaps(self.r, self.cs)
        reportingUtils.writeAssemblyMassSummary(self.r)

        if self.cs["summarizeAssemDesign"]:
            reportingUtils.summarizePinDesign(self.r.core)

        runLog.info(report.ALL[report.RUN_META])

    def interactEveryNode(self, cycle, node):
        if self.cs["assemPowSummary"]:
            reportingUtils.summarizePower(self.r.core)

        self.r.core.calcBlockMaxes()
        reportingUtils.summarizePowerPeaking(self.r.core)

        runLog.important("Cycle {}, node {} Summary: ".format(cycle, node))
        runLog.important(
            "  time= {0:8.2f} years, keff= {1:.12f} maxPD= {2:-8.2f} MW/m^2, "
            "maxBuI= {3:-8.4f} maxBuF= {4:8.4f}".format(
                self.r.p.time,
                self.r.core.p.keff,
                self.r.core.p.maxPD,
                self.r.core.p.maxBuI,
                self.r.core.p.maxBuF,
            )
        )

        if self.cs["plots"]:
            adjoint = self.cs[CONF_NEUTRONICS_TYPE] == neutronics.ADJREAL_CALC
            figName = (
                self.cs.caseTitle
                + "_{0}_{1}".format(cycle, node)
                + ".mgFlux."
                + self.cs["outputFileExtension"]
            )

            if self.r.core.getFirstBlock(Flags.FUEL).p.mgFlux is not None:
                from armi.reactor import blocks

                blocks.Block.plotFlux(
                    self.r.core, fName=figName, peak=True, adjoint=adjoint
                )
            else:
                runLog.warning("No mgFlux to plot in reports")

    def interactBOC(self, cycle=None):
        self.fuelCycleSummary["bocFissile"] = self.r.core.getTotalBlockParam("kgFis")

    def interactEOC(self, cycle=None):
        reportingUtils.writeCycleSummary(self.r.core)
        runLog.info(self.o.timer.report(inclusion_cutoff=0.001))

    def generateDesignReport(self, generateFullCoreMap, showBlockAxMesh):
        reportingUtils.makeCoreDesignReport(self.r.core, self.cs)
        reportingUtils.makeCoreAndAssemblyMaps(
            self.r, self.cs, generateFullCoreMap, showBlockAxMesh
        )
        reportingUtils.makeBlockDesignReport(self.r)

    def interactEOL(self):
        """Adds the data to the report, and generates it."""
        b = self.r.core.getFirstBlock(Flags.FUEL)
        b.setAreaFractionsReport()

        dbi = self.o.getInterface("database")
        buGroups = self.cs["buGroups"]
        history = self.o.getInterface("history")
        reportPlotting.plotReactorPerformance(
            self.r,
            dbi,
            buGroups,
            extension=self.cs["outputFileExtension"],
            history=history,
        )

        reportingUtils.setNeutronBalancesReport(self.r.core)
        self.writeRunSummary()
        self.o.timer.stopAll()  # consider the run done
        runLog.info(self.o.timer.report(inclusion_cutoff=0.001, total_time=True))
        _timelinePlot = self.o.timer.timeline(
            self.cs.caseTitle, self.cs["timelineInclusionCutoff"], total_time=True
        )
        runLog.debug("Generating report HTML.")
        self.writeReports()
        runLog.debug("Report HTML generated successfully.")
        runLog.info(self.printReports())

    # --------------------------------------------
    #        Report Interface Specific
    # --------------------------------------------
    def printReports(self):
        str_ = ""
        for report_ in self.reports:
            str_ += re.sub("\n", "\n\t", "{}".format(report_))

        return (
            "---------- REPORTS BEGIN ----------\n"
            + str_
            + "\n----------- REPORTS END -----------"
        )

    def writeReports(self):
        """Renders each report into a document for viewing."""
        with directoryChangers.ForcedCreationDirectoryChanger("reports"):
            for report_ in self.reports:
                report_.writeHTML()

    # --------------------------------------------
    #        Misc Summaries
    # --------------------------------------------
    def writeRunSummary(self):
        """Make a summary of the run."""
        # spent fuel pool report
        if self.r.sfp is not None:
            self.r.sfp.report()
            self.r.sfp.count()

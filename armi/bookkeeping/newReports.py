import re
import webbrowser
import collections
import shutil
import os
from enum import Enum
from enum import auto
from armi import runLog
from armi import interfaces
from armi.utils import directoryChangers
from armi.bookkeeping import report
from armi.bookkeeping.newReportUtils import valueVsTime, tableToHTML, tableOfContents
from armi.physics import neutronics
from armi.reactor.flags import Flags

from htmltree import *


class ReportContent:
    """Holds the report contents"""

    listOrder = []

    def __init__(self, title, description):
        self.description = description
        self.title = title
        self.sections = collections.OrderedDict()

    def writeReports(self):
        """Renders each report into a document for viewing."""
        body = Body()
        head = Head()
        head.C.append(Link(rel="stylesheet", href="styles.css"))
        reorderSections = dict_reorder(self.sections)
        divMain = Div(id="container")
        # div.C.append(Header().C.append(H1("Report System")))
        header = Div(H1("Report System", _class="heading", id="myid"), id="heading")
        divMain.C.append(header)
        div = Div(id="reportContent")
        div.C.append(H4("Report Generated for : " + self.title))
        body.C.append(tableOfContents(reorderSections))
        for group in reorderSections:
            # add it to the body
            div.C.append(H1(group, id=group))
            # but do we want to be able to check sections[group].parent
            # and put all these parent groups together for ordering?
            for subgroup in reorderSections[group]:
                div.C.append(H2(subgroup, id=subgroup))
                if type(self.sections[group][subgroup]) == TableSection:
                    # turn it into a table...
                    tableContent = self.sections[group][subgroup]
                    table = tableToHTML(tableContent)
                    div.C.append(table)
                elif type(self.sections[group][subgroup]) == TimeSeries:
                    # make it a graph.
                    timePoints = self.sections[group][subgroup]
                    graph = valueVsTime(timePoints, ymin=None)
                    div.C.append(graph)
                else:
                    fig = Figure()
                    fig.C.append(
                        Img(
                            src=self.sections[group][subgroup].imagePath,
                            alt=self.sections[group][subgroup].title,
                        )
                    )
                    fig.C.append(Figcaption(self.sections[group][subgroup].caption))
                    div.C.append(fig)
        divMain.C.append(div)
        body.C.append(divMain)
        doc = Html(head, body)

        # Copy css file to the correct folder containing the reportContent.html
        shutil.copy(
            os.path.abspath(
                os.path.join(os.path.abspath(__file__), os.pardir, "styles.css")
            ),
            "styles.css",
        )
        fileurl = doc.renderToFile("ReportContent.html", 0)

        webbrowser.open(fileurl)

    def addContents(self, contents):
        """contents is itself a ReportContent object"""

        """for key in contents.sections:
            if key not in self.sections:
                # They don't have the same section already
                self.sections[key] = contents.sections[key]
            else:
                self.sections[key] = self.sections[key]"""


def dict_reorder(item):
    # return {k: v for k, v in sorted(item.items())}
    return item


class Sections:
    def __init__(self, title, caption=""):
        self.title = title
        self.caption = caption


class ImageSection(Sections):
    """For Images within the report (such as Hexplots premade and not time dependent)
    (For time dependent images see TimeSeries)

    Parameters
    ----------
    title
    caption
    imagePath: .png or .img image name to reference later

    """

    def __init__(
        self,
        title,
        caption,
        imagePath,
        header=None,
    ):
        Sections.__init__(self, title, caption=caption)
        self.header = header
        self.imagePath = imagePath
        # rows will be a list of lists


class TableSection(Sections):
    """For Table Objects that are then later converted to htmltree tables

    Parameters
    ----------
    title: String
        for Table Title

    caption: String
        for Table Caption

    header: List
        a list of column headings, optional,
        for when tables have columns with headings.

    """

    def __init__(
        self,
        title,
        caption="",
        header=None,
    ):
        Sections.__init__(self, title, caption=caption)
        self.header = header
        self.rows = []
        # rows will be a list of lists

    def addRow(self, row):
        self.rows.append(row)


class TimeSeries(Sections):
    """Handles storing new values that will come together to make a graph later

    Parameters
    ----------
    title: String
        Title for eventual graph

    caption: String
        Caption for eventual graph

    labels: List
        list of stored labels where length = number of lines within graph

    yaxis: String
        label for the y-axis

    key: String
        identifier for the resulting image file name (i.e. linegraph.[key].img,
        where key may be peakDPA or Keff)

    """

    def __init__(self, title, caption, labels, yaxis, key):
        Sections.__init__(self, title, caption)
        self.times = []
        self.labels = labels
        self.datapoints = [[] for i in range(len(labels))]
        self.uncertainties = [[] for i in range(len(labels))]
        self.yaxis = yaxis
        self.key = key
        # self.times.append(time)

    # data and uncertainty both lists of values corresponding to different Data Points
    def add(self, time, data, uncertainty):
        """
        Adds data point (with associated time and uncertainty) to a TimeSeries object for
        later plotting.

        Parameters
        ----------

        time : a single time point
        data : a list with length = to number of lines that will be present on the graph
            (must be equal to the length of other data objects previously added to this TimeSeries object)
        uncertainty: list with uncertainy values for each line. Can be all zeroes.

        """
        self.times.append(time)
        index = 0
        for plotLine in data:
            self.datapoints[index].append(plotLine)
            index = index + 1
        index = 0
        for error in uncertainty:
            self.uncertainties[index].append(error)
            index = index + 1

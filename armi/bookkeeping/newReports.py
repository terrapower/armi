import re
import webbrowser
import collections
import shutil
import os


import htmltree
from htmltree import Table as HtmlTable


class ReportContent:
    """Holds the report contents"""

    listOrder = []

    def __init__(self, title, description):
        self.description = description
        self.title = title
        self.sections = collections.OrderedDict()

    def writeReports(self):
        """Renders each report into a document for viewing."""

        from armi.bookkeeping.newReportUtils import tableOfContents

        body = htmltree.Body()
        head = htmltree.Head()
        head.C.append(htmltree.Link(rel="stylesheet", href="styles.css"))

        divMain = htmltree.Div(id="container")
        header = htmltree.Div(id="heading")
        header.C.append(
            htmltree.Img(
                src="https://terrapower.github.io/armi/_images/armi-logo.png",
                alt="logo",
                _class="heading",
            )
        )
        header.C.append(htmltree.H1("Report System", _class="heading", id="titleFont"))

        divMain.C.append(header)
        div = htmltree.Div(id="reportContent")
        div.C.append(htmltree.H4("Report Generated for : " + self.title))
        body.C.append(tableOfContents(self.sections))
        for group in self.sections:
            div.C.append(htmltree.H1(group, id=group))
            for subgroup in self.sections[group]:
                div.C.append(htmltree.H2(subgroup, id=subgroup))
                if type(self.sections[group][subgroup]) == list:
                    for element in self.sections[group][subgroup]:
                        div.C.append(htmltree.H2(element.title, id=element.title))
                        item = element.toHtml()
                        div.C.append(item)
                else:
                    fig = self.sections[group][subgroup].toHtml()
                    div.C.append(fig)
        divMain.C.append(div)
        body.C.append(divMain)
        body.C.append(htmltree.Script(src="report.js"))

        doc = htmltree.Html(head, body)

        # Copy css file to the correct folder containing the reportContent.html
        shutil.copy(
            os.path.abspath(
                os.path.join(os.path.abspath(__file__), os.pardir, "styles.css")
            ),
            "styles.css",
        )
        shutil.copy(
            os.path.abspath(
                os.path.join(os.path.abspath(__file__), os.pardir, "report.js")
            ),
            "report.js",
        )
        fileurl = doc.renderToFile("ReportContent.html", 0)

        webbrowser.open(fileurl)

    def addSubsection(self, section, subsection, item):
        """Add a subsection to contents within a report

        Parameters
        ----------
        section: String
            Name of section to add Subsection to.
        subsection: String
            Name of subsection to add item to
        item: Table, TimeSeries, Image or List
            content to add into the html report later

        """
        self.ensureExistance(section)

        self.sections[section][subsection] = item

    def accessSubsection(self, section, subsection):
        """Access a subsection of the report for additions

        Parameters
        ----------
        section: String
            Name of section to add Subsection to.
        subsection: String
            Name of subsection to add item to
        """
        self.ensureExistance(section)

        return self.sections[section][subsection]

    def ensureExistance(self, section):
        """Adds a section to the report if it is not present

        Parameters
        ----------
        section: String
            Section name to add or ensure existance of

        Returns
        -------
        Dictionary for the section that was desired."""

        if section not in self.sections:
            self.sections[section] = dict()
        return self.sections[section]


class Sections:
    def __init__(self, title, caption=""):
        self.title = title
        self.caption = caption

    def toHtml(self):
        """Renders the section to a htmltree element for inserting into HTML document tree"""
        raise NotImplementedError


class Image(Sections):
    """For Images within the report (such as Hexplots premade and not time dependent)
    (For time dependent images see TimeSeries)

    Parameters
    ----------
    title: String
    caption: String
    imagePath: String
        .png or .img image name to reference later


    """

    def __init__(
        self,
        title,
        caption,
        imagePath,
    ):
        Sections.__init__(self, title, caption=caption)
        self.imagePath = imagePath

    def toHtml(self):
        from armi.bookkeeping.newReportUtils import encode64

        figure = htmltree.Figure()
        self.imagePath = encode64(os.path.abspath(self.imagePath))
        figure.C.append(
            htmltree.Img(
                src=self.imagePath,
                alt="{}_image".format(self.title),
            )
        )
        figure.C.append(htmltree.Figcaption(self.caption))
        return figure


class Table(Sections):
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

    def toHtml(self):
        """Converts a TableSection object into a html table representation htmltree element

        Parameters
        ----------
        tableRows: newReports.TableSection
            Object that holds information to be made into a table.
        """

        table = htmltree.Table()
        if self.header is not None:
            titleRow = htmltree.Tr()
            for heading in self.header:
                titleRow.C.append(htmltree.Th(heading))
            table.C.append(titleRow)
        for row in self.rows:
            htmlRow = htmltree.Tr()
            for element in row:
                htmlRow.C.append(htmltree.Td(element))
            table.C.append(htmlRow)
        return table


class TimeSeries(Sections):
    """Handles storing new data point values for use in graphing later.

    Parameters
    ----------
    title: String
        Title for eventual graph

    caption: String
        Reactor Name for eventual graph's title caption and file name

    labels: List
        list of stored labels where length = number of lines within graph

    yaxis: String
        label for the y-axis

    key: String
        identifier for the resulting image file name (i.e. rName.[key],
        where key may be peakDPA.img or Keff.png)
    """

    def __init__(self, title, caption, labels, yaxis, key):
        Sections.__init__(self, title, caption)
        self.times = []
        self.labels = labels
        self.dataDictionary = dict()
        # iniialize list of labels...
        for label in labels:
            self.dataDictionary[label] = []
        self.yaxis = yaxis
        self.key = key

    def add(self, lineToAddTo, time, data, uncertainty=None):
        """To add a point to our data collection.

        Parameters
        ----------

        lineToAddTo: String
            Label associated with the line we are adding ths point to
        time: float
            time value for the point
        data: float
            data value for the point
        uncertainty: float
            uncertainty associated with the point

        Notes
        -----
        Example Uses:

        1. Adding to a plot with a single line for k-effective...

        series = TimeSeries("Plot of K-effective", "plot", ["k-effective"], "k-eff", "keff.png")

        time = r.p.time                     # The current time node of the reactor.

        data = r.core.p.keff                # The parameter k-effective value at that time.

        uncertainty = r.core.p.keffUnc      # Since the parameter yields keff-uncertainty value at the current time.

        series.add("k-effective", time, data, uncertainty)   # Adds this point to be plotted later.

        2. Adding to a plot with multiple lines for fuel Burn-Up Plot.

        for a in r.core.getAssemblies(Flags.FUEL):
            if a.p.type not in labels:
                labels.append(a.p.type)
        maxValue = defaultdict(float)

        Collect Max Value Data

        for a in r.core.getAssemblies(Flags.FUEL):
            maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxPercentBu)

        Add this data for each assembly type (which will each be it's own line)

        for a in r.core.getAssemblies(Flags.FUEL):
            series.add(a.p.type, r.p.time, maxValue[a.p.type], None)

            (Adding a point for line labeled for this type of fuel,
            at this time, with the found maxValue, and no uncertainty...)

        """
        self.dataDictionary[lineToAddTo].append((time, data, uncertainty))

    def plot(self, ymin=None):
        """To plot a collected TimeSeries.

        Parameters
        ----------
        ext: String
            The extension to use on the graph.
        ymin: float
            The minimum y-value for the graph.
        """

        from operator import itemgetter
        import matplotlib.pyplot as plt

        plt.figure()
        lowestY = True
        for label in self.labels:

            points = self.dataDictionary[label]
            # want to sort points by first entry in tuple... (so by asscending time stamp...)
            points.sort(key=itemgetter(0))
            if ymin is None or not all([ymin > yi for yi in points]):
                lowestY = False
            lineY = []
            timepoints = []
            uncertainties = []
            for point in points:
                # Now points is sorted, collect times, and a data line...

                timepoints.append(point[0])
                lineY.append(point[1])
                uncertainties.append(point[2])
            self.dataDictionary[label] = (lineY, timepoints, uncertainties)
            if any(uncertainties):
                plt.errorbar(
                    timepoints,
                    lineY,
                    yerr=uncertainties,
                    label=label,
                )
            else:
                plt.plot(timepoints, lineY, ".-", label=label)
        plt.xlabel("Time (yr)")
        plt.legend()
        plt.ylabel(self.yaxis)
        plt.grid(color="0.70")
        plt.title(self.title + " for {0}".format(self.caption))
        if lowestY:
            # set ymin all values are greater than it and it exists.
            ax = plt.gca()
            ax.set_ylim(bottom=ymin)

        figName = self.caption + "." + self.key
        plt.savefig(figName)
        plt.close()
        return figName

    def toHtml(self):
        from armi.bookkeeping.newReportUtils import encode64

        figName = self.plot()
        return htmltree.Img(
            src=encode64(os.path.abspath(figName)), alt="{}_image".format(self.title)
        )

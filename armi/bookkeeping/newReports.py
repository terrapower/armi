import re
import webbrowser
import collections
import shutil
import os
import copy
from typing import DefaultDict, Union, Dict
from abc import ABC, abstractmethod

import htmltree
from htmltree import Table as HtmlTable


import armi.context


class ReportContent:
    """Holds the report contents"""

    def __init__(self, title):
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
        header.C.append(
            htmltree.H1(
                "{} Report".format(armi.context.APP_NAME.capitalize()),
                _class="heading",
                id="titleFont",
            )
        )

        divMain.C.append(header)
        div = htmltree.Div(id="reportContent")
        div.C.append(htmltree.H4("Report Generated for : " + self.title))
        body.C.append(tableOfContents(self.sections))
        for group in self.sections:
            div.C.append(htmltree.H1(group, id=group))
            for subgroup in self.sections[group].childContents:
                innerDiv = htmltree.Div()
                if isinstance(self.sections[group][subgroup], htmltree.HtmlElement):
                    fig = self.sections[group].childContents[subgroup].render()
                else:
                    fig = (
                        self.sections[group]
                        .childContents[subgroup]
                        .render(0, str(group) + str(subgroup))
                    )
                innerDiv.C.append(fig)
                div.C.append(innerDiv)
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

    def get(self, section, default=None):
        if section not in self.sections:
            self.sections[section] = default
        return self.sections[section]

    def __getitem__(self, key):
        if key not in self.sections:
            self.sections[key] = Section(key)

        return self.sections[key]

    def __setitem__(self, key, item):
        if key in self.sections:
            self.sections[key] = item


levelDict = collections.defaultdict(lambda: htmltree.H4())
levelDict[0] = htmltree.H1()
levelDict[1] = htmltree.H2()
levelDict[2] = htmltree.H3()
levelDict[3] = htmltree.H4()


class ReportNode(ABC):
    @abstractmethod
    def render(self, level, idPrefix):
        """Renders the section to a htmltree element for inserting into HTML document tree

        Parameters
        ----------
        level : int
            level of the nesting for this section, determines the size of the heading title for the Section
            (The higher the level, the smaller the title font-size). Ranges from H1 - H4 in html terms.

        idPrefix : String
            used for href/id referencing for the left hand side table of contents to be paired with the item
            that render() is called upon.

        Returns
        -------
        HtmlElement : an html representation of this Nodes report content. Appended into the report
            after it is rendered within writeReports().
        """
        raise NotImplementedError


class Section(ReportNode):
    """A grouping of objects within the report.
    These items can be either of type ReportNode (Table, Image, Section, TimeSeries)
    of, HtmlElements as defined by htmltree.

    """

    def __init__(self, title):
        self.title = title
        self.childContents: Dict[
            str, Union[Section, htmltree.HtmlElement, ReportNode]
        ] = collections.OrderedDict()

    def contains(self, item):
        return item in self.childContents

    def addChildElement(self, element, heading="", subheading=None):
        """Add an element to the group of Sections.

        Parameters
        ----------
        element: ReportNode, or an HtmlElement as defined by htmltree
            Item to be added as child to this Section.

        """
        # Have to check if that heading exists first...
        if heading in self.childContents:
            # Add it to existing section...
            currentStatus = self.childContents[heading]
            if isinstance(currentStatus, Section):
                currentStatus.childContents[subheading] = element
        else:
            self.childContents[element] = element

    def __contains__(self, key):
        return key in self.childContents

    def __iter__(self):
        return iter(self.childContents)

    def get(self, title, default=None):
        if title not in self.childContents:
            self.childContents[title] = default
        return self.childContents[title]

    def __getitem__(self, key):
        if key not in self.childContents:
            self.childContents[key] = Section(key)
        return self.childContents[key]

    def __setitem__(self, key, item):
        self.childContents[key] = item

    def items(self):
        return self.childContents.items()

    def __str__(self):
        return self.title

    def render(self, level, idPrefix="") -> htmltree.HtmlElement:
        """Renders a Section into the appropriate html representation

        Parameters
        ----------
        level : int
            level of the nesting for this section, determines the size of the heading title for the Section
            (The higher the level, the smaller the title font-size). Ranges from H1 - H4 in html terms.

        idPrefix : String
            used for href/id referencing for the left hand side table of contents to be paired with the item
            that render() is called upon.

        Returns
        -------
        HtmlElement : an html representation of this Nodes report content. Appended into the report
                    after it is rendered within writeReports().
        """
        itemsToAdd = []
        headingLevel = copy.deepcopy(levelDict[level])
        headingLevel.A.update({"id": "{}".format(idPrefix)})
        headingLevel.C.append(self.title)
        heading = headingLevel
        itemsToAdd.append(heading)
        for key in self.childContents:
            element = self.childContents[key]

            if isinstance(element, htmltree.HtmlElement):
                item = element.render()
            else:
                item = element.render(level + 1, idPrefix + str(key))

            itemsToAdd.append(item)

        return htmltree.Div(*itemsToAdd)


class Image(ReportNode):
    """For Images within the report (such as Hexplots premade and not time dependent)
    (For time dependent images see TimeSeries)

    Parameters
    ----------
    title: String
    caption: String
    imagePath: String
        .png or .img image name to reference later


    """

    def __init__(self, caption, imagePath, title=None):
        self.title = title
        self.imagePath = imagePath
        self.caption = caption

    def __str__(self):
        return self.caption

    def render(self, level, idPrefix="") -> htmltree.HtmlElement:
        """Wraps an image file into an html Img tag. (With caption included in the figure)"""
        from armi.bookkeeping.newReportUtils import encode64

        figure = htmltree.Figure()
        self.imagePath = encode64(os.path.abspath(self.imagePath))
        figure.C.append(
            htmltree.Img(
                src=self.imagePath, alt="{}_image".format(self.caption), id=idPrefix
            )
        )
        figure.C.append(htmltree.Figcaption(self.caption))
        return figure


class Table(ReportNode):
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
        self.title = title
        self.header = header
        self.rows = []
        self.caption = caption
        # rows will be a list of lists

    def addRow(self, row):
        self.rows.append(row)

    def __str__(self):
        return self.title

    def render(self, level, idPrefix="") -> htmltree.HtmlElement:
        """Converts a TableSection object into a html table representation htmltree element with
        header as heading if not None.
        """

        table = htmltree.Table()
        table.C.append(htmltree.Caption(self.title, id=idPrefix))
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
        table.C.append(
            htmltree.Caption(
                self.caption, style={"caption-side": "bottom", "font-size": "13"}
            )
        )
        return table


class TimeSeries(ReportNode):
    """Handles storing new data point values for use in graphing later.

    Parameters
    ----------
    title: String
        Title for eventual graph

    caption: String
        Eventual graph's title caption, "" default.

    labels: List
        list of stored labels where length = number of lines within graph

    yaxis: String
        label for the y-axis

    fName: String
        identifier for the resulting image file name (i.e. rName.[fName],
        where key may be peakDPA.img or Keff.png)

    rName: Reactor Name for graphs title and file name

    Example
    -------


    >>> series = TimeSeries("Plot of K-effective", "plot", ["k-effective"], "k-eff", "keff.png") # Adding to a plot with k-effective
    >>> time = r.p.time                     # The current time node of the reactor.
    >>> data = r.core.p.keff                # The parameter k-effective value at that time.
    >>> uncertainty = r.core.p.keffUnc      # Since the parameter yields keff-uncontrolled value at the current time.
    >>> series.add("k-effective", time, data, uncertainty)   # Adds this point to be plotted later.

    >>> # Adding to a plot with multiple lines for fuel Burn-Up Plot.
    >>> labels = [] # Start collecting labels for the lines to plot...
    >>> for a in r.core.getAssemblies(Flags.FUEL):
    >>>     if a.p.type not in labels:
    >>>         labels.append(a.p.type)
    >>> series = TimeSeries("Plot of Burn-Up", r.name, labels, "PeakBU", "bu.png")
    >>> maxValue = defaultdict(float)
    >>> for a in r.core.getAssemblies(Flags.FUEL):
    >>>     maxValue[a.p.type] = max(maxValue[a.p.type], a.p.maxPercentBu)
    >>> # Add this data for each assembly type (which will each be it's own line)
    >>> for a in r.core.getAssemblies(Flags.FUEL):
    >>>     series.add(a.p.type, r.p.time, maxValue[a.p.type], None)
    >>>    # (Adding a point for line labeled for this type of fuel,
    >>>    # at this time, with the found maxValue, and no uncertainty...)
    """

    def __init__(self, title, rName, labels, yaxis, fName, caption=""):
        self.title = title
        self.times = []
        self.labels = labels
        self.caption = caption
        self.dataDictionary = dict()
        # iniialize list of labels...
        for label in labels:
            self.dataDictionary[label] = []
        self.yaxis = yaxis
        self.fName = fName
        self.rName = rName

    def __str__(self):
        return self.title

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
        plt.title(self.title + " for {0}".format(self.rName))
        if lowestY:
            # set ymin all values are greater than it and it exists.
            ax = plt.gca()
            ax.set_ylim(bottom=ymin)

        figName = self.rName + "." + self.fName
        plt.savefig(figName)
        plt.close()
        return figName

    def render(self, level, idPrefix="") -> htmltree.HtmlElement:
        """Renders the Timeseries into a graph and places that Image into an html Img tag."""
        from armi.bookkeeping.newReportUtils import encode64

        figName = self.plot()
        return htmltree.Div(
            htmltree.Img(
                src=encode64(os.path.abspath(figName)),
                alt="{}_image".format(self.title),
                id=idPrefix,
            ),
            htmltree.P(self.caption),
        )

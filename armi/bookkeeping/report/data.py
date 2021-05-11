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

"""
import re
import copy
import collections

from armi import runLog
from armi.bookkeeping.report import html


# --------------------------------------------
#                REPORTS
# --------------------------------------------
class Report:
    """Storage for data separated out for a particular kind of user"""

    # stubs for "further stylization" in the report package init
    groupsOrderFirst = []
    componentWellGroups = []

    def __init__(self, title, description):
        self.title = title
        self.description = description
        self.groups = {}  # {Global Instance : Local Instance}

    @property
    def _groupRenderOrder(self):
        """Helper method to the rendering methods on this class for rendering order of contained info"""
        presentGroupsOrderFirst = [
            group for group in self.groupsOrderFirst if group in self.groups
        ]
        completeGroupOrder = presentGroupsOrderFirst + [
            group
            for group in self.groups.keys()
            if group not in presentGroupsOrderFirst
        ]
        specialsRemovedOrder = [
            group
            for group in completeGroupOrder
            if group not in self.componentWellGroups
        ]
        return specialsRemovedOrder

    def __str__(self):
        str_ = "\n{} - (REPORT) {}\n".format(self.title, self.description)
        for global_group in self.groups.values():
            str_ += re.sub(
                "\n", "\n\t", "{}".format(Group.__str__(global_group))
            )  # Don't use subclassed methods
        return str_

    def addToReport(self, group, name, value):
        """Inserts the datum into the correct group of the report"""
        if group not in self.groups:
            self.groups[group] = copy.deepcopy(group)
        self.groups[group][name] = value

    def __getitem__(self, group):
        try:
            return self.groups[group]
        except KeyError:
            runLog.warning(
                "Cannot locate group {} in report {}".format(group.title, self.title)
            )

    def writeHTML(self):
        """Renders this report as a standalone HTML file"""
        filename = "{}.html".format(self.title)
        runLog.debug("Writing HTML document {}.".format(filename))

        with html.HTMLFile(filename, "w") as f:
            html.writeStandardReportTemplate(f, self)

        runLog.info("HTML document {} written".format(filename))

    def writeGroupsHTML(self, f):
        """A helper method to the writeHTML method process

        Composes the group html content, intended for use in the midst of the html document generation

        """
        Image.count = 0  # reset the count for this report's figure enumeration

        # this implementation is hardcoded as 2 equal width layout
        # easy enough to change if so desired
        leftCol = []
        leftNumRows, leftNumImgs = 0, 0
        rightCol = []
        rightNumRows, rightNumImgs = 0, 0

        # roughly compose the groups into equalish length columns
        for global_group in self._groupRenderOrder:
            group = self.groups[global_group]
            if isinstance(group, Table):
                tableEstimateLength = len(group.data.keys())
                if leftNumRows <= rightNumRows:
                    leftCol.append(group)
                    leftNumRows += tableEstimateLength
                else:
                    rightCol.append(group)
                    rightNumRows += tableEstimateLength
            elif isinstance(group, Image):
                if leftNumImgs <= rightNumImgs:
                    leftCol.append(group)
                    leftNumImgs += len(group.data.keys())
                else:
                    rightCol.append(group)
                    rightNumImgs += len(group.data.keys())
            else:
                raise NotImplementedError(
                    "Please update this method for handling of new group classes."
                )

        # write html columns and place content inside
        with html.Div(f, attrs={"class": "row"}):
            with html.Div(f, attrs={"class": "col-md-6"}):
                for group in leftCol:
                    group.writeHTML(f)
            with html.Div(f, attrs={"class": "col-md-6"}):
                for group in rightCol:
                    group.writeHTML(f)

        # specially gathered groups constructed into own subsection
        presentComponentSpecials = [
            group for group in self.componentWellGroups if group in self.groups
        ]
        if any(presentComponentSpecials):
            with html.Div(f, attrs={"class": "well"}):
                for global_group in presentComponentSpecials:
                    self.groups[global_group].writeHTML(f)


# --------------------------------------------
#                GROUPS
# --------------------------------------------
class Group:
    """Abstract class, when extended is used for storage for data within a report

    Only accepts things wrapped in the ReportDatum class

    """

    def __init__(self, title, description=""):
        self.title = title
        self.description = description

        self.data = collections.OrderedDict()

        self.titleStyle = "font-weight: bold; padding-top: 20px;"
        self.descStyle = "font-weight: normal; font-style: italic; font-size: 14px; padding-left: 5px;"

    def __str__(self):
        str_ = "\n{} - (GROUP) {}\n".format(self.title, self.description)
        for name, value in self.data.items():
            str_ += "\t{:<30} {}\n".format(name, value)
        return str_

    def __getitem__(self, name):
        try:
            return self.data[name]
        except KeyError:
            runLog.warning(
                "Given name {} not present in report group {}".format(name, self.title)
            )

    def __setitem__(self, name, value):
        self.data[name] = value

    def writeHTML(self, f):
        """Writes the HTML information to file."""
        raise NotImplementedError


class Table(Group):
    def __init__(self, title, description="", header=None):
        Group.__init__(self, title, description=description)
        self.header = header

    def __str__(self):
        """Truer to content representation"""
        # set up
        prototypical_data = list(self.data.values())[0]
        num_cols = len(prototypical_data) + 1
        border_dashes = "-" * (num_cols * 31) + "\n"

        # create header
        str_ = border_dashes
        str_ += "{} - {}\n".format(self.title, self.description)
        if self.header:
            for column_title in self.header:
                str_ += "{:<30} ".format(column_title)
            str_ += "\n"
        str_ += border_dashes

        # create table body
        for name, value in sorted(self.data.items(), key=self._lowerCaseSortForTuples):
            str_ += "{:<30} ".format(name)
            for item in value:
                str_ += "{:<30} ".format(item)
            str_ += "\n"

        return str_

    @staticmethod
    def _lowerCaseSortForTuples(nameValPair):
        """This unfortunate method is made so the sort in the __str__ method complies with cython and python,

        previous attempts with lambdas have been unsuccessful in bridging the gap.

        """
        return nameValPair[0].lower()

    def __setitem__(self, name, value):
        if not isinstance(value, list):
            value = [value]

        Group.__setitem__(self, name, value)

    def writeHTML(self, f):

        with html.Table(f, attrs={"class": "table table-striped table-hover "}):
            with html.H4(f, attrs={"style": self.titleStyle}):
                f.writeEscaped(self.title)
                with html.Span(f, attrs={"style": self.descStyle}):
                    f.writeEscaped(self.description)

            if self.header:
                with html.THead(f):
                    with html.TR(f):
                        for colname in self.header:
                            with html.TH(f):
                                with html.Span(f):
                                    f.writeEscaped(colname)

            with html.TBody(f):
                for name, value in self.data.items():
                    with html.TR(f):
                        with html.TD(f, attrs={"class": "lalign"}):
                            f.writeEscaped(name)
                        for col in value:
                            with html.TD(f):
                                f.writeEscaped(col)


class Image(Group):

    count = 0

    def __init__(self, title, description=""):
        Group.__init__(self, title, description=description)
        self._shortformTitle = title.replace(" ", "").lower()

    def writeHTML(self, f):

        if len(self.data.keys()) == 1:

            # single images don't get the standard Header as the same information is moved to it's Figure Caption

            with html.Img(
                f,
                attrs={
                    "src": html.encode64(self.data[list(self.data.keys())[0]]),
                    "width": "100%",
                    "height": "100%",
                    "padding-top": "15px",
                },
            ):
                with html.Div(f, attrs={"class": "alert alert-dismissible alert-info"}):
                    with html.B(f):
                        Image.count += 1
                        f.writeEscaped("Figure {} - {}".format(Image.count, self.title))
                    f.writeEscaped(self.description)

        elif len(self.data.keys()) > 1:

            with html.H4(f, attrs={"style": self.titleStyle}):
                f.writeEscaped(self.title)
                with html.Span(f, attrs={"style": self.descStyle}):
                    f.writeEscaped(self.description)

            with html.UL(f, attrs={"class": "nav nav-tabs", "data-tabs": "tabs"}):
                first = True
                first_attrs = {"class": "active"}
                later_attrs = {"class": ""}
                for i in range(len(self.data.keys())):
                    with html.LI(f, attrs=first_attrs if first else later_attrs):
                        with html.A(
                            f,
                            attrs={
                                "href": "#{}{}".format(self._shortformTitle, i),
                                "data-toggle": "tab",
                            },
                        ):
                            f.writeEscaped(str(i + 1))
                    first = False

            with html.Div(f, attrs={"class": "tab-content"}):
                Image.count += 1
                first = True
                for i, (name, filepath) in enumerate(self.data.items()):
                    pane_attrs = {}
                    pane_attrs["class"] = (
                        "tab-pane fade active in" if first else "tab-pane fade"
                    )
                    pane_attrs["id"] = "{}{}".format(self._shortformTitle, i)
                    first = False

                    with html.Div(f, attrs=pane_attrs):
                        with html.Img(
                            f,
                            attrs={
                                "src": html.encode64(filepath),
                                "width": "100%",
                                "height": "100%",
                                "padding-top": "15px",
                            },
                        ):
                            with html.Div(
                                f, attrs={"class": "alert alert-dismissible alert-info"}
                            ):
                                with html.B(f):
                                    f.writeEscaped(
                                        "Figure {} - {}".format(Image.count, name)
                                    )
                                f.writeEscaped(filepath)

        else:
            runLog.warning(
                "Empty Image group {} has nothing to report to HTML".format(self.title)
            )

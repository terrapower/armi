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

"""Data formats for reports."""

import collections
import copy
import re

from armi import runLog


class Report:
    """Storage for data separated out for a particular kind of user."""

    # stubs for "further stylization" in the report package init
    groupsOrderFirst = []
    componentWellGroups = []

    def __init__(self, title, description):
        self.title = title
        self.description = description
        self.groups = {}  # {Global Instance : Local Instance}

    @property
    def _groupRenderOrder(self):
        """Helper method to the rendering methods on this class for rendering order of contained info."""
        presentGroupsOrderFirst = [group for group in self.groupsOrderFirst if group in self.groups]
        completeGroupOrder = presentGroupsOrderFirst + [
            group for group in self.groups.keys() if group not in presentGroupsOrderFirst
        ]
        specialsRemovedOrder = [group for group in completeGroupOrder if group not in self.componentWellGroups]
        return specialsRemovedOrder

    def __str__(self):
        str_ = "\n{} - (REPORT) {}\n".format(self.title, self.description)
        for global_group in self.groups.values():
            str_ += re.sub("\n", "\n\t", "{}".format(Group.__str__(global_group)))  # Don't use subclassed methods
        return str_

    def addToReport(self, group, name, value):
        """Inserts the datum into the correct group of the report."""
        if group not in self.groups:
            self.groups[group] = copy.deepcopy(group)
        self.groups[group][name] = value

    def __getitem__(self, group):
        try:
            return self.groups[group]
        except KeyError:
            runLog.warning("Cannot locate group {} in report {}".format(group.title, self.title))
            return None


class Group:
    """Abstract class, when extended is used for storage for data within a report.

    Only accepts things wrapped in the ReportDatum class.
    """

    def __init__(self, title, description=""):
        self.title = title
        self.description = description
        self.data = collections.OrderedDict()
        self.descStyle = "font-weight: normal; font-style: italic; font-size: 14px; padding-left: 5px;"
        self.titleStyle = "font-weight: bold; padding-top: 20px;"

    def __str__(self):
        str_ = "\n{} - (GROUP) {}\n".format(self.title, self.description)
        for name, value in self.data.items():
            str_ += "\t{:<30} {}\n".format(name, value)
        return str_

    def __getitem__(self, name):
        try:
            return self.data[name]
        except KeyError:
            runLog.warning("Given name {} not present in report group {}".format(name, self.title))

        return None

    def __setitem__(self, name, value):
        self.data[name] = value


class Table(Group):
    def __init__(self, title, description="", header=None):
        Group.__init__(self, title, description=description)
        self.header = header

    def __str__(self):
        """Truer to content representation."""
        # error handling
        if not len(self.data):
            return ""

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
        """Force the key in a key-value pair to lower case."""
        return nameValPair[0].lower()

    def __setitem__(self, name, value):
        if not isinstance(value, list):
            value = [value]

        Group.__setitem__(self, name, value)


class Image(Group):
    def __init__(self, title, description=""):
        Group.__init__(self, title, description=description)
        self._shortformTitle = title.replace(" ", "").lower()

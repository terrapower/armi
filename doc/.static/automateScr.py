# Copyright 2025 TerraPower, LLC
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
TODO: JOHN.

TODO: JOHN.
"""
import os
import pathlib
import subprocess

from ruamel.yaml import YAML

# TODO: JOHN: Explain
GITHUB_USERS = {
    "aaronjamesreynolds": "Aaron Reynolds",
    "albeanth": "Tony Alberti",
    "bsculac": "Brian Sculac",
    "drew-tp": "Drew Johnson",
    "john-science": "John Stilley",
    "keckler": "Chris Keckler",
    "mgjarrett": "Michael Jarrett",
    "ntouran": "Nick Touran",
    "onufer": "Mark Onufer",
    "opotowsky": "Arrielle Opotowsky",
    "zachmprince": "Zachary Prince",
}


def _findOneLineData(lines, key):
    """TODO: JOHN."""
    for line in lines:
        if line.startswith(key):
            return line.split(key)[1].strip()

    return "TBD"


def _buildScrLine(prNum: str, scrType: str):
    """TODO: JOHN."""
    txt = subprocess.check_output(["gh", "pr", "view", prNum]).decode("utf-8")
    lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]

    # grab title
    title = _findOneLineData(lines, "title:")

    # grab author
    author = _findOneLineData(lines, "author:")
    author = GITHUB_USERS.get(author, author)

    # grab reviewer(s)
    reviewers = _findOneLineData(lines, "reviewers:")
    reviewers = [rr.split("(")[0].strip() for rr in reviewers.split(",")]
    reviewers = [GITHUB_USERS.get(rr, rr) for rr in reviewers]
    reviewers = ", ".join(reviewers)

    # grab one-line description
    desc = _findOneLineData(lines, "One-Sentence Description:")

    # grab impact on requirements
    impact = _findOneLineData(lines, "One-line Impact on Requirements:")

    # build RST line for a list-table, representing this data
    tab = "   "
    col0 = f"{tab}* - "
    coli = f"{tab}  - "
    content = f"{col0}{title}\n"
    content += f"{coli}{desc}\n"
    content += f"{coli}{impact}\n"
    content += f"{coli}{author}\n"
    content += f"{coli}{reviewers}\n"
    content += f"{coli}{prNum}\n"

    return content


def buildScrTable(fileName: str, scrType: str):
    """TODO: JOHN."""
    # build file path from file name
    thisDir = pathlib.Path(__file__).parent.absolute()
    filePath = os.path.join(thisDir, "..", "qa_docs", "scr", fileName)

    # read YAML data
    with open(filePath, "r") as f:
        scrData = YAML().load(f)

    scrData = scrData[scrType]
    scrData = [int(st) for st in scrData if int(st) > 0]

    if len(scrData) < 1:
        return "NOTE: there were SCRs of this type.\n"

    # build table header
    tab = "   "
    content = ".. list-table:: Code Changes, Features\n"
    content += f"{tab}:widths: 20 25 25 15 15 10\n"
    content += f"{tab}:header-rows: 1\n\n"
    content += f"{tab}* - Title\n"
    content += f"{tab}  - Change\n"
    content += f"{tab}  - | Impact on\n"
    content += f"{tab}    | Requirements\n"
    content += f"{tab}  - Author\n"
    content += f"{tab}  - Reviewer(s)\n"
    content += f"{tab}  - PR\n"

    # add one row to the table for each SCR
    for prNum in sorted(scrData):
        content += _buildScrLine(str(prNum), scrType)

    content += "\n"
    return content

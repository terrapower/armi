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
Tool to build SCR tables to be added to the RST docs.

This script is meant to generate an RST-formatted list-table to the docs, to automate the process of
generating an SCR in ARMI.
"""

import subprocess

# A mapping of GitHub user names to actual names. Completely optional, just makes the SCR prettier.
GITHUB_USERS = {
    "aaronjamesreynolds": "Aaron Reynolds",
    "albeanth": "Tony Alberti",
    "alexhjames": "Alex James",
    "bsculac": "Brian Sculac",
    "clstocking": "Casey Stocking",
    "drewj-tp": "Drew Johnson",
    "jakehader": "Jake Hader",
    "john-science": "John Stilley",
    "keckler": "Chris Keckler",
    "mgjarrett": "Michael Jarrett",
    "ntouran": "Nick Touran",
    "onufer": "Mark Onufer",
    "opotowsky": "Arrielle Opotowsky",
    "sombrereau": "Tommy Cisneros",
    "zachmprince": "Zachary Prince",
}

PR_TYPES = {
    "docs": "Documentation-Only Changes",
    "features": "Code Changes, Features",
    "fixes": "Code Changes, Bugs and Fixes",
    "trivial": "Code Changes, Maintenance, or Trivial",
}


def _findOneLineData(lines: list, prNum: str, key: str):
    """Helper method to find a single line in a GH CLI PR dump.

    Parameters
    ----------
    lines : list
        The GH CLI dump of a PR, split into lines for convenience.
    prNum : str
        The GitHub PR number in question.
    key : str
        The substring that the line in questions starts with.

    Returns
    -------
    str
        Data pulled for the key in question.
    """
    for line in lines:
        if line.startswith(key):
            return line.split(key)[1].strip()

    print(f"WARNING: SCR: Could not find {key} in PR#{prNum}.")
    return "TBD"


def _buildScrLine(prNum: str):
    """Helper method to build a single RST list-table row in an SCR.

    Parameters
    ----------
    prNum : str
        The GitHub PR number in question.

    Returns
    -------
    str
        RST-formatted list-table row.
    """
    txt = subprocess.check_output(["gh", "pr", "view", prNum]).decode("utf-8")
    lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]

    # grab title
    title = _findOneLineData(lines, prNum, "title:")

    # grab author
    author = _findOneLineData(lines, prNum, "author:")
    author = GITHUB_USERS.get(author, author)

    # grab reviewer(s)
    reviewers = _findOneLineData(lines, prNum, "reviewers:")
    reviewers = [rr.split("(")[0].strip() for rr in reviewers.split(",")]
    reviewers = [GITHUB_USERS.get(rr, rr) for rr in reviewers]
    reviewers = ", ".join(reviewers)

    # grab one-line description
    scrType = _findOneLineData(lines, prNum, "Change Type:")
    if scrType not in PR_TYPES:
        print(f"WARNING: SCR: Invalid change type '{scrType}' for PR#{prNum}")
        scrType = "trivial"

    # grab one-line description
    desc = _findOneLineData(lines, prNum, "One-Sentence Description:")

    # grab impact on requirements
    impact = _findOneLineData(lines, prNum, "One-line Impact on Requirements:")

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

    return content, scrType


def _buildTableHeader(scrType: str):
    """Build a RST list-table header for an SCR listing.

    Parameters
    ----------
    scrType : str
        This has to be one of the defined SCR types: features, fixes, trivial, docs

    Returns
    -------
    str
        RST-formatted list-table header.
    """
    # build table header
    tab = "   "
    content = f".. list-table:: {PR_TYPES[scrType]}\n"
    content += f"{tab}:widths: 20 25 25 13 12 5\n"
    content += f"{tab}:header-rows: 1\n\n"
    content += f"{tab}* - Title\n"
    content += f"{tab}  - Change\n"
    content += f"{tab}  - | Impact on\n"
    content += f"{tab}    | Requirements\n"
    content += f"{tab}  - Author\n"
    content += f"{tab}  - Reviewer(s)\n"
    content += f"{tab}  - PR\n"

    return content


def isMainPR(prNum: int):
    """Determine if this PR is into the ARMI main branch.

    Parameters
    ----------
    prNum : int
        The number of this PR.

    Returns
    -------
    bool
        True if this PR is merging INTO the ARMI main branch. Default is True.
    """
    try:
        proc = subprocess.Popen(f"curl https://github.com/terrapower/armi/pull/{prNum}", stdout=subprocess.PIPE)
        txt = proc.communicate()[0].decode("utf-8")
        return "terrapower/armi:main" in txt
    except Exception as e:
        print(f"Failed to determine if this PR merged into the main branch: {e}")
        return True


def buildScrTable(thisPrNum: int, pastCommit: str):
    """Helper method to build an RST list-table for an SCR.

    Parameters
    ----------
    thisPrNum : int
        The number of this PR. If this is not a PR, this is a -1.
    pastCommit : str
        The shortened commit hash for a past reference commit. (This is the last commit of the last
        release. It will not be included.)

    Returns
    -------
    str
        RST-formatted list-table content.
    """
    # 1. Get a list of all the commits between this one and the reference
    txt = ""
    for num in range(100, 1001, 100):
        gitCmd = f"git log -n {num} --pretty=oneline --all".split(" ")
        txt = subprocess.check_output(gitCmd).decode("utf-8")
        if pastCommit in txt:
            break

    if not txt:
        return f"Could not find commit in git log: {pastCommit}"

    # 2. arse commit history to get the PR numbers
    prNums = []
    if thisPrNum > 0:
        # in case the docs are not being built from a PR
        prNums.append(thisPrNum)

    for ln in txt.split("\n"):
        line = ln.strip()
        if pastCommit in line:
            # do not include the reference commit
            break
        if line.endswith(")") and "(#" in line:
            # get the PR number
            prNums.append(int(line.split("(#")[-1].split(")")[0]))

    # 3. Build a table row for each SCR
    data = {"docs": [], "features": [], "fixes": [], "trivial": []}
    for prNum in sorted(prNums):
        if not isMainPR(prNum):
            continue
        row, scrType = _buildScrLine(str(prNum))
        data[scrType].append(row)

    # 4. Build final RST for all four tables, to return to the docs
    content = ""
    for typ in ["features", "fixes", "trivial", "docs"]:
        if len(data[typ]):
            content += _buildTableHeader(typ)
            for line in data[typ]:
                content += line
            content += "\n\n"

    return content

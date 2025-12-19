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
Tool to build SCR lists to be added to the RST docs.

This script is meant to be called by the docs build process, to help automate the process of generating lists of SCRs.
"""

import argparse
import subprocess

import requests

# A mapping of GitHub user names to actual names. Completely optional, just makes the SCR prettier.
GITHUB_USERS = {
    "aaronjamesreynolds": "Aaron Reynolds",
    "albeanth": "Tony Alberti",
    "alexhjames": "Alex James",
    "bsculac": "Brian Sculac",
    "clstocking": "Casey Stocking",
    "crswong888": "Chris Wong",
    "drewj-tp": "Drew Johnson",
    "HunterPSmith": "Hunter Smith",
    "jakehader": "Jake Hader",
    "jasonbmeng": "Jason Meng",
    "john-science": "John Stilley",
    "keckler": "Chris Keckler",
    "mgjarrett": "Michael Jarrett",
    "nipowell": "Nicole Powell",
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


def main():
    """NOTE: This is not used during CI, but exists only for testing and dev purposes."""
    # Instantiate the parser
    parser = argparse.ArgumentParser(description="An ARMI custom doc tool to build the SCR for this release.")

    # Required positional argument
    parser.add_argument("prNum", type=int, help="The current PR number (use -1 if there is no PR).")
    parser.add_argument("pastCommit", help="The commit hash of the last release.")

    # Parse the command line
    args = parser.parse_args()
    prNum = int(args.prNum)
    pastCommit = args.pastCommit

    buildScrListing(prNum, pastCommit)


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
    """Helper method to build a single RST list item in an SCR.

    Parameters
    ----------
    prNum : str
        The GitHub PR number in question.

    Returns
    -------
    str
        RST-formatted list item.
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
    reviewerHeader = "Reviewer(s)" if len(reviewers) > 1 else "Reviewer"
    reviewers = ", ".join(reviewers)

    # grab one-line description
    scrType = _findOneLineData(lines, prNum, "Change Type:")
    if scrType not in PR_TYPES:
        print(f"WARNING: SCR: Invalid change type '{scrType}' for PR#{prNum}")
        scrType = "trivial"

    # grab one-line description
    desc = _findOneLineData(lines, prNum, "One-Sentence Rationale:")

    # grab impact on requirements
    impact = _findOneLineData(lines, prNum, "One-line Impact on Requirements:")

    # build RST list item, representing this data
    tab = "  "
    content = f"* PR #{prNum}: {title}\n\n"
    content += f"{tab}* Rationale: {desc}\n"
    content += f"{tab}* Impact on Requirements: {impact}\n"
    content += f"{tab}* Author: {author}\n"
    content += f"{tab}* {reviewerHeader}: {reviewers}\n\n"

    return content, scrType


def _buildHeader(scrType: str):
    """Build a RST list header for an SCR listing.

    Parameters
    ----------
    scrType : str
        This has to be one of the defined SCR types: features, fixes, trivial, docs

    Returns
    -------
    str
        RST-formatted header title.
    """
    return f"\nList of SCRs of type: {PR_TYPES[scrType]}\n\n"


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
        url = f"https://github.com/terrapower/armi/pull/{prNum}"
        r = requests.get(url)
        return "terrapower/armi:main" in r.text
    except Exception as e:
        print(f"WARNING: SCR: Failed to determine if PR#{prNum} merged into the main branch: {e}")
        return True


def buildScrListing(thisPrNum: int, pastCommit: str):
    """Helper method to build an RST-formatted lists of all SCRs, by category.

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
        RST-formatted list content.
    """
    # 1. Get a list of all the commits between this one and the reference
    txt = ""
    for num in range(100, 2001, 100):
        print(f"Looking back {num} commits...")
        gitCmd = f"git log -n {num} --pretty=oneline --all".split(" ")
        txt = subprocess.check_output(gitCmd).decode("utf-8")
        if pastCommit in txt:
            break

    if not txt or pastCommit not in txt:
        return f"Could not find commit in git log: {pastCommit}"

    # 2. Parse commit history to get the PR numbers
    prNums = set()
    if thisPrNum > 0:
        # in case the docs are not being built from a PR
        prNums.add(thisPrNum)

    for ln in txt.split("\n"):
        line = ln.strip()
        if pastCommit in line:
            # do not include the reference commit
            break
        elif line.endswith(")") and "(#" in line:
            # get the PR number
            try:
                prNums.add(int(line.split("(#")[-1].split(")")[0]))
            except ValueError:
                # This is not a PR. Someone unwisely put some trash in the commit message.
                pass

    # 3. Build a list for each SCR
    data = {"docs": [], "features": [], "fixes": [], "trivial": []}
    for prNum in sorted(prNums):
        if not isMainPR(prNum):
            continue

        row, scrType = _buildScrLine(str(prNum))
        data[scrType].append(row)

    # 4. Build final RST for all four lists, to return to the docs
    content = ""
    for typ in ["features", "fixes", "trivial", "docs"]:
        if len(data[typ]):
            print(f"Found {len(data[typ])} SCRs in the {typ} category")
            content += _buildHeader(typ)
            for line in data[typ]:
                content += line
            content += "\n\n"

    content += "\n\n"

    print(content)
    return content


if __name__ == "__main__":
    main()

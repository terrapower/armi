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

import glob
import os
import xml.etree.ElementTree as ET

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(THIS_DIR, "..")
TEST_RESULTS = []


def parseTestXML(file):
    """Parse the test result XML file to gather results in a list of dictionaries.

    Parameters
    ----------
    file : path
        Path of XML file to be parsed

    Returns
    -------
    list
        Dictionaries containing:

        - File location of the test: 'file'
        - Class signature of test: 'class'
        - Method signature of test: 'method'
        - Runtime of test: 'time'
        - The result of the test: 'result' (passed, skipped, failure)
        - Console message when skipped or failed: 'info'
    """
    tree = ET.parse(file)

    results = []
    for testcase in tree.getroot().iter("testcase"):
        cn = testcase.attrib.get("classname", "unknown")
        tc_dict = {
            "file": "/".join(cn.split(".")[:-1]) + ".py",
            "class": cn.split(".")[-1],
            "method": testcase.attrib.get("name", "unknown"),
            "time": float(testcase.attrib.get("time", -1)),
            "result": "passed",
            "info": None,
        }
        if testcase.find("skipped") is not None:
            tc_dict["result"] = "skipped"
            tc_dict["info"] = testcase.find("skipped").attrib["message"]
        elif testcase.find("failure") is not None:
            tc_dict["result"] = "failure"
            tc_dict["info"] = testcase.find("failure").text

        results.append(tc_dict)

    return results


def getTestResult(app, need, needs):
    """Dynamic function used by sphinx-needs to gather the result of a test tag."""
    if not need["signature"]:
        return "none"

    # Get all the tests that match the method signature
    results = [
        test_case["result"]
        for test_case in TEST_RESULTS
        if need["signature"] == test_case["method"]
    ]
    # Logic is as follows if there are multiple matches:
    #   - If one is a "failure", then return "failure"
    #   - If all are "skipped", then return "skipped"
    #   - Otherwise, return "passed"
    if results:
        if "failure" in results:
            return "failure"
        elif "passed" in results:
            return "passed"
        else:
            return "skipped"

    # Things get a little more complicated when the test tag has a class-level signature.
    # Basically we have to determine if all the methods in the class passed or if any of skipped/failed.
    # First, gather all the results related to the class signature from the tag and categorize by method
    results = {}
    for test_case in TEST_RESULTS:
        if need["signature"] == test_case["class"]:
            if test_case["method"] in results:
                results[test_case["method"]].append(test_case["result"])
            else:
                results[test_case["method"]] = [test_case["result"]]

    # If we haven't found the test by now, we never will
    if not results:
        return "none"

    # Apply logic from before for each method in the class
    for m, r in results.items():
        if "failure" in r:
            results[m] = "failure"
        elif "passed" in r:
            results[m] = "passed"
        else:
            results[m] = "skipped"

    # Now for the class logic
    #  - If any of the methods failed, return "failure"
    #  - If any of the methods skipped, return "skipped"
    #  - If all of the methods passed, return "passed"
    if "failure" in results.values():
        return "failure"
    elif "skipped" in results.values():
        return "skipped"
    else:
        return "passed"


# Here is where we fill out all the test results, so it is only done once
for file in glob.glob(os.path.join(RESULTS_DIR, "*.xml")):
    TEST_RESULTS.extend(parseTestXML(file))

if __name__ == "__main__":
    # Prints results of all the tests found in the repo in a pytest-like way
    colors = {
        "passed": "\033[92m",
        "skipped": "\033[93m",
        "failure": "\033[91m",
        "end": "\033[0m",
    }
    for testcase in TEST_RESULTS:
        print(
            "{} {} {} {}::{}::{}".format(
                colors[testcase["result"]],
                testcase["result"].upper(),
                colors["end"],
                testcase["file"],
                testcase["class"],
                testcase["method"],
            )
        )

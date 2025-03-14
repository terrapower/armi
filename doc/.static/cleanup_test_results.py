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
Docs build helper script, used to clean up the test-results file so it is easier to read in HTML
and PDF later.
"""

from sys import argv

CLASS_NAME = 'classname="'


def main():
    assert len(argv) == 2, "No input file provided"
    filePath = argv[1]
    cleanup_test_results(filePath)


def cleanup_test_results(filePath: str):
    """Clean up the test-results file so it is easier to read in HTML and PDF later.

    Parameters
    ----------
    filePath : str
        Path to junit pytest test results XML file.
    """
    txt = open(filePath, "r").read()
    bits = txt.split(CLASS_NAME)

    newTxt = bits[0]
    for i in range(1, len(bits)):
        assert '"' in bits[i], f"Something is wrong with the file: {bits[i]}"
        row = bits[i].split('"')
        row[0] = row[0].split(".")[-1]
        newTxt += CLASS_NAME + '"'.join(row)

    with open(filePath, "w") as f:
        f.write(newTxt)


if __name__ == "__main__":
    main()

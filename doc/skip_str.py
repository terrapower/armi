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
A simple helper script to create dummy data files for the STR.

If the user wants to build the docs without going through the hassle of running the testing, they
can run this simple script which will create some placeholder files for the STR:

* pytest_verbose.log
* test_results.xml
* test_results_mpi1.xml
* test_results_mpi2.xml
* test_results_mpi3.xml

"""


def main():
    # skip build the STR, if you are running locally
    with open("pytest_verbose.log", "w") as f:
        f.write("skipping STR")

    fileNames = [f"test_results_mpi{i}.xml" for i in range(1, 4)]
    fileNames.append("test_results.xml")
    for fileName in fileNames:
        with open(fileName, "w") as f:
            f.write("<metadata></metadata>")


if __name__ == "__main__":
    main()

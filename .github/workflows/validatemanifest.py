# Copyright 2022 TerraPower, LLC
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
Validating the package-data in the pyproject.toml.

Validate that we aren't trying to include files that don't exist.
"""

import os
from glob import glob

import toml

# CONSTANTS
ARMI_DIR = "armi/"
PRPROJECT = "pyproject.toml"


def main():
    # parse the data files out of the pyproject.toml
    txt = open(PRPROJECT, "r").read()
    data = toml.loads(txt)
    fileChunks = data["tool"]["setuptools"]["package-data"]["armi"]

    # loop through each line in the package-data and find all the file paths
    errors = []
    for i, line in enumerate(fileChunks):
        # make sure the file exists
        path = ARMI_DIR + line.strip()
        if "*" in path:
            paths = [f for f in glob(path) if len(f) > 3]
            if not len(paths):
                errors.append((i, path))
        else:
            if not os.path.exists(path):
                errors.append((i, path))

    # If there were any missing files, raise an Error.
    if errors:
        for i, line in errors:
            print("Nonexistant file on line {}: {}".format(i, line))
        raise ValueError("Package-data file is incorrect: includes non-existant files.")


if __name__ == "__main__":
    main()

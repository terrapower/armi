# Copyright 2024 TerraPower, LLC
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

"""This script exists so we can determine if new tests in CI are leaving crumbs."""

import subprocess

# A list of objects we expect during a run, and don't mind (like pycache dirs).
IGNORED_OBJECTS = [
    ".pytest_cache",
    ".tox",
    "__pycache__",
    "armi.egg-info",
    "armi/logs/ARMI.armiRun.",
    "armi/logs/armiRun.mpi.log",
    "armi/tests/tutorials/case-suite/",
    "armi/tests/tutorials/logs/",
    "logs/",
]


def main():
    # use "git clean" to find all non-tracked files
    proc = subprocess.Popen(["git", "clean", "-xnd"], stdout=subprocess.PIPE)
    lines = proc.communicate()[0].decode("utf-8").split("\n")

    # clean up the whitespace
    lines = [ln.strip() for ln in lines if len(ln.strip())]

    # ignore certain untracked object, like __pycache__ dirs
    for ignore in IGNORED_OBJECTS:
        lines = [ln for ln in lines if ignore not in ln]

    # fail hard if there are still untracked files
    if len(lines):
        for line in lines:
            print(line)

        raise ValueError("The workspace is dirty; the tests are leaving crumbs!")


if __name__ == "__main__":
    main()

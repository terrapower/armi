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

"""TODO."""
import subprocess


def main():
    # skip build the STR, if you are running locally
    cmd = 'echo "skipping STR"'
    fileName = "pytest_verbose.log"
    _pipeCmdToFile(cmd, fileName, True)

    cmd = 'echo "<metadata></metadata>"'
    fileName = "test_results.xml"
    _pipeCmdToFile(cmd, fileName, True)


def _pipeCmdToFile(cmd, fileName, append=False):
    """Write the results of a command line to a simple log file."""
    if append:
        write = "a"
    else:
        write = "w"

    txt = subprocess.check_output(cmd).decode("utf-8").strip()
    with open(fileName, write) as f:
        print(f"Writing {fileName}")
        f.write(txt)
        f.write("\n\n")


if __name__ == "__main__":
    main()

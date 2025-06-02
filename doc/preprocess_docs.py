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
TODO.

Then this:

pytest --junit-xml=test_results.xml -v -n 4 armi > pytest_verbose.log
mpiexec -n 2 --use-hwthread-cpus pytest --junit-xml=test_results_mpi1.xml
    armi/tests/test_mpiFeatures.py > pytest_verbose_mpi1.log
mpiexec -n 2 --use-hwthread-cpus pytest --junit-xml=test_results_mpi2.xml
    armi/tests/test_mpiParameters.py > pytest_verbose_mpi2.log
mpiexec -n 2 --use-hwthread-cpus pytest --junit-xml=test_results_mpi3.xml
    armi/utils/tests/test_directoryChangersMpi.py > pytest_verbose_mpi3.log
python doc/.static/cleanup_test_results.py test_results.xml
"""
import os
import subprocess
import sys
from datetime import datetime

from armi.bookkeeping.report.reportingUtils import getSystemInfo


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--cleanup", "-c"]:
        # TODO
        for fileName in [
            "python_details.log",
            "pytest_verbose.log",
            "system_info.log",
            "test_results.xml",
        ]:
            if os.path.exists(fileName):
                print(f"Removing {fileName}")
                os.remove(fileName)

        return

    if len(sys.argv) > 1 and sys.argv[1].lower() in ["--skip-str", "-s"]:
        # TODO
        cmd = 'echo "skipping STR"'
        fileName = "pytest_verbose.log"
        pipeCmdToFile(cmd, fileName, True)

        cmd = 'echo "<metadata></metadata>"'
        fileName = "test_results.xml"
        pipeCmdToFile(cmd, fileName, True)

    # Use an ARMI tool to grab all system information
    fileName = "system_info.log"

    txt = getSystemInfo()
    with open(fileName, "w") as f:
        print(f"Writing {fileName}")
        f.write(txt)

    # Use command line to get Python venv information
    fileName = "python_details.log"
    writeDateFile(fileName)

    cmd = "armi --version"
    pipeCmdToFile(cmd, fileName, True)

    cmd = "python --version"
    pipeCmdToFile(cmd, fileName, True)

    cmd = "pip freeze"
    pipeCmdToFile(cmd, fileName, True)


def writeDateFile(fileName):
    """TODO."""
    txt = datetime.now().strftime("%Y-%m-%d")
    with open(fileName, "w") as f:
        print(f"Writing {fileName}")
        f.write(txt)
        f.write("\n\n")


def pipeCmdToFile(cmd, fileName, append=False):
    """TODO."""
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

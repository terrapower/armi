# Copyright 2019 TerraPower, LLC
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
Primary entry point into ARMI.

There are a variety of entry points in the ``cli`` package that define the various run options.
This invokes them according to command-line user input.
"""

import sys
import traceback

from armi import apps, configure, context, isConfigured, runLog
from armi.cli import ArmiCLI


def main():
    # Main entry point into ARMI
    try:
        if not isConfigured():
            configure(apps.App())
        code = ArmiCLI().run()
        # sys exit interprets None as 0
        sys.exit(code)
    except Exception:
        # Make sure not to catch all BaseExceptions, lest we catch the expected SystemExit exception
        runLog.error(
            f"Unhandled exception in __main__, rank {context.MPI_RANK} on {context.MPI_NODENAME}.",
            file=sys.__stderr__,
        )
        runLog.error(traceback.format_exc(), file=sys.__stderr__)
        if context.MPI_SIZE > 1:
            runLog.error(
                f"Killing all MPI tasks from __main__, rank {context.MPI_RANK}.",
                file=sys.__stderr__,
            )
            # cleanFastPathAfterSimulation has @atexit.register so it should be called at the end, but mpi. Abort
            # in main will not allow for @atexit.register or except/finally code to be called so
            # calling here as well
            context.cleanFastPathAfterSimulation()
            # .Abort will not allow for @atexit.register or except/finally code to be called
            context.MPI_COMM.Abort(errorcode=-1)

        raise SystemExit(1)


if __name__ == "__main__":
    main()

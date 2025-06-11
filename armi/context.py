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
Module containing global constants that reflect the executing context of ARMI.

ARMI's global state information: operating system information, environment data, user data, memory
parallelism, temporary storage locations, and if operational mode (interactive, gui, or batch).
"""

import datetime
import enum
import gc
import getpass
import os
import sys
import time
from logging import DEBUG

# h5py needs to be imported here, so that the disconnectAllHdfDBs() call that gets bound to atexit
# below doesn't lead to a segfault on python exit.
#
# Minimal code to reproduce the issue:
#
# >>> import atexit
#
# >>> def willSegFault():
# >>>     import h5py
#
# >>> atexit.register(willSegFault)
import h5py  # noqa: F401

BLUEPRINTS_IMPORTED = False
BLUEPRINTS_IMPORT_CONTEXT = ""

# App name is used when spawning new tasks that should invoke a specific ARMI application. Sometimes
# these tasks only use ARMI functionality, so running `python -m armi` is fine. Other times, the
# task is specific to an application, requiring something like: `python -m myArmiApp`
APP_NAME = "armi"


class Mode(enum.Enum):
    """
    Mode represents different run types possible in ARMI.

    The modes can be Batch, Interactive, or GUI. Mode is generally auto-detected based on your
    terminal. It can also be set in various CLI entry points. Each entry point has a ``--batch``
    command line argument that can force Batch mode.
    """

    BATCH = 1
    INTERACTIVE = 2
    GUI = 4

    @classmethod
    def setMode(cls, mode):
        """Set the run mode of the current ARMI case."""
        global CURRENT_MODE
        assert isinstance(mode, cls), "Invalid mode {}".format(mode)
        CURRENT_MODE = mode


ROOT = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.join(ROOT, "..")
RES = os.path.join(ROOT, "resources")
DOC = os.path.abspath(os.path.join(PROJECT_ROOT, "doc"))
USER = getpass.getuser()
START_TIME = time.ctime()

# Set batch mode if not a TTY, which means you're on a cluster writing to a stdout file. In this
# mode you cannot respond to prompts. (This does not work reliably for both Windows and Linux so an
# os-specific solution is applied.)
IS_WINDOWS = ("win" in sys.platform) and ("darwin" not in sys.platform)
isatty = sys.stdout.isatty() if IS_WINDOWS else sys.stdin.isatty()
CURRENT_MODE = Mode.INTERACTIVE if isatty else Mode.BATCH
Mode.setMode(CURRENT_MODE)

MPI_COMM = None
# MPI_RANK represents the index of the CPU that is running.
# 0 is typically the primary CPU, while 1+ are typically workers.
MPI_RANK = 0
# MPI_SIZE is the total number of CPUs.
MPI_SIZE = 1
LOCAL = "local"
MPI_NODENAME = LOCAL
MPI_NODENAMES = [LOCAL]


try:
    # Check for MPI
    from mpi4py import MPI

    MPI_COMM = MPI.COMM_WORLD
    MPI_RANK = MPI_COMM.Get_rank()
    MPI_SIZE = MPI_COMM.Get_size()
    MPI_NODENAME = MPI.Get_processor_name()
    MPI_NODENAMES = MPI_COMM.allgather(MPI_NODENAME)
except ImportError:
    # stick with defaults
    pass

if sys.platform.startswith("win"):
    # trying a Windows approach
    APP_DATA = os.path.join(os.environ["APPDATA"], "armi")
    APP_DATA = APP_DATA.replace("/", "\\")
else:
    # non-Windows: /tmp/ if possible, if not home
    if os.access("/tmp/", os.W_OK):
        APP_DATA = "/tmp/.armi"
    else:
        APP_DATA = os.path.expanduser("~/.armi")

if MPI_NODENAMES.index(MPI_NODENAME) == MPI_RANK:
    if not os.path.isdir(APP_DATA):
        try:
            os.makedirs(APP_DATA)
            os.chmod(APP_DATA, 0o0777)
        except OSError:
            pass
    if not os.path.isdir(APP_DATA):
        raise OSError("Directory doesn't exist {0}".format(APP_DATA))

if MPI_COMM is not None:
    # Make sure app data exists before workers proceed.
    MPI_COMM.barrier()

MPI_DISTRIBUTABLE = MPI_SIZE > 1

_FAST_PATH = os.path.join(os.getcwd())
"""
A directory available for high-performance I/O.

.. warning:: This is not a constant and can change at runtime.
"""

_FAST_PATH_IS_TEMPORARY = False
"""Flag indicating whether or not the FAST_PATH should be cleaned up on exit."""


def activateLocalFastPath() -> None:
    """
    Specify a local temp directory to be the fast path.

    ``FAST_PATH`` is often a local hard drive on a cluster node. It should be a high-performance
    scratch space. Different processors on the same node should have different fast paths.

    Notes
    -----
    This path will be obliterated when the job ends.

    This path is set at import time, so if a series of unit tests come through that instantiate one
    operator after the other, the path will already exist the second time. The directory is created
    in the Operator constructor.
    """
    global _FAST_PATH, _FAST_PATH_IS_TEMPORARY, APP_DATA

    # Try to fix pathing issues in Windows.
    if os.name == "nt":
        APP_DATA = APP_DATA.replace("/", "\\")

    _FAST_PATH = os.path.join(
        APP_DATA,
        "{}{}-{}".format(
            MPI_RANK,
            os.environ.get("PYTEST_XDIST_WORKER", ""),  # for parallel unit testing,
            datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
        ),
    )

    _FAST_PATH_IS_TEMPORARY = True


def getFastPath() -> str:
    """
    Callable to get the current FAST_PATH.

    Notes
    -----
    This exists because it's dangerous to use ``FAST_PATH`` directly. as it can change between
    import and runtime.
    """
    return _FAST_PATH


def cleanTempDirs(olderThanDays=None):
    """
    Clean up temporary files after a run.

    Some Windows HPC systems send a SIGBREAK signal when the user cancels a job, which is NOT
    handled by ``atexit``. Notably, SIGBREAK does not exist outside Windows. For the SIGBREAK signal
    to work with a Windows HPC, the ``TaskCancelGracePeriod`` option must be configured to be non-
    zero. This sets the period between SIGBREAK and SIGTERM/SIGINT. To do cleanups in this case, we
    must use the ``signal`` module. Actually, even then it does not work because MS ``mpiexec`` does
    not pass signals through.

    Parameters
    ----------
    olderThanDays: int, optional
        If provided, deletes other ARMI directories if they are older than the requested time.
    """
    from armi import runLog
    from armi.utils.pathTools import cleanPath

    disconnectAllHdfDBs()
    printMsg = runLog.getVerbosity() <= DEBUG
    if _FAST_PATH_IS_TEMPORARY and os.path.exists(_FAST_PATH):
        if printMsg:
            print(
                "Cleaning up temporary files in: {}".format(_FAST_PATH),
                file=sys.stdout,
            )
        try:
            cleanPath(_FAST_PATH, mpiRank=MPI_RANK)
        except Exception as error:
            for outputStream in (sys.stderr, sys.stdout):
                if printMsg:
                    print(
                        "Failed to delete temporary files in: {}\n    error: {}".format(_FAST_PATH, error),
                        file=outputStream,
                    )

    if olderThanDays is not None:
        cleanAllArmiTempDirs(olderThanDays)


def cleanAllArmiTempDirs(olderThanDays: int) -> None:
    """
    Delete all ARMI-related files from other unrelated runs after `olderThanDays` days (in case this
    failed on earlier runs).

    This is a useful utility in HPC environments when some runs crash sometimes.

    Warning
    -------
    This will break any concurrent runs that are still running.
    """
    from armi.utils.pathTools import cleanPath

    gracePeriod = datetime.timedelta(days=olderThanDays)
    now = datetime.datetime.now()
    thisRunFolder = os.path.basename(_FAST_PATH)

    for dirname in os.listdir(APP_DATA):
        dirPath = os.path.join(APP_DATA, dirname)
        if not os.path.isdir(dirPath):
            continue
        try:
            fromThisRun = dirname == thisRunFolder  # second chance to delete
            _rank, dateString = dirname.split("-")
            dateOfFolder = datetime.datetime.strptime(dateString, "%Y%m%d%H%M%S%f")
            runIsOldAndLikleyComplete = (now - dateOfFolder) > gracePeriod
            if runIsOldAndLikleyComplete or fromThisRun:
                # Delete old files
                cleanPath(dirPath, mpiRank=MPI_RANK)
        except Exception:
            pass


def disconnectAllHdfDBs() -> None:
    """
    Forcibly disconnect all instances of HdfDB objects.

    Notes
    -----
    This is a hack to help ARMI exit gracefully when the garbage collector and h5py have issues
    destroying objects. The root cause for why this was having issues was never identified. It
    appears that when several HDF5 files are open in the same run (e.g. when calling ``armi.init()``
    multiple times from a post-processing script), when these h5py File objects were closed, the
    garbage collector would raise an exception related to the repr'ing the object. We get around
    this by using the garbage collector to manually disconnect all open HdfDBs.
    """
    from armi.bookkeeping.db import Database

    h5dbs = [db for db in gc.get_objects() if isinstance(db, Database)]
    for db in h5dbs:
        db.close()

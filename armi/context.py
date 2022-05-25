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

This contains information about the circumstatces under which an ARMI application is
running. Things like the MPI environment, executing user, etc. live here. These are
re-exported by the `armi` package, but live here so that import loops won't lead to
as many issues.
"""
from logging import DEBUG
import datetime
import enum
import gc
import getpass
import os
import sys
import time

# h5py needs to be imported here, so that the disconnectAllHdfDBs() call that gets bound
# to atexit below doesn't lead to a segfault on python exit. The Database3 module is
# imported at call time, since it itself needs stuff that is initialized in this module
# to import properly.  However, if that import leads to the first time that h5py is
# imported in this process, doing so will cause a segfault. The theory here is that this
# happens because the h5py extension module is not safe to import (for whatever reason)
# when the python interpreter is in whatever state it's in when the atexit callbacks are
# being invoked.  Importing early avoids this.
#
# Minimal code to reproduce the issue:
#
# >>> import atexit
#
# >>> def willSegFault():
# >>>     import h5py
#
# >>> atexit.register(willSegFault)

import h5py


BLUEPRINTS_IMPORTED = False
BLUEPRINTS_IMPORT_CONTEXT = ""

# App name is used when spawning new tasks that should invoke a specific ARMI
# application. For instance, the framework provides some features to help with
# submitting tasks to an HPC cluster. Sometimes these tasks are themselves only using
# ARMI functionality, so running `python -m armi` is fine. Other times, the task is
# specific to an application, requiring something like `python -m myArmiApp`
APP_NAME = "armi"


class Mode(enum.Enum):
    """
    Mode represents different run modes possible in ARMI.

    The modes can be Batch, Interactive, or GUI. In different modes, there are different
    types of interactions possible.

    Mode is generally auto-detected based on your terminal. It can also be set in
    various CLI entry points, which are the implementations of
    :py:class:`armi.cli.entryPoint.EntryPoint`. Lastly, each entry point has a
    ``--batch`` command line argument that can force Batch mode.
    """

    BATCH = 1
    INTERACTIVE = 2
    GUI = 4

    @classmethod
    def setMode(cls, mode):
        """Set the run mode of the current ARMI case."""
        global CURRENT_MODE  # pylint: disable=global-statement
        assert isinstance(mode, cls), "Invalid mode {}".format(mode)
        CURRENT_MODE = mode


ROOT = os.path.abspath(os.path.dirname(__file__))
RES = os.path.join(ROOT, "resources")
DOC = os.path.abspath(os.path.join(ROOT, "..", "doc"))
USER = getpass.getuser()
START_TIME = time.ctime()

# Set batch mode if not a TTY, which means you're on a cluster writing to a stdout file
# In this mode you cannot respond to prompts or anything
CURRENT_MODE = Mode.INTERACTIVE if sys.stdout.isatty() else Mode.BATCH
Mode.setMode(CURRENT_MODE)

MPI_COMM = None
# MPI_RANK represents the index of the CPU that is running.
# 0 is typically the master CPU, while 1+ are typically workers.
# MPI_SIZE is the total number of CPUs
MPI_RANK = 0
MPI_SIZE = 1
MPI_NODENAME = "local"
MPI_NODENAMES = ["local"]


try:
    # Check for MPI
    # The mpi4py module uses cPickle to serialize python objects in preparation for
    # network transmission. Sometimes, when cPickle fails, it gives very cryptic error
    # messages that do not help much. If you uncomment th following line, you can trick
    # mpi4py into using the pure-python pickle module in place of cPickle and now you
    # will generally get much more meaningful and useful error messages Then comment it
    # back out because it's slow.
    # import sys, pickle; sys.modules['cPickle'] = pickle
    from mpi4py import MPI

    MPI_COMM = MPI.COMM_WORLD
    MPI_RANK = MPI_COMM.Get_rank()
    MPI_SIZE = MPI_COMM.Get_size()
    MPI_NODENAME = MPI.Get_processor_name()
    MPI_NODENAMES = MPI_COMM.allgather(MPI_NODENAME)
except ImportError:
    # stick with defaults
    pass

try:
    # trying a windows approach
    APP_DATA = os.path.join(os.environ["APPDATA"], "armi")
    APP_DATA = APP_DATA.replace("/", "\\")
except:  # pylint: disable=bare-except
    # non-windows
    APP_DATA = os.path.expanduser("~/.armi")

if MPI_NODENAMES.index(MPI_NODENAME) == MPI_RANK:
    if not os.path.isdir(APP_DATA):
        try:
            os.makedirs(APP_DATA)
        except OSError as e:
            pass
    if not os.path.isdir(APP_DATA):
        raise e

if MPI_COMM is not None:
    MPI_COMM.barrier()  # make sure app data exists before workers proceed.

MPI_DISTRIBUTABLE = MPI_RANK == 0 and MPI_SIZE > 1

_FAST_PATH = os.path.join(os.getcwd())
"""
A directory available for high-performance I/O

.. warning:: This is not a constant and can change at runtime.
"""

_FAST_PATH_IS_TEMPORARY = False
"""Flag indicating whether or not the FAST_PATH should be cleaned up on exit."""


def activateLocalFastPath() -> None:
    """
    Specify a local temp directory to be the fast path.

    ``FAST_PATH`` is often a local hard drive on a cluster node. It's a high-performance
    scratch space. Different processors on the same node should have different fast paths.
    Some old code may MPI_RANK-dependent folders/filenames as well, but this is no longer
    necessary.

    .. warning:: This path will be obliterated when the job ends so be careful.

    Note also
    that this path is set at import time, so if a series of unit tests come through that
    instantiate one operator after the other, the path will already exist the second time.
    The directory is created in the Operator constructor.
    """
    global _FAST_PATH, _FAST_PATH_IS_TEMPORARY, APP_DATA  # pylint: disable=global-statement

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
    It's too dangerous to use ``FAST_PATH`` directly as it can change between import and
    runtime. For example, a module that does ``from armi.context import FAST_PATH`` is
    disconnected from the official ``FAST_PATH`` controlled by this module.
    """
    return _FAST_PATH


def cleanTempDirs(olderThanDays=None):
    """
    Clean up temporary files after a run.

    The Windows HPC system sends a SIGBREAK signal when the user cancels a job, which
    is NOT handled by ``atexit``. Notably SIGBREAK doesn't exist off Windows.
    For the SIGBREAK signal to work with a Microsoft HPC, the ``TaskCancelGracePeriod``
    option must be configured to be non-zero. This sets the period between SIGBREAK
    and SIGTERM/SIGINT. To do cleanups in this case, we must use the ``signal`` module.
    Actually, even then it does not work because MS ``mpiexec`` does not pass signals
    through.

    Parameters
    ----------
    olderThanDays: int, optional
        If provided, deletes other ARMI directories if they are older than the requested
        time.
    """
    # pylint: disable=import-outside-toplevel # avoid cyclic import
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
            cleanPath(_FAST_PATH, MPI_RANK)
        except Exception as error:  # pylint: disable=broad-except
            for outputStream in (sys.stderr, sys.stdout):
                if printMsg:
                    print(
                        "Failed to delete temporary files in: {}\n"
                        "    error: {}".format(_FAST_PATH, error),
                        file=outputStream,
                    )

    if olderThanDays is not None:
        cleanAllArmiTempDirs(olderThanDays)


def cleanAllArmiTempDirs(olderThanDays: int) -> None:
    """
    Delete all ARMI-related files from other unrelated runs after `olderThanDays` days (in
    case this failed on earlier runs).

    .. warning:: This will break any concurrent runs that are still running.

    This is a useful utility in HPC environments when some runs crash sometimes.
    """
    # pylint: disable=import-outside-toplevel # avoid cyclic import
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
                cleanPath(dirPath, MPI_RANK)
        except:  # pylint: disable=bare-except
            pass


def disconnectAllHdfDBs() -> None:
    """
    Forcibly disconnect all instances of HdfDB objects

    Notes
    -----
    This is a hack to help ARMI exit gracefully when the garbage collector and h5py have
    issues destroying objects. After lots of investigation, the root cause for why this
    was having issues was never identified. It appears that when several HDF5 files are
    open in the same run (e.g.  when calling armi.init() multiple times from a
    post-processing script), when these h5py File objects were closed, the garbage
    collector would raise an exception related to the repr'ing the object. We
    get around this by using the garbage collector to manually disconnect all open HdfDB
    objects.
    """

    from armi.bookkeeping.db import Database3  # pylint: disable=import-outside-toplevel

    h5dbs = [db for db in gc.get_objects() if isinstance(db, Database3)]
    for db in h5dbs:
        db.close()

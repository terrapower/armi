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
import datetime
import getpass
import os
import time
import sys


BLUEPRINTS_IMPORTED = False
BLUEPRINTS_IMPORT_CONTEXT = ""


# App name is used when spawning new tasks that should invoke a specific ARMI
# application. For instance, the framework provides some features to help with
# submitting tasks to an HPC cluster. Sometimes these tasks are themselves only using
# ARMI functionality, so running `python -m armi` is fine. Other times, the task is
# specific to an application, requiring something like `python -m myArmiApp`
APP_NAME = "armi"


class Mode:
    """
    Mode represents different run modes possible in ARMI.

    The modes can be Batch, Interactive, or GUI. In different modes, there are different
    types of interactions possible.

    Mode is generally auto-detected based on your terminal. It can also be set in
    various CLI entry points, which are the implementations of
    :py:class:`armi.cli.entryPoint.EntryPoint`. Lastly, each entry point has a
    ``--batch`` command line argument that can force Batch mode.
    """

    Batch = 1
    Interactive = 2
    Gui = 4

    @classmethod
    def setMode(cls, mode):
        """Set the run mode of the current ARMI case."""
        global CURRENT_MODE  # pylint: disable=global-statement
        assert mode in (cls.Batch, cls.Interactive, cls.Gui), "Invalid mode {}".format(
            mode
        )
        CURRENT_MODE = mode


ROOT = os.path.abspath(os.path.dirname(__file__))
RES = os.path.join(ROOT, "resources")
DOC = os.path.abspath(os.path.join(ROOT, "..", "doc"))
USER = getpass.getuser()
START_TIME = time.ctime()

# Set batch mode if not a TTY, which means you're on a cluster writing to a stdout file
# In this mode you cannot respond to prompts or anything
CURRENT_MODE = Mode.Interactive if sys.stdout.isatty() else Mode.Batch
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
    APP_DATA = os.path.join(os.environ["APPDATA"], "armi")
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

# FAST_PATH is often a local hard drive on a cluster node. It's a high-performance
# scratch space. Different processors on the same node should have different fast paths.
# Some old code may MPI_RANK-dependent folders/filenames as well, but this is no longer
# necessary. This path will be obliterated when the job ends so be careful. Note also
# that this path is set at import time, so if a series of unit tests come through that
# instantiate one operator after the other, the path will already exist the second time.
# The directory is created in the Operator constructor.
FAST_PATH = os.path.join(
    APP_DATA,
    "{}{}-{}".format(
        MPI_RANK,
        os.environ.get("PYTEST_XDIST_WORKER", ""),  # for parallel unit testing,
        datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
    ),
)

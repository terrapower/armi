# Copyright 2009-2019 TerraPower, LLC
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
Welcome to the Advanced Reactor Modeling Interface (ARMI).

This module initializes the ARMI platform. The bootstrap process is broken into several phases:

* Import fundamental dependencies in Python library and some third-party libs
* Investigate environment: Check Python version, check code version, check MPI situation,
  check for TTY/GUI/interactivity,
* Set up temp dirs
* Set up printout table formats (in preparation of logging info)
* Initialize all possible nuclide objects in the nuclide directory
* Discover and register available built-in :py:mod:`plugins <armi.plugins>`
  (custom ones registered after input available)
* Discover and define all potential configuration settings from available plugins
* Read input files
* Update :py:mod:`nuclide directory <armi.nucDirectory>` with depletion info based on config
* Discover and define all state :py:mod:`Parameters <armi.reactor.parameters>` on data model
  (possibly dependent on config)
* Discover :py:mod:`Entry points <armi.cli>` from plugins
* Choose entry point based on user command

If using the ``run`` entry point, additional work is done:

* Build :py:mod:`reactor model <armi.reactor>` based on input
* Build :py:mod:`operator object <armi.operators>` with specific calculation loop
* Build ordered interface stack based on configuration settings
* Begin looping over interface stack, operating upon data model according to operator design
* Loop until complete
* Wrap up
* Quit
"""
import atexit
import datetime
import gc
import importlib
import os
import shutil
import signal
import subprocess
import sys
from typing import Optional, List, Type
import warnings

import pluggy

# The _bootstrap module performs operations that may need to occur before it is
# necessarily safe to import the rest of the ARMI system. Things like:
# - configure the MPI environment
# - detect the nature of interaction with the user (terminal UI, GUI, unsupervized, etc)
# - create/define the FAST_PATH, etc
# - Initialize the nuclide database
import armi._bootstrap
import armi.context
from armi.context import (
    ROOT,
    RES,
    DOC,
    USER,
    START_TIME,
    CURRENT_MODE,
    MPI_COMM,
    MPI_RANK,
    MPI_NODENAME,
    MPI_NODENAMES,
    MPI_DISTRIBUTABLE,
    MPI_SIZE,
    APP_DATA,
    FAST_PATH,
)
from armi.context import Mode
from armi.meta import __version__
from armi import apps
from armi import plugins
from armi import runLog
from armi import materials
from armi.reactor import composites
from armi.reactor import flags
from armi.bookkeeping.db import Database3
from armi.reactor import parameters
from armi.nucDirectory import nuclideBases


# ARMI does not configure its own application by default. This is mostly to catch issues
# involving calling code that requires the framework to be configured before that has
# explicitly taken place. An application should call `configure()` with its App class in
# order for ARMI to work properly
_app: Optional[apps.App] = None


def isStableReleaseVersion(version=None):
    """Determine if the version should be considered a stable release"""
    version = version or __version__
    return not "-" in version


def _registerUserPlugin(plugManager, userPluginName):
    """Register one individual user plugin by name."""
    try:
        pluginMod = importlib.import_module(userPluginName)
    except ImportError:
        runLog.error(
            f"The plugin `{userPluginName}` could not be imported. Verify it is installed "
            "in your current environment or adjust the active user plugins."
        )
        raise

    # Each plugin must have a constant called PLUGIN pointing to the plugin class.
    # This allows discoverability without being overly restrictive in class names
    try:
        plugManager.register(pluginMod.PLUGIN)
    except AttributeError:
        runLog.error(
            f"The plugin `{userPluginName}` does not have a PLUGIN constant defined. "
            "This constant is required in user plugins. Please adjust plugin."
        )
        raise


def disconnectAllHdfDBs():
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
    h5dbs = [db for db in gc.get_objects() if isinstance(db, Database3)]
    for db in h5dbs:
        db.close()


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
    disconnectAllHdfDBs()

    if os.path.exists(FAST_PATH):
        if runLog.getVerbosity() <= runLog.getLogVerbosityRank("extra"):
            print(
                "Cleaning up temporary files in: {}".format(FAST_PATH), file=sys.stdout
            )
        try:
            shutil.rmtree(FAST_PATH)
        except Exception as error:  # pylint: disable=broad-except
            for outputStream in (sys.stderr, sys.stdout):
                print(
                    "Failed to delete temporary files in: {}\n"
                    "    error: {}".format(FAST_PATH, error),
                    file=outputStream,
                )

    # Also delete anything still here after `olderThanDays` days (in case this failed on
    # earlier runs)
    if olderThanDays is not None:
        gracePeriod = datetime.timedelta(days=olderThanDays)
        now = datetime.datetime.now()
        thisRunFolder = os.path.basename(FAST_PATH)

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
                    shutil.rmtree(dirPath)
            except:  # pylint: disable=bare-except
                pass


def init(choice=None, fName=None, cs=None):
    """
    Scan a directory for armi inputs and load one to interact with.

    Parameters
    ----------
    choice : int, optional
        Automatically run with this item out of the menu
        that would be produced of existing xml files.

    fName : str, optional
        An actual case name to load. e.g. ntTwr1.xml

    cs : object, optional
        If supplied, supercede the other case input methods and use the object directly

    Examples
    --------
    >>> o = armi.init()

    """
    from armi import cases
    from armi import settings

    if cs is None:
        if fName is None:
            fName = settings.promptForSettingsFile(choice)
        cs = settings.Settings(fName)
    # clear out any old masterCs objects
    settings.setMasterCs(cs)

    armiCase = cases.Case(cs=cs)
    armiCase.checkInputs()

    try:
        return armiCase.initializeOperator()
    except:  # Catch any and all errors. Naked exception on purpose.
        # Concatenate errors to the master log file.
        runLog.LOG.close()
        raise


def getDefaultPlugins() -> List[Type[plugins.ArmiPlugin]]:
    """
    Return a list containing the default set of ARMI Framework plugins.

    This is useful for an application to fold all of the ARMI Framework's capabilities
    into its own set of plugins.
    """
    from armi import cli
    from armi import bookkeeping
    from armi.physics import fuelCycle
    from armi.physics import neutronics
    from armi.physics import safety
    from armi import reactor

    defaultPlugins = [
        cli.EntryPointsPlugin,
        bookkeeping.BookkeepingPlugin,
        fuelCycle.FuelHandlerPlugin,
        neutronics.NeutronicsPlugin,
        safety.SafetyPlugin,
        reactor.ReactorPlugin,
    ]

    return defaultPlugins


def getDefaultPluginManager() -> pluggy.PluginManager:
    """
    Return a plugin manager containing the default set of ARMI Framework plugins.

    This is useful when using standalone facilities of ARMI without a specific
    application.
    """
    pm = plugins.getNewPluginManager()
    for plugin in getDefaultPlugins():
        pm.register(plugin)

    return pm


def isConfigured():
    """
    Returns whether ARMI has been configured with an App.
    """
    return _app is not None


def getPluginManager() -> Optional[pluggy.PluginManager]:
    """
    Return the plugin manager, if there is one.
    """
    global _app
    if _app is None:
        return None
    return _app.pluginManager


def getPluginManagerOrFail() -> pluggy.PluginManager:
    """
    Return the plugin manager. Raise an error if there is none.
    """
    global _app
    assert _app is not None, (
        "The ARMI plugin manager was requested, no App has been configured. Ensure "
        "that `armi.configure()` has been called before attempting to interact with "
        "the plugin manager."
    )

    return _app.pluginManager


def getApp() -> Optional[apps.App]:
    global _app
    return _app


def _cleanupOnCancel(signum, _frame):
    """Helper function to clean up upon cancellation."""
    print(
        "Caught Cancel signal ({}); cleaning temporary files and exiting..."
        "".format(signum),
        file=sys.stderr,
    )
    cleanTempDirs()
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(1)  # since we're handling the signal we have to cancel


def configure(app: Optional[apps.App]=None):
    """
    Set the plugin manager for the Framework and configure internals to those plugins.

    Parameters
    ----------
    app :
        An :py:class:`armi.apps.App` instance with which the framework is to be
        configured. If it is not provided, then the default ARMI App will be used.

    Important
    ---------
    Since this affects the behavior of several modules at their import time, it is
    generally not safe to re-configure the ARMI framework once it has been configured.
    Therefore this will raise an ``AssertionError`` if such a re-configuration is
    attempted.

    Notes
    -----
    We are planning on encapsulating much of the global ARMI state that gets configured
    with an App into the App object itself (with some other things going into the Case
    object). This will provide a number of benefits, the main one being that it will
    become trivial to re-configure the framework, which is currently not possible.
    """
    assert not armi.context.BLUEPRINTS_IMPORTED, (
        "ARMI can no longer be configured after blueprints have been imported. "
        "Blueprints were imported from:\n{}".format(
            armi.context.BLUEPRINTS_IMPORT_CONTEXT
        )
    )

    app = app or apps.App()

    global _app
    _app = app

    pm = app.pluginManager
    armi.context.APP_NAME = app.name
    parameters.collectPluginParameters(pm)
    parameters.applyAllParameters()
    flags.registerPluginFlags(pm)
    if MPI_RANK == 0:
        runLog.raw(app.splashText)


# The ``atexit`` handler is like putting it in a finally after everything.
atexit.register(cleanTempDirs, olderThanDays=14)

# register cleanups upon HPC cancellations. Linux clusters will send a different signal.
# SIGBREAK doesn't exist on non-windows
# This actually doesn't work in mpi runs because MSMPI's mpiexec does not pass signals.
if os.name == "nt":
    signal.signal(signal.SIGBREAK, _cleanupOnCancel)  # pylint: disable=no-member
signal.signal(signal.SIGINT, _cleanupOnCancel)

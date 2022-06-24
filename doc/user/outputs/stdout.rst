*******************
The Standard Output
*******************

The Standard Output (or **stdout**) is a running log of things an ARMI run prints out as it executes a case. It shows
what happened during a run, which inputs were used, which warnings were issued, and in some cases, what the summary
results are.  Here is an excerpt::

        ===========  Completed BOL Event ===========

        ===========  Triggering BOC - cycle 0 Event ===========
        =========== 01 - main                           BOC - cycle 0   ===========
        [impt] Beginning of Cycle 0
        =========== 02 - fissionProducts                BOC - cycle 0   ===========
        =========== 03 - xsGroups                       BOC - cycle 0   ===========
        [xtra] Generating representative blocks for XS
        [xtra] Cross section group manager summary

In a standard run, the various interfaces will loop through and print out messages according to the `verbosity`
setting. In multi-processing runs, the **stdout** shows messages from the primary node first and then shows information
from all other nodes below (with verbosity set by the `branchVerbosity` setting). Sometimes a user will want to set the
verbosity of just one module (.py file) in the code higher than the rest of ARMI, to do so they can set up a custom
logger by placing this line at the top of the file::

    runLog = logging.getLogger(__name__)

These single-module (file) loggers can be controlled using a the `moduleVerbosity` setting. All of these logger
verbosities can be controlled from the settings file, for example::

    branchVerbosity: debug
    moduleVerbosity:
        armi.reactor.reactors: info
    verbosity: extra

If there is an error, a useful message may be printed in the **stdout**, and a full traceback will be provided in the
associated **stderr** file.

Some Linux users tend to use the **tail** command to monitor the progress of an ARMI run::

    tail -f myRun.stdout

This provides live information on the progress.


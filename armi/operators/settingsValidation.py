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
A system to check user settings for validity and provide users with meaningful suggestions to fix.

This allows developers to specify a rich set of rules and suggestions for user settings.
These then pop up during initialization of a run, either on the command line or as
dialogues in the GUI. They say things like: "Your ___ setting has the value ___, which
is impossible. Would you like to switch to ___?"

"""
import os

import armi
from armi import runLog, settings, utils
from armi.utils import pathTools
from armi.reactor import geometry
from armi.reactor import systemLayoutInput
from armi.physics import neutronics
from armi.utils import directoryChangers
from armi.settings.fwSettings import globalSettings
from armi.settings.settingsIO import (
    prompt,
    RunLogPromptCancel,
    RunLogPromptUnresolvable,
)


class Query:
    """An individual query."""

    def __init__(self, condition, statement, question, correction):
        """
        Construct a query.

        Parameters
        ----------
        condition : callable
            A callable that returns True or False. If True,
            then the query activates its question and potential correction.
        statement : str
            A statement of the problem indicated by a True condition
        question : str
            A question asking the user for confirmation of the proposed
            fix.
        correction : callable
            A callable that when called fixes the situation. See
            :py:meth:`Inspector.NO_ACTION` for no-ops.
        """
        self.condition = condition
        self.statement = statement
        self.question = question
        self.correction = correction
        # True if the query is `passed` and does not result in an immediate failure
        self._passed = False
        self._corrected = False
        self.autoResolved = True

    def __repr__(self):
        # Add representation so that it's possible to identify which one
        # is being referred to when there are errors.
        return "<Query: {}>".format(self.statement)

    def __bool__(self):
        try:
            return bool(self.condition())
        except TypeError:
            runLog.error(
                f"Invalid setting validation query. Update validator for: {self})"
            )
            raise

    __nonzero__ = __bool__  # Python2 compatibility

    def isCorrective(self):
        return self.correction is not Inspector.NO_ACTION

    def resolve(self):
        """Standard i/o prompt for resolution of an individual query"""
        if armi.MPI_RANK != 0:
            return

        if self.condition():
            try:
                if self.isCorrective():
                    try:
                        make_correction = prompt(
                            "INSPECTOR: " + self.statement,
                            self.question,
                            "YES_NO",
                            "NO_DEFAULT",
                            "CANCEL",
                        )
                        if make_correction:
                            self.correction()
                            self._corrected = True
                        else:
                            self._passed = True
                    except RunLogPromptCancel as ki:
                        raise KeyboardInterrupt from ki
                else:
                    try:
                        continue_submission = prompt(
                            "INSPECTOR: " + self.statement,
                            "Continue?",
                            "YES_NO",
                            "NO_DEFAULT",
                            "CANCEL",
                        )
                        if not continue_submission:
                            raise KeyboardInterrupt
                    except RunLogPromptCancel as ki:
                        raise KeyboardInterrupt from ki

            except RunLogPromptUnresolvable:
                self.autoResolved = False
                self._passed = True


class Inspector:
    """
    This manages queries which assert certain states of the data model, generally presenting
    themselves to the user, offering information on the potential problem, a question
    and the action to take on an affirmative and negative answer from the user.

    In practice very useful for making sure setting values are as intended and without
    bad interplay with one another.

    One Inspector will contain multiple Queries and be associated directly with an
    :py:class:`~armi.operators.operator.Operator`.
    """

    @staticmethod
    def NO_ACTION():  # pylint: disable=invalid-name
        """Convenience callable used to generate Queries that can't be easily auto-resolved."""
        return None

    def __init__(self, cs):
        """
        Construct an inspector.

        Parameters
        ----------
        cs : Settings
        """
        self.queries = []
        self.cs = cs
        self.geomType = None
        self.coreSymmetry = None
        self._inspectBlueprints()
        self._setGeomType()
        self._inspectSettings()

        # Gather and attach validators from all plugins
        # This runs on all registered plugins, not just active ones.
        pluginQueries = armi.getPluginManagerOrFail().hook.defineSettingsValidators(
            inspector=self
        )
        for queries in pluginQueries:
            self.queries.extend(queries)

    def run(self, cs=None):
        """
        Run through each query and deal with it if possible.

        Returns
        -------
        correctionsMade : bool
            Whether or not anything was updated.

        Raises
        ------
        RuntimeError
            When a programming error causes queries to loop.
        """
        if armi.MPI_RANK != 0:
            return False

        # the following attribute changes will alter what the queries investigate when
        # resolved
        correctionsMade = False
        self.cs = cs or self.cs
        runLog.debug("{} executing queries.".format(self.__class__.__name__))
        if not any(self.queries):
            runLog.debug(
                "{} found no problems with the current state.".format(
                    self.__class__.__name__
                )
            )
        else:
            for query in self.queries:
                query.resolve()
                if query._corrected:  # pylint: disable=protected-access
                    correctionsMade = True
            issues = [
                query
                for query in self.queries
                if query
                and (
                    query.isCorrective() and not query._passed
                )  # pylint: disable=protected-access
            ]
            if any(issues):
                # something isn't resolved or was unresolved by changes
                raise RuntimeError(
                    "The input inspection did not resolve all queries, "
                    "some issues are creating cyclic resolutions: {}".format(issues)
                )
            runLog.debug("{} has finished querying.".format(self.__class__.__name__))
        return correctionsMade

    def addQuery(self, condition, statement, question, correction):
        """Convenience method, query must be resolved, else run fails"""
        if not callable(correction):
            raise ValueError(
                'Query for "{}" malformed. Expecting callable.'.format(statement)
            )
        self.queries.append(Query(condition, statement, question, correction))

    def addQueryBadLocationWillLikelyFail(self, settingName):
        """Add a query indicating the current path for ``settingName`` does not exist and will likely fail."""
        self.addQuery(
            lambda: not os.path.exists(pathTools.armiAbsPath(self.cs[settingName])),
            "Setting {} points to nonexistent location\n{}\nFailure extremely likely".format(
                settingName, self.cs[settingName]
            ),
            "",
            self.NO_ACTION,
        )

    def addQueryCurrentSettingMayNotSupportFeatures(self, settingName):
        """Add a query that the current value for ``settingName`` may not support certain features."""
        self.addQuery(
            lambda: self.cs[settingName] != self.cs.getSetting(settingName).default,
            "{} set as:\n{}\nUsing this location instead of the default location\n{}\n"
            "may not support certain functions.".format(
                settingName,
                self.cs[settingName],
                self.cs.getSetting(settingName).default,
            ),
            "Revert to default location?",
            lambda: self._assignCS(
                settingName, self.cs.getSetting(settingName).default
            ),
        )

    def _assignCS(self, key, value):
        """Lambda assignment workaround"""
        # this type of assignment works, but be mindful of
        # scoping when trying different methods
        self.cs[key] = value

    def _raise(self):  # pylint: disable=no-self-use
        raise KeyboardInterrupt("Input inspection has been interrupted.")

    def _inspectBlueprints(self):
        """Blueprints early error detection and old format conversions."""
        from armi.reactor import blueprints

        self.addQuery(
            lambda: not self.cs["loadingFile"],
            "No blueprints file loaded. Run will probably fail.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: not self._csRelativePathExists(self.cs["loadingFile"]),
            "Blueprints file {} not found. Run will fail.".format(
                self.cs["loadingFile"]
            ),
            "",
            self.NO_ACTION,
        )

    def _csRelativePathExists(self, filename):
        csRelativePath = self._csRelativePath(filename)
        return os.path.exists(csRelativePath) and os.path.isfile(csRelativePath)

    def _csRelativePath(self, filename):
        return os.path.join(self.cs.inputDirectory, filename)

    def _setGeomType(self):
        if self.cs["geomFile"]:
            with directoryChangers.DirectoryChanger(
                self.cs.inputDirectory, dumpOnException=False
            ):
                geom = systemLayoutInput.SystemLayoutInput()
                geom.readGeomFromFile(self.cs["geomFile"])

            self.geomType, self.coreSymmetry = geom.geomType, geom.symmetry

    def _inspectSettings(self):
        """Check settings for inconsistencies."""
        # import here to avoid cyclic issues
        from armi import operators

        self.addQuery(
            lambda: self.cs.path.endswith(".xml"),
            "Your settings were loaded from a XML file. These are being converted to yaml files.",
            "Would you like to auto-convert it to YAML?",
            lambda: settings.convertSettingsFromXMLToYaml(self.cs),
        )

        self.addQueryBadLocationWillLikelyFail("operatorLocation")

        self.addQuery(
            lambda: self.cs["outputFileExtension"] == "pdf" and self.cs["genReports"],
            "Output files of '.pdf' format are not supported by the reporting HTML generator. '.pdf' "
            "images will not be included.",
            "Switch to '.png'?",
            lambda: self._assignCS("outputFileExtension", "png"),
        )

        self.addQuery(
            lambda: (
                self.cs[globalSettings.CONF_ZONING_STRATEGY] == "manual"
                and not self.cs["zoneDefinitions"]
            ),
            "`manual` zoningStrategy requires that `zoneDefinitions` setting be defined. Run will have "
            "no zones.",
            "",
            self.NO_ACTION,
        )
        self.addQuery(
            lambda: (
                (
                    self.cs["beta"]
                    and isinstance(self.cs["beta"], list)
                    and not self.cs["decayConstants"]
                )
                or (self.cs["decayConstants"] and not self.cs["beta"])
            ),
            "Both beta components and decay constants should be provided if either are "
            "being supplied.",
            "",
            self.NO_ACTION,
        ),

        self.addQuery(
            lambda: self.cs["skipCycles"] > 0 and not self.cs["reloadDBName"],
            "You have chosen to do a restart case without specifying a database to load from. "
            "Run will load from output files, if they exist but burnup, etc. will not be updated.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["runType"] != operators.RunTypes.SNAPSHOTS
            and self.cs["loadStyle"] == "fromDB"
            and self.cs["startCycle"] == 0
            and self.cs["startNode"] == 0,
            "Starting from cycle 0, and time node 0 was chosen. Restart runs load from "
            "the time node just before the restart. There is no time node to load from "
            "before cycle 0 node 0. Either switch to the snapshot operator, start from "
            "a different time step or load from inputs rather than database as "
            "`loadStyle`.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["runType"] == operators.RunTypes.SNAPSHOTS
            and not (self.cs["dumpSnapshot"] or self.cs["defaultSnapshots"]),
            "The Snapshots operator was specified, but no dump snapshots were chosen."
            "Please specify snapshot steps with the `dumpSnapshot` setting.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs.caseTitle.lower()
            == os.path.splitext(os.path.basename(self.cs["reloadDBName"].lower()))[0],
            "Snapshot DB ({0}) and main DB ({1}) cannot have the same name."
            "Change name of settings file and resubmit.".format(
                self.cs["reloadDBName"], self.cs.caseTitle
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["reloadDBName"] != ""
            and not os.path.exists(self.cs["reloadDBName"]),
            "Reload database {} does not exist. \nPlease point to an existing DB, "
            "or set to empty and load from input.".format(self.cs["reloadDBName"]),
            "",
            self.NO_ACTION,
        )

        def _willBeCopiedFrom(fName):
            for copyFile in self.cs["copyFilesFrom"]:
                if fName == os.path.split(copyFile)[1]:
                    return True
            return False

        self.addQuery(
            lambda: self.cs["explicitRepeatShuffles"]
            and not self._csRelativePathExists(self.cs["explicitRepeatShuffles"])
            and not _willBeCopiedFrom(self.cs["explicitRepeatShuffles"]),
            "The specified repeat shuffle file `{0}` does not exist, and won't be copied from elsewhere. "
            "Run will crash.".format(self.cs["explicitRepeatShuffles"]),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: not self.cs["power"],
            "No power level set. You must always start by importing a base settings file.",
            "",
            self.NO_ACTION,
        )

        # The gamma cross sections generated for MC2-3 by ANL were done with NJOY with
        # P3 scattering. MC2-3 would have to be modified and the gamma cross sections
        # re-generated with NJOY for MC2-3 to allow any other scattering order with
        # gamma cross sections enabled.
        self.addQuery(
            lambda: (
                "MC2v3" in self.cs["xsKernel"]
                and neutronics.gammaXsAreRequested(self.cs)
                and self.cs["xsScatteringOrder"] != 3
            ),
            "MC2-3 will crash if a scattering order is not set to 3 when generating gamma XS.",
            "Would you like to set the `xsScatteringOrder` to 3?",
            lambda: self._assignCS("xsScatteringOrder", 3),
        )

        self.addQuery(
            lambda: self.cs["outputCacheLocation"]
            and not os.path.exists(self.cs["outputCacheLocation"]),
            "`outputCacheLocation` path {} does not exist. Please specify a location that exists.".format(
                self.cs["outputCacheLocation"]
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["numCoupledIterations"] > 0,
            "You have {0} coupling iterations selected.".format(
                self.cs["numCoupledIterations"]
            ),
            "1 coupling iteration doubles run time (2 triples, etc). Do you want to use 0 instead? ",
            lambda: self._assignCS("numCoupledIterations", 0),
        )

        def _factorsAreValid(factors, maxVal=1.0):
            try:
                expandedList = utils.expandRepeatedFloats(factors)
            except (ValueError, IndexError):
                return False
            return (
                all(0.0 <= val <= maxVal for val in expandedList)
                and len(expandedList) == self.cs["nCycles"]
            )

        self.addQuery(
            lambda: self.cs["availabilityFactors"]
            and not _factorsAreValid(self.cs["availabilityFactors"]),
            "`availabilityFactors` was not set to a list compatible with the number of cycles. "
            "Please update input or use constant duration.",
            "Use constant availability factor specified in `availabilityFactor` setting?",
            lambda: self._assignCS("availabilityFactors", []),
        )

        self.addQuery(
            lambda: self.cs["powerFractions"]
            and not _factorsAreValid(self.cs["powerFractions"]),
            "`powerFractions` was not set to a compatible list. "
            "Please update input or use full power at all cycles.",
            "Use full power for all cycles?",
            lambda: self._assignCS("powerFractions", []),
        )

        self.addQuery(
            lambda: (
                self.cs["cycleLengths"]
                and not _factorsAreValid(self.cs["cycleLengths"], maxVal=1e10)
            ),
            "The number of cycles defined in `cycleLengths` is not equal to the number of cycles in "
            "the run `nCycles`."
            "Please ensure that there is exactly one duration for each cycle in the run or use "
            "{} days for all cycles.".format(self.cs["cycleLength"]),
            "Use {} days for all cycles?".format(self.cs["cycleLength"]),
            lambda: self._assignCS("cycleLengths", []),
        )

        def _correctCycles():
            newSettings = {"nCycles": 1, "burnSteps": 0}
            self.cs = self.cs.modified(newSettings=newSettings)

        self.addQuery(
            lambda: not self.cs["cycleLengths"] and self.cs["nCycles"] == 0,
            "Cannot run 0 cycles. Set burnSteps to 0 to activate a single time-independent case.",
            "Set 1 cycle and 0 burnSteps for single time-independent case?",
            _correctCycles,
        )

        self.addQuery(
            lambda: (
                self.cs["runType"] == "Standard"
                and self.cs["burnSteps"] == 0
                and (len(self.cs["cycleLengths"]) > 1 or self.cs["nCycles"] > 1)
            ),
            "Cannot run multi-cycle standard cases with 0 burnSteps per cycle. Please update settings.",
            "",
            self.NO_ACTION,
        )

        def decayCyclesHaveInputThatWillBeIgnored():
            """Check if there is any decay-related input that will be ignored."""
            try:
                powerFracs = utils.expandRepeatedFloats(self.cs["powerFractions"])
                availabilities = utils.expandRepeatedFloats(
                    self.cs["availabilityFactors"]
                ) or ([self.cs["availabilityFactor"]] * self.cs["nCycles"])
            except:  # pylint: disable=bare-except
                return True

            for pf, af in zip(powerFracs, availabilities):
                if pf > 0.0 and af == 0.0:
                    # this will be a full decay step and any power fraction will be ignored. May be ok, but warn.
                    return True
            return False

        self.addQuery(
            lambda: (
                self.cs["cycleLengths"]
                and self.cs["powerFractions"]
                and decayCyclesHaveInputThatWillBeIgnored()
            ),
            "At least one cycle has a non-zero power fraction but an availability of zero. Please "
            "update the input.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["operatorLocation"]
            and self.cs["runType"] != operators.RunTypes.STANDARD,
            "The `runType` setting is set to `{0}` but there is a `custom operator location` defined".format(
                self.cs["runType"]
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["operatorLocation"]
            and self.cs["runType"] != operators.RunTypes.STANDARD,
            "The `runType` setting is set to `{0}` but there is a `custom operator location` defined".format(
                self.cs["runType"]
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["skipCycles"] > 0
            and not os.path.exists(self.cs.caseTitle + ".restart.dat"),
            "This is a restart case, but the required restart file {0}.restart.dat is not found".format(
                self.cs.caseTitle
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["deferredInterfacesCycle"] > self.cs["nCycles"],
            "The deferred interface activation cycle exceeds set cycle occurrence. "
            "Interfaces will not be activated in this run!",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: (
                self.cs["boundaries"] != neutronics.GENERAL_BC
                and self.cs["bcCoefficient"]
            ),
            "General neutronic boundary condition was not selected, but `bcCoefficient` was defined. "
            "Please enable `Generalized` neutronic boundary condition or disable `bcCoefficient`.",
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["geomFile"]
            and str(self.geomType) not in geometry.VALID_GEOMETRY_TYPE,
            "{} is not a valid geometry Please update geom type on the geom file. "
            "Valid (case insensitive) geom types are: {}".format(
                self.geomType, geometry.VALID_GEOMETRY_TYPE
            ),
            "",
            self.NO_ACTION,
        )

        self.addQuery(
            lambda: self.cs["geomFile"]
            and not geometry.checkValidGeomSymmetryCombo(
                self.geomType, self.coreSymmetry
            ),
            "{}, {} is not a valid geometry and symmetry combination. Please update "
            "either geometry or symmetry on the geom file.".format(
                str(self.geomType), str(self.coreSymmetry)
            ),
            "",
            self.NO_ACTION,
        )


def createQueryRevertBadPathToDefault(inspector, settingName, initialLambda=None):
    """
    Return a query to revert a bad path to its default.

    Parameters
    ----------
    inspector: Inspector
        the inspector who's settings are being queried
    settingName: str
        name of the setting to inspect
    initialLambda: None or callable function
        If ``None``, the callable argument for :py:meth:`addQuery` is does the setting's path exist.
        If more complicated callable arguments are needed, they can be passed in as the ``initialLambda`` setting.

    """
    if initialLambda is None:
        initialLambda = lambda: (
            not os.path.exists(pathTools.armiAbsPath(inspector.cs[settingName]))
            and inspector.cs.getSetting(settingName).offDefault
        )  # solution is to revert to default

    query = Query(
        initialLambda,
        "Setting {} points to a nonexistent location:\n{}".format(
            settingName, inspector.cs[settingName]
        ),
        "Revert to default location?",
        inspector.cs.getSetting(settingName).revertToDefault,
    )
    return query

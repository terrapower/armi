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
The base ARMI App class.

This module defines the :py:class:`App` class, which is used to configure the ARMI
Framework for a specific application. An ``App`` implements a simple interface for
customizing much of the Framework's behavior.

.. admonition:: Historical Fun Fact

    This pattern is used by many frameworks as a way of encapsulating what would
    otherwise be global state. The ARMI Framework has historically made heavy use of
    global state (e.g., :py:mod:`armi.nucDirectory.nuclideBases`), and it will take
    quite a bit of effort to refactor the code to access such things through an App
    object. We are planning to do this, but for now this App class is somewhat
    rudimentary.
"""
from typing import Dict, Optional, Tuple, List
import collections

from armi import context, plugins, pluginManager, meta, settings
from armi.reactor import parameters
from armi.settings import Setting
from armi.settings import fwSettings


class App:
    """
    The main point of customization for the ARMI Framework.

    The App class is intended to be subclassed in order to customize the functionality
    and look-and-feel of the ARMI Framework for a specific use case. An App contains a
    plugin manager, which should be populated in ``__init__()`` with a collection of
    plugins that are deemed suitable for a given application, as well as other methods
    which provide further customization.

    The base App class is also a good place to expose some more convenient ways to get
    data out of the Plugin API; calling the ``pluggy`` hooks directly can sometimes be a
    pain, as the results returned by the individual plugins may need to be merged and/or
    checked for errors. Adding that logic here reduces boilerplate throughout the rest
    of the code.
    """

    name = "armi"
    """
    The program name of the app. This should be the actual name of the python entry
    point that loads the app, or the name of the module that contains the appropriate
    __main__ function. For example, if the app is expected to be invoked with ``python
    -m myapp``, ``name`` should be ``"myapp"``
    """

    def __init__(self):
        """
        This mostly initializes the default plugin manager. Subclasses are free to adopt
        this plugin manager and register more plugins of their own, or to throw it away
        and start from scratch if they do not wish to use the default Framework plugins.

        For a description of the things that an ARMI plugin can do, see the
        :py:mod:`armi.plugins` module.
        """
        from armi import cli
        from armi import bookkeeping
        from armi.physics import fuelCycle
        from armi.physics import fuelPerformance
        from armi.physics import neutronics
        from armi.physics import safety
        from armi.physics import thermalHydraulics
        from armi import reactor

        self._pm = plugins.getNewPluginManager()
        for plugin in (
            cli.EntryPointsPlugin,
            bookkeeping.BookkeepingPlugin,
            fuelCycle.FuelHandlerPlugin,
            fuelPerformance.FuelPerformancePlugin,
            neutronics.NeutronicsPlugin,
            safety.SafetyPlugin,
            thermalHydraulics.ThermalHydraulicsPlugin,
            reactor.ReactorPlugin,
        ):
            self._pm.register(plugin)

        self._paramRenames: Optional[Tuple[Dict[str, str], int]] = None

    @property
    def version(self) -> str:
        """Grab the version of this app (defaults to ARMI version).

        NOTE: This is designed to be over-ridable by Application developers.
        """
        return meta.__version__

    @property
    def pluginManager(self) -> pluginManager.ArmiPluginManager:
        """Return the App's PluginManager."""
        return self._pm

    def getSettings(self) -> Dict[str, Setting]:
        """
        Return a dictionary containing all Settings defined by the framework and all plugins.
        """
        # Start with framework settings
        settingDefs = {
            setting.name: setting for setting in fwSettings.getFrameworkSettings()
        }

        # The optionsCache stores options that may have come from a plugin before the
        # setting to which they apply. Whenever a new setting is added, we check to see
        # if there are any options in the cache, popping them out and adding them to the
        # setting.  If all plugins' settings have been processed and the cache is not
        # empty, that's an error, because a plugin must have provided options to a
        # setting that doesn't exist.
        optionsCache: Dict[str, List[settings.Option]] = collections.defaultdict(list)
        defaultsCache: Dict[str, settings.Default] = {}

        for pluginSettings in self._pm.hook.defineSettings():
            for pluginSetting in pluginSettings:
                if isinstance(pluginSetting, settings.Setting):
                    name = pluginSetting.name
                    if name in settingDefs:
                        raise ValueError(
                            f"The setting {pluginSetting.name} "
                            "already exists and cannot be redefined."
                        )
                    settingDefs[name] = pluginSetting
                    # handle when new setting has modifier in the cache (modifier loaded first)
                    if name in optionsCache:
                        settingDefs[name].addOptions(optionsCache.pop(name))
                    if name in defaultsCache:
                        settingDefs[name].changeDefault(defaultsCache.pop(name))
                elif isinstance(pluginSetting, settings.Option):
                    if pluginSetting.settingName in settingDefs:
                        # modifier loaded after setting, so just apply it (no cache needed)
                        settingDefs[pluginSetting.settingName].addOption(pluginSetting)
                    else:
                        # no setting yet, cache it and apply when it arrives
                        optionsCache[pluginSetting.settingName].append(pluginSetting)
                elif isinstance(pluginSetting, settings.Default):
                    if pluginSetting.settingName in settingDefs:
                        # modifier loaded after setting, so just apply it (no cache needed)
                        settingDefs[pluginSetting.settingName].changeDefault(
                            pluginSetting
                        )
                    else:
                        # no setting yet, cache it and apply when it arrives
                        defaultsCache[pluginSetting.settingName] = pluginSetting
                else:
                    raise TypeError(
                        "Invalid setting definition found: {} ({})".format(
                            pluginSetting, type(pluginSetting)
                        )
                    )

        if optionsCache:
            raise ValueError(
                "The following options were provided for settings that do "
                "not exist. Make sure that the set of active plugins is "
                "consistent.\n{}".format(optionsCache)
            )

        if defaultsCache:
            raise ValueError(
                "The following defaults were provided for settings that do "
                "not exist. Make sure that the set of active plugins is "
                "consistent.\n{}".format(defaultsCache)
            )

        return settingDefs

    def getParamRenames(self) -> Dict[str, str]:
        """
        Return the parameter renames from all registered plugins.

        This renders a merged dictionary containing all parameter renames from all of
        the registered plugins. It also performs simple error checking. The result of
        this operation is cached, since it is somewhat expensive to perform. If the App
        detects that its plugin manager's set of registered plugins has changed, the
        cache will be invalidated and recomputed.
        """
        cacheInvalid = False
        if self._paramRenames is not None:
            renames, counter = self._paramRenames
            if counter != self._pm.counter:
                cacheInvalid = True
        else:
            cacheInvalid = True

        if cacheInvalid:
            currentNames = {pd.name for pd in parameters.ALL_DEFINITIONS}

            renames = dict()
            for (
                pluginRenames
            ) in self._pm.hook.defineParameterRenames():  #  pylint: disable=no-member
                collisions = currentNames & pluginRenames.keys()
                if collisions:
                    raise plugins.PluginError(
                        "The following parameter renames from a plugin collide with "
                        "currently-defined parameters:\n{}".format(collisions)
                    )
                pluginCollisions = renames.keys() & pluginRenames.keys()
                if pluginCollisions:
                    raise plugins.PluginError(
                        "The following parameter renames are already defined by another "
                        "plugin:\n{}".format(pluginCollisions)
                    )
                renames.update(pluginRenames)
            self._paramRenames = renames, self._pm.counter
        return renames

    @property
    def splashText(self):
        """
        Return a textual splash screen.

        Specific applications will want to customize this, but by default the ARMI one
        is produced, with extra data on the App name and version, if available.
        """
        # typical ARMI splash text
        splash = r"""
+===================================================+
|            _      ____     __  __    ___          |
|           / \    |  _ \   |  \/  |  |_ _|         |
|          / _ \   | |_) |  | |\/| |   | |          |
|         / ___ \  |  _ <   | |  | |   | |          |
|        /_/   \_\ |_| \_\  |_|  |_|  |___|         |
|        Advanced  Reactor  Modeling Interface      |
|                                                   |
|                    version {0:10s}             |
|                                                   |""".format(
            meta.__version__
        )

        # add the name/version of the current App, if it's not the default
        if context.APP_NAME != "armi":
            # pylint: disable=import-outside-toplevel # avoid cyclic import
            from armi import getApp

            splash += r"""
|---------------------------------------------------|
|   {0:>17s} app version {1:10s}        |""".format(
                context.APP_NAME, getApp().version
            )

        # bottom border of the splash
        splash += r"""
+===================================================+
"""

        return splash

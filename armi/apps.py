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
from typing import Dict, Optional

from armi import plugins
from armi import meta
from armi.reactor import parameters


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
    of the code. Another place where such code could go would be an ARMI subclass of the
    ``pluggy.PluginManager`` class. For the time being, we are doing okay without having
    to specialize the PluginManager, and we already have an App class to work with, so
    this is a pretty good place. If at some point it makes sense to introduce stateful
    plugins, or a more specialized PluginManager, then these methods should be migrated
    there.
    """

    name = "ARMI"

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
        from armi import reactor

        self._pm = plugins.getNewPluginManager()
        for plugin in (
            cli.EntryPointsPlugin,
            bookkeeping.BookkeepingPlugin,
            fuelCycle.FuelHandlerPlugin,
            fuelPerformance.FuelPerformancePlugin,
            neutronics.NeutronicsPlugin,
            safety.SafetyPlugin,
            reactor.ReactorPlugin,
        ):
            self._pm.register(plugin)

        self._paramRenames: Optional[Dict[str, str]] = None

    @property
    def pluginManager(self):
        """
        Return the App's PluginManager.
        """
        return self._pm

    def getParamRenames(self) -> Dict[str, str]:
        """
        Return the parameter renames from all registered plugins.

        This renders a merged dictionary containing all parameter renames from all of
        the registered plugins. It also performs simple error checking.
        """
        if self._paramRenames is None:
            currentNames = {pd.name for pd in parameters.ALL_DEFINITIONS}

            renames: Dict[str, str] = dict()
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
            self._paramRenames = renames
        return self._paramRenames

    @property
    def splashText(self):
        """
        Return a textual splash screen.

        Specific applications will want to customize this, but by default the ARMI one
        is produced.
        """
        # Don't move the triple quotes from the beginning of the line
        return r"""
                       ---------------------------------------------------
                      |             _      ____     __  __    ___         |
                      |            / \    |  _ \   |  \/  |  |_ _|        |
                      |           / _ \   | |_) |  | |\/| |   | |         |
                      |          / ___ \  |  _ <   | |  | |   | |         |
                      |         /_/   \_\ |_| \_\  |_|  |_|  |___|        |
                      |         Advanced  Reactor  Modeling Interface     |
                       ---------------------------------------------------
                                      Version {0:10s}
""".format(
            meta.__version__
        )

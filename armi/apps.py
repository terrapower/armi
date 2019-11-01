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

from armi import plugins
from armi import meta


class App:
    """
    The main point of customization for the ARMI Framework.

    The App class is intended to be subclassed in order to customize the functionality
    and look-and-feel of the ARMI Framework for a specific use case.
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
        from armi.physics import neutronics
        from armi.physics import safety
        from armi import reactor

        self._pm = plugins.getNewPluginManager()
        for plugin in (
            cli.EntryPointsPlugin,
            bookkeeping.BookkeepingPlugin,
            fuelCycle.FuelHandlerPlugin,
            neutronics.NeutronicsPlugin,
            safety.SafetyPlugin,
            reactor.ReactorPlugin,
        ):
            self._pm.register(plugin)

    @property
    def pluginManager(self):
        """
        Return the App's PluginManager
        """
        return self._pm

    @property
    def splashText(self):
        """
        Return a textual splash screen.

        Specific applications will want to customize this, but by default the ARMI one
        is produced.
        """
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
        )  # Don't move the triple quotes from the beginning of the line

"""
Slightly customized version of the stock pluggy ``PluginManager``.
"""

import pluggy


class ArmiPluginManager(pluggy.PluginManager):
    """
    PluginManager implementation with ARMI-specific features.

    The main point of this subclass is to make it possible to detect when the plugin
    manager has been mutated, allowing for safe caching of expensive results derived
    from the set of registered plugins. This is done by exposing a counter that is
    incremented any time the set of registered plugins is modified. If a client caches
    any results derived from calling plugin hooks, caching this counter along with that
    data allows for cheaply testing that the cached results are still valid.
    """

    def __init__(self, *args, **kwargs):
        pluggy.PluginManager.__init__(self, *args, **kwargs)

        self._counter = 0

    @property
    def counter(self):
        return self._counter

    def register(self, *args, **kwargs):
        self._counter += 1
        pluggy.PluginManager.register(self, *args, **kwargs)

    def unregister(self, *args, **kwargs):
        self._counter += 1
        pluggy.PluginManager.unregister(self, *args, **kwargs)

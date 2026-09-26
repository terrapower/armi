# Copyright 2026 TerraPower, LLC
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

"""Temporary patches to the unmaintained ``yamlize`` package.

``yamlize`` 0.7.1 was last released in 2019 and is effectively unmaintained, but ARMI blueprints
still depend on it. This module holds the patches ARMI needs to keep it working against modern
``ruamel.yaml``, in one place, so that they can all be deleted in a single stroke once blueprints no
longer use ``yamlize``.

Importing this module applies the patches as a side effect. It is imported by
:py:mod:`armi.reactor.blueprints`, which every blueprints load goes through.

Warning
-------
Nothing in here is public API. Do not import it from outside the blueprints package.
"""

from ruamel.yaml import RoundTripLoader
from yamlize.round_trip_data import RoundTripData


def _applyMaxDepthShim():
    """Give ``RoundTripLoader`` the ``max_depth`` attribute that newer ruamel.yaml expects.

    ruamel.yaml 0.19.1 started reading ``max_depth`` off the loader during ``get_single_node()``,
    but yamlize 0.7.1 builds its loaders in a way that never sets it, so every yamlize load raises
    ``AttributeError: 'RoundTripLoader' object has no attribute 'max_depth'``. Supplying the default
    here covers every yamlize class in ARMI, not just ``Blueprints``.
    """
    if not hasattr(RoundTripLoader, "max_depth"):
        RoundTripLoader.max_depth = None


def _applyRoundTripDataKeyShim():
    """Stop yamlize from mixing up the round-trip metadata of values that merely hash alike.

    yamlize carries YAML formatting metadata (tag, quote/flow style, anchor, comments) across a
    load/dump cycle by stashing it in a dict on the parent container, and it keys that dict on
    ``hash(value)`` alone. In Python, ``hash`` collides across types for the values that show up
    constantly in blueprints::

        hash("") == hash(0.0) == hash(0) == hash(False) == 0
        hash(1) == hash(1.0) == hash(True) == 1

    So whenever two such values share a container, the second one to be dumped inherits the first
    one's metadata -- *including its YAML tag*. A material modification of
    ``["", 0.0, 0.0, ""]`` round trips to ``["", "0.0", "0.0", ""]``: the floats pick up the empty
    string's quote style and come back as strings on the next read. Other spellings of the same bug
    are ``[0, 0.0]`` -> ``[!!float '0', 0.0]`` and ``["a", 1.0, true]`` -> ``["a", !!bool '1.0',
    true]``.

    This was originally diagnosed as a ruamel.yaml regression, because it became visible when we
    picked up ruamel.yaml 0.19.1 (see ``streamCleaner``, removed alongside this shim). It is not.
    Plain ruamel.yaml round trips every one of those documents byte-for-byte on 0.19.1; the
    corruption only appears when the values are routed through yamlize's metadata cache.

    Including the type in the key separates the colliding values, which fixes every case ARMI has
    hit. Two *identical* values in one container still share an entry -- that is inherent to keying
    metadata by value rather than by node, and it goes away when blueprints stop using yamlize.
    """

    def getKey(self, key):
        try:
            hash(key)
        except TypeError:
            return type(key), id(key)

        return type(key), key

    # the method is name-mangled inside RoundTripData, hence the awkward attribute name
    RoundTripData._RoundTripData__get_key = getKey


_applyMaxDepthShim()
_applyRoundTripDataKeyShim()

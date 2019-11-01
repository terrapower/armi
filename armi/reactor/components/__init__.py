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
Components package contains components and shapes.

These objects hold the dimensions, temperatures, composition, and shape of reactor primitives.

.. _component-class-diagram:

.. pyreverse:: armi.reactor.components -A -k --ignore=componentParameters.py
    :align: center
    :alt: Component class diagram
    :width: 100%

    Class inheritance diagram for :py:mod:`armi.reactor.components`.

"""
from armi.reactor.components.component import *  # pylint: disable=wildcard-import
from armi.reactor.components.shapes import *  # pylint: disable=wildcard-import
from armi.reactor.components.basicShapes import *  # pylint: disable=wildcard-import
from armi.reactor.components.volumetricShapes import *  # pylint: disable=wildcard-import


def factory(shape, bcomps, kwargs):
    """
    Build a new component object.

    Parameters
    ---------
    shape : str
        lowercase string corresponding to the component type name

    bcomps : list(Component)
        list of "sibling" components. This list is used to find component links, which are of the form
        ``<name>.<dimension``.

    kwargs : dict
        dictionary of inputs for the Component subclass's ``__init__`` method.
    """
    try:
        class_ = ComponentType.TYPES[shape]
    except KeyError:
        raise ValueError(
            "Unrecognized component shape: '{}'\n"
            "Valid component names are {}".format(
                shape, ", ".join(ComponentType.TYPES.keys())
            )
        )

    _removeDimensionNameSpaces(kwargs)

    return class_(components=bcomps, **kwargs)


def _removeDimensionNameSpaces(attrs):
    """Some components use spacing in their dimension names, but can't internally."""
    for key in list(attrs.keys()):
        if " " in key:
            clean = key.replace(" ", "_")
            attrs[clean] = attrs.pop(key)

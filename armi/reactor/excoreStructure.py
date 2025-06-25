# Copyright 2024 TerraPower, LLC
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
"""This module provides the simplest base-class tools for representing reactor objects that are
outside the reactor core.

The idea here is that all ex-core objects will be represented first as a spatial grid, and then
arbitrary ArmiObjects can be added to that grid.
"""

import copy

from armi.reactor.composites import Composite


class ExcoreStructure(Composite):
    """This is meant as the simplest baseclass needed to represent an ex-core reactor thing.

    An ex-core structure is expected to:

    - be a child of the Reactor,
    - have a grid associated with it,
    - contain a hierarchical set of ArmiObjects.
    """

    def __init__(self, name, parent=None):
        Composite.__init__(self, name)
        self.parent = parent
        self.spatialGrid = None

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

    @property
    def r(self):
        return self.getAncestor(fn=lambda x: x.__class__.__name__ == "Reactor")

    def add(self, obj, loc=None):
        """Add an ArmiObject to a particular grid location, in this structure.

        Parameters
        ----------
        assem : ArmiObject
            Any generic ArmiObject to add to the structure.
        loc : LocationBase, optional
            The location on this structure's grid. If omitted, will come from the object.
        """
        # if a location is not provided, we demand the object has one
        if loc is None:
            loc = obj.spatialLocator

        if loc.grid is not self.spatialGrid:
            raise ValueError(f"An Composite cannot be added to {self} using a spatial locator from another grid.")

        # If an assembly is added and it has a negative ID, that is a placeholder, fix it.
        if "assemNum" in obj.p and obj.p.assemNum < 0:
            # update the assembly count in the Reactor
            newNum = self.r.incrementAssemNum()
            obj.renumber(newNum)

        obj.spatialLocator = loc
        super().add(obj)


class ExcoreCollection(dict):
    """
    A collection that allows ex-core structures to be accessed like a dict, or class attributes.

    Examples
    --------
    Build some sample data::

        >>> sfp = ExcoreStructure("sfp")
        >>> ivs = ExcoreStructure("ivs")

    Build THIS collection::

        >>> excore = ExcoreCollection()

    Now you can add data to this collection like it were a dictionary, and access freely::

        >>> excore["sfp"] = sfp
        >>> excore["sfp"]
        <ExcoreStructure: sfp id:2311582653024>
        >>> excore.sfp
        <ExcoreStructure: sfp id:2311582653024>

    Or you can add data as if it were a class attribute, and still have dual access::

        >>> excore.ivs = ivs
        >>> excore.ivs
        <ExcoreStructure: ivs id:2311590971136>
        >>> excore["ivs"]
        <ExcoreStructure: ivs id:2311590971136>
    """

    def __getattr__(self, key):
        """Override the class attribute getter.

        First check if the class attribute exists. If not, check if the key is in the dictionary.
        """
        try:
            # try to get a real class attribute
            return self.__dict__[key]
        except KeyError:
            try:
                # if it's not a class attribute, maybe it is a dictionary key?
                return self.__getitem__(key)
            except Exception:
                pass
            # it is neither, just raise the usual error
            raise

    def __setattr__(self, key, value):
        """Override the class attribute setting.

        If the value has an ExcoreStructure type, assume we want to store this in the dictionary.
        """
        if type(value) is ExcoreStructure:
            self.__setitem__(key, value)
        else:
            self.__dict__[key] = value

    def __getstate__(self):
        """Needed to support pickling and unpickling the Reactor."""
        return self.__dict__.copy()

    def __setstate__(self, state):
        """Needed to support pickling and unpickling the Reactor."""
        self.__dict__.update(state)

    def __deepcopy__(self, memo):
        """Needed to support pickling and unpickling the Reactor."""
        memo[id(self)] = newE = self.__class__.__new__(self.__class__)
        newE.__setstate__(copy.deepcopy(self.__getstate__(), memo))
        return newE

    def __repr__(self):
        return "<{}: {} id:{}>".format(self.__class__.__name__, self.name, id(self))

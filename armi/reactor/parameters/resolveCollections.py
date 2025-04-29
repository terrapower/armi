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
This module contains the magic that makes the Parameter system and ARMI composite model
play nicely together.

The contained metaclass is useful for maintaining a hierarchy of ``ParameterCollection``
classes, which mimic the hierarchy of ``ArmiObject`` s to which they apply. Some
``ArmiObject`` subclasses define their own parameters, while others do not, so we do not
want to blindly create a ``ParameterCollectionClass`` for each ``ArmiObject`` subclass.
Instead, we want to be able to skip generations when no additional parameters were
requested for that level. For instance if we have a hierarchy like: ``ArmiObject`` <-
``A`` <- ``B``, where ``ArmiObject`` and ``B`` define parameters, while ``A`` does not
define any parameters of its own, we want to have a ``ArmiObjectParameterCollection``
and a ``BParameterCollection`` (with ``BParameterCollection`` being a subclass of
``ArmiObjectParameterCollection``).  ``ArmiObject`` and ``A`` will both *share* the
``ArmiObjectParameterCollection``, while ``B`` will use ``BParameterCollection``.
``BParameterCollection`` will contain all of the parameters defined in
``ArmiObjectParameterCollection``, plus whatever additional parameters were defined on
``B``.

The above scenario should behave rather intuitively for someone used to classes and
inheritance, but maintaining this hierarchy by hand would be onerous and error-prone.
What if one day we decide to add some parameters to ``A``? We need to remember to add a
new class for its parameters, and make sure to make ``BParameterCollection`` a subclass
of that new ``ParameterCollection`` class. With the below metaclass, we needn't worry
ourselves with any of that; it is taken care of automatically.

If you want to know how the sausage is made, the ``ResolveParametersMeta`` metaclass is
responsible for forming a hierarchy of ``ParameterCollection`` classes that correspond
to the related hierarchy of classes inheriting the root ``ArmiObject`` class. It should
be rare for an ARMI developer not engaged directly with Framework development to need to
know exactly how this works, but a proficient ARMI developer must keep in mind the
following rules about how this system behaves in practice:

* When defining subclasses of ``ArmiObject``, defining a class attribute called
  ``pDefs`` of the ``ParameterDefinitionCollection`` type signals to the system that
  this is a *Parameter Class*.
* When defining a *Parameter Class*, it will trigger the creation of a new
  ``ParameterCollection`` class, which will be derived from the
  ``ParameterCollection`` class of the most immediate *Parameter Class* ancestor
  the new class's inheritance tree.
* All classes derived from ``ArmiObject`` will receive an associated subclass of
  ``ParameterCollection``, which will ultimately include all of the relevant
  Parameters for that class. The specific class is the ``ParameterCollection``
  subclass defined for the most immediate *Parameter Class* in the classes
  inheritance tree.
* Parameter definitions can be added to a *Parameter Class*'s ``pDefs`` until
  Parameters have been "compiled" for it. After compiling parameters, the ``pDefs``
  are locked, and any attempts at defining additional parameters will cause an
  error.
* ``ArmiObject`` s cannot be instantiated until after parameters have been compiled.

"""

from armi.reactor.parameters.parameterCollections import ParameterCollection
from armi.reactor.parameters.parameterDefinitions import ParameterDefinitionCollection


class ResolveParametersMeta(type):
    """Metaclass for automatically defining associated ParameterCollection classes.

    Any class invoking this metaclass will automatically create an associated sub-class
    of the ``ParameterCollection`` type, if it has a class attribute called ``pDefs``
    that is an instance of ``ParameterDefinitionCollection``. This new class will itself
    be a subclass of the ``ParameterCollection`` class that is associated with the
    invoking class's parent.

    If no ``pDefs`` class attribute is present, the invoking class will adopt the
    ``ParameterCollection`` class associated with it's parent, or ``None`` if it cannot
    find one.

    The associated ``ParameterCollection`` will be stored on the new class's
    ``paramCollectionType`` attribute.

    For example, when this metaclass is applied to the ``Block`` class it will create a
    new class named ``BlockParameterCollection``, and add it as a class attribute called
    ``Block.paramCollectionType``. The ``BlockParameterCollection`` class will itself be
    a subclass of ``ArmiObjectParameterCollection``, which it would have found from the
    ``Composite`` class from which the ``Block`` class inherits. The ``Composite``
    class, on the other hand, would have obtained the ``ArmiObjectParameterCollection``
    from it's parent (``ArmiObject``), since it does not have a ``pDefs`` attribute of
    its own.
    """

    def __new__(mcl, name, bases, attrs):
        assert (
            attrs.get("paramCollectionType") is None
        ), "{} already has parameter collection".format(name)
        baseCollections = [
            b.paramCollectionType for b in bases if hasattr(b, "paramCollectionType")
        ]
        # Make sure that these are what we expect them to be
        assert all(
            [
                issubclass(c, ParameterCollection)
                for c in baseCollections
                if c is not None
            ]
        )

        # Make sure that we aren't doing some sort of multiple inheritance. We may
        # wish to support this in the future, but at this point we don't need it and
        # there are probably lots of snakes in that grass.
        # Turning this off to support multiple-inheritance materials/matprops material.
        # But we should still be careful.
        # assert len(baseCollections) <= 1, "Multiple inheritance is not yet supported in the ARMI composite pattern"

        # Pull out the one element of the list if it exists
        inferredBaseCollection = next(iter(baseCollections), None)

        # pDefs can be defined in the class definition; if it is, this is is a Parameter
        # Class!
        pDefs = attrs.get("pDefs")
        makeNewPC = pDefs is not None
        if makeNewPC:
            # We may have our own parameters, so we need to spin up a new
            # XParameterCollection class to store them.
            assert isinstance(pDefs, ParameterDefinitionCollection)

            collectionName = name + "ParameterCollection"
            collectionBase = inferredBaseCollection or ParameterCollection

            # Note that we also give a reference to the pDefs to the parameter
            # collection. This is so that the ParmameterCollection hierarchy can do all
            # of the parameter definitions work, while plugins can associate definitions
            # with the ArmiObjects
            paramCollectionType = type(
                collectionName,
                (collectionBase,),
                {
                    "pDefs": pDefs,
                },
            )
        else:
            # We will not be defining our own parameters, so we will defer to to those
            # of our parent classes if they have any
            paramCollectionType = inferredBaseCollection

        attrs["paramCollectionType"] = paramCollectionType

        nt = type.__new__(mcl, name, bases, attrs)
        if makeNewPC:
            paramCollectionType._ArmiObject = nt

        return nt

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

r"""
The parameters system holds state information for everything within ARMI's composite
structure:

.. list-table:: Example Parameters
    :widths: 50 50
    :header-rows: 1

    * - Object
      - Parameters
    * - :py:class:`~armi.reactor.reactors.Reactor`
      - :py:mod:`Reactor Parameters <armi.reactor.reactorParameters>`
    * - :py:class:`~armi.reactor.assemblies.Assembly`
      - :py:mod:`Assembly Parameters <armi.reactor.assemblyParameters>`
    * - :py:class:`~armi.reactor.blocks.Block`
      - :py:mod:`Block Parameters <armi.reactor.blockParameters>`
    * - :py:class:`~armi.reactor.components.Component`
      - :py:mod:`Component Parameters <armi.reactor.components.componentParameters>`

Basic Usage
===========
Given an ARMI reactor model object such as ``r``, one may set or get a parameter just
like any other instance attribute on ``r.p``::

    >>> r.p.cycleLength
    350.0

Alternatively, dictionary-like access is supported::

    >>> r.p["cycleLength"]
    350.0

.. note::

    The data themselves are stored in special hidden fields, which are typically
    accessed through the ``Parameter`` definition that describes them. The name for such
    a parameter field looks like ``"_p_" + paramName``. For example, to get
    ``cycleLength`` one could do::

        >>> r.core.p._p_cycleLength
        350.0

    However, it is not recommended to access parameters in this way, as it circumvents
    the setters and getters that may have been implemented for a given parameter. One
    should always use the style from the first two examples to access parameter values.

    Furthermore, ``ParameterCollection`` classes have some extra controls to make sure
    that someone doesn't try to set random extra attributes on them. Only parameters
    that were defined before a particular ``ParameterCollection`` class is instantiated
    may be accessed.The rationale behind this is documented in the Design
    Considerations section below.

Most parameters in ARMI are block parameters. These include flux, power, temperatures,
number densities, etc. Parameters can be any basic type (float, int, str), or an array
of any such types. The type within a given array should be homogeneous. Examples::

    >>> b.p.flux = 2.5e13
    >>> b.p.fuelTemp = numpy.array(range(217), dtype=float)
    >>> b.p.fuelTemp[58] = 600


.. note::

    There have been many discussions on what the specific name of this module/system
    should be. After great deliberation, the definition of parameter seemed very
    suitable:

        One of a set of measurable factors, such as temperature and pressure, that
        define a system and determine its behavior and are varied in an experiment ~
        `thefreedictionary`_

        any of a set of physical properties whose values determine the characteristics
        or behavior of something <parameters of the atmosphere such as temperature,
        pressure, and density> ~ `Meriam-Webster`_

The parameters system is composed of several classes:

:py:class:`~armi.reactor.parameters.parameterDefinitions.Parameter` :
    These store metadata about each parameter including the name, description, its
    units, etc. :py:class:`Parameters <parameterDefinitions.Parameter>` also define some
    behaviors such as setters/getters, and what to do when retrieving a value that has
    not been set, and whether or not to store the parameter in the database. The
    :py:class:`parameterDefinitions.Parameter` object implement the Python descriptor
    protocol (the magic behind ``@property``), and are stored on corresponding
    :py:class:`parameterCollections.ParameterCollection` classes to access their
    underlying values.

:py:class:`~armi.reactor.parameters.parameterDefinitions.ParameterDefinitionCollection` :
    As the name suggests, these represent a collection of parameter definitions. Each
    :py:class:`ParameterCollection` gets a :py:class:`ParameterDefinitionCollection`,
    and there are also module-global collections, such as ``ALL_DEFINITIONS``
    (containing all defined parameters over all ``ArmiObject`` classes), and others
    which break parameters down by their categories, associated composite types, etc.

:py:class:`~armi.reactor.parameters.parameterDefinitions.ParameterBuilder` :
    These are used to aid in the creation of :py:class:`Parameter` instances, and store
    default arguments to the :py:class:`Parameter` constructor.

:py:class:`~armi.reactor.parameters.parameterCollections.ParameterCollection` :
    These are used to store parameter values for a specific instance of an item in the
    ARMI composite structure, and have features for accessing those parameters and their
    definitions. The actual parameter values are stored in secret `"_p_"+paramName`
    fields, and accessed through the Parameter definition, which functions as a
    descriptor. Parameter definitions are stored as class attributes so that they can be
    shared amongst instances. All parameter fields are filled with an initial value in
    their ``__init__()`` to benefit from the split-key dictionaries introduced in
    PEP-412. This and protections to prevent setting any other attributes form a sort of
    "``__slots__`` lite".

:py:class:`~armi.reactor.parameters.resolveCollections.ResolveParametersMeta` :
    This metaclass is used by the base ``ArmiObject`` class to aid in the creation of a
    hierarchy of ``ParameterCollection`` classes that appropriately represent a specific
    ``ArmiObject`` subclass's parameters. In short, it looks at the class attributes of
    an ``ArmiObject`` subclass to see if there is a ``pDefs`` attribute (which should be
    an instance of ``ParameterDefinitionCollection``). If the ``pDefs`` attribute
    exists, the class will get its own ``ParameterCollection`` class, which will itself
    be a subclass of the parameter collection class associated with the most immediate
    ancestor that also had its own ``pDefs``. If an ``ArmiObject`` subclass has not
    ``pDefs`` attribute of its own, it will simply be associated with the parameter
    collection class of its parent.

This rather roundabout approach is used to address many of the design considerations
laid out below.  Namely that pains be taken to minimize memory consumption, properties
be used to control data access, and that it be relatively difficult to introduce
programming errors related to improperly-defined or colliding parameters.

Design Considerations
=====================

.. list-table:: Design considerations
    :header-rows: 1

    * - Issue
      - Resolution/Consequences
    * - Metadata about parameters is necessary for determining whether a parameter
        should be stored in the database, and to allow the user to toggle this switch.
      - Parameters must uniquely named within a ``Composite`` subclass.

        Also, we need to have :py:class:`Parameter` classes to store this metadata.
    * - There should not be any naming restrictions between different ``Composite`` subclasses.
      - Parameters must be defined or associated with a specific ``ParameterCollection`` subclass.
    * - PyLint cannot find programming errors related to incorrect strings.
      - We would like to use methods/functions for controlling state information.

        This also eliminated the possibility of using resource files to define the
        properties, otherwise we would be mapping names between some resource file and
        the associated parameter/property definition.
    * - Creating getters and setters for every parameter would be overwhelming and
        unsustainable.
      - We will use Python descriptors, which have *most* of the functionality used in
        getters and setters.

        :py:class:`ParameterCollection` knows how to generate descriptors for itself,
        based on a :py:class:`ParameterDefinitionCollection`.
    * - The majority of memory consumption occurs in parameters, strings and
        dictionaries.  Minimizing the storage requirements of the parameters is desirable.
      - Python ``__slots__`` are a language feature which eliminates the need for each
        class instance to have a ``__dict__``. This saves memory when there are many
        instances of a class. Slot access can sometimes be faster as well.

        In the past, ``__slots__`` were used to store parameter values. This became
        rather onerous when we wanted to support parameter definitions from plugins. We
        now use the traditional ``__dict__``, but take pains to make sure that we can
        get the memory savings from the key-sharing dicts provided by PEP-412. Namely,
        all attributes from the parameter definitions and other state are initialized to
        __something__ within the ``__init__()`` routine.
    * - Parameters are just fancy properties with meta data.
      - Implementing the descriptor interface on a :py:class:`Parameter` removes the
        need to construct a :py:class:`Parameter` without a name, then come back through
        with the ``applyParameters()`` class method to apply the
        :py:class:`Parameter` as a descriptor.

.. _thefreedictionary: http://www.thefreedictionary.com/parameter
.. _Meriam-Webster: http://www.merriam-webster.com/dictionary/parameter
"""

from armi.reactor.parameters.parameterCollections import (
    ParameterCollection,
    collectPluginParameters,
)
from armi.reactor.parameters.parameterCollections import applyAllParameters
from armi.reactor.parameters.parameterDefinitions import (
    ParameterDefinitionCollection,
    Parameter,
)

from armi.reactor.parameters.parameterDefinitions import (
    SINCE_INITIALIZATION,
    SINCE_LAST_DB_TRANSMISSION,
    SINCE_LAST_DISTRIBUTE_STATE,
    SINCE_LAST_GEOMETRY_TRANSFORMATION,
    SINCE_BACKUP,
    SINCE_ANYTHING,
    NEVER,
    Serializer,
    Category,
    ParamLocation,
    NoDefault,
    ALL_DEFINITIONS,
)

from armi.reactor.parameters.exceptions import (
    ParameterDefinitionError,
    ParameterError,
    UnknownParameterError,
)


forType = ALL_DEFINITIONS.forType
inCategory = ALL_DEFINITIONS.inCategory
byNameAndType = ALL_DEFINITIONS.byNameAndType
resetAssignmentFlag = ALL_DEFINITIONS.resetAssignmentFlag
since = ALL_DEFINITIONS.since


def reset():
    """Reset the status of all parameter definintions.

    This may become necessary when the state of the global parameter definitions becomes
    invalid.  Typically this happens when running multiple cases for the same import of
    this module, e.g. in unit tests. In this case things like the assigned flags will
    persist across test cases, leading to strange and incorrect behavior.
    """
    for pd in ALL_DEFINITIONS:
        pd.assigned = NEVER

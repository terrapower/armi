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
This module defines the ARMI input for a component definition, and code for constructing an ARMI
``Component``.

Special logic is required for handling component links.
"""

import yamlize

from armi import materials, runLog
from armi.nucDirectory import nuclideBases
from armi.reactor import components, composites
from armi.reactor.flags import Flags
from armi.utils import densityTools

COMPONENT_GROUP_SHAPE = "group"


class ComponentDimension(yamlize.Object):
    """
    Dummy object for ensuring well-formed component links are specified within the YAML input.

    This can be either a number (float or int), or a conformation string (``name.dimension``).
    """

    def __init__(self, value):
        # note: yamlizable does not call an __init__ method, instead it uses __new__ and setattr
        self.value = value
        if isinstance(value, str):
            if not components.COMPONENT_LINK_REGEX.search(value):
                raise ValueError("Bad component link `{}`, must be in form `name.dimension`".format(value))

    def __repr__(self):
        return "<ComponentDimension value: {}>".format(self.value)

    @classmethod
    def from_yaml(cls, loader, node, _rtd=None):
        """
        Override the ``Yamlizable.from_yaml`` to inject custom interpretation of component dimension.

        This allows us to create a new object with either a string or numeric value.
        """
        try:
            val = loader.construct_object(node)
            self = ComponentDimension(val)
            loader.constructed_objects[node] = self
            return self
        except ValueError as ve:
            raise yamlize.YamlizingError(str(ve), node)

    @classmethod
    def to_yaml(cls, dumper, self, _rtd=None):
        """
        Override the ``Yamlizable.to_yaml`` to remove the object-like behavior, otherwise we'd end
        up with a ``{value: ...}`` dictionary.

        This allows someone to programmatically edit the component dimensions without using the
        ``ComponentDimension`` class.
        """
        if not isinstance(self, cls):
            self = cls(self)
        node = dumper.represent_data(self.value)
        dumper.represented_objects[self] = node
        return node

    def __mul__(self, other):
        return self.value * other

    def __add__(self, other):
        return self.value + other

    def __div__(self, other):
        return self.value / other

    def __sub__(self, other):
        return self.value - other

    def __eq__(self, other):
        return self.value == other

    def __ne__(self, other):
        return self.value != other

    def __gt__(self, other):
        return self.value > other

    def __ge__(self, other):
        return self.value >= other

    def __lt__(self, other):
        return self.value < other

    def __le__(self, other):
        return self.value <= other

    def __hash__(self):
        return id(self)


class ComponentBlueprint(yamlize.Object):
    """
    This class defines the inputs necessary to build ARMI component objects. It uses ``yamlize`` to
    enable serialization to and from YAML.

    .. impl:: Construct component from blueprint file.
        :id: I_ARMI_BP_COMP
        :implements: R_ARMI_BP_COMP

        Defines a yaml construct that allows the user to specify attributes of a component from
        within their blueprints file, including a name, flags, shape, material and/or isotopic
        vector, input temperature, corresponding component dimensions, and ID for placement in a
        block lattice (see :py:class:`~armi.reactor.blueprints.blockBlueprint.BlockBlueprint`).
        Component dimensions that can be defined for a given component are dependent on the
        component's ``shape`` attribute, and the dimensions defining each shape can be found in the
        :py:mod:`~armi.reactor.components` module.

        Limited validation on the inputs is performed to ensure that the component shape corresponds
        to a valid shape defined by the ARMI application.

        Relies on the underlying infrastructure from the ``yamlize`` package for reading from text
        files, serialization, and internal storage of the data.

        Is implemented as part of a blueprints file by being imported and used as an attribute
        within the larger :py:class:`~armi.reactor.blueprints.Blueprints` class. Can also be used
        within the :py:class:`~armi.reactor.blueprints.blockBlueprint.BlockBlueprint` class to
        enable specification of components directly within the "blocks" portion of the blueprint
        file.

        Includes a ``construct`` method, which instantiates an instance of
        :py:class:`~armi.reactor.components.component.Component` with the characteristics specified
        in the blueprints (see :need:`I_ARMI_MAT_USER_INPUT1`).
    """

    name = yamlize.Attribute(type=str)
    flags = yamlize.Attribute(type=str, default=None)

    @name.validator
    def name(self, name):
        """Validate component names."""
        if name == "cladding":
            # many users were mixing cladding and clad and it caused issues downstream
            # where physics plugins checked for clad.
            raise ValueError(f"Cannot set ComponentBlueprint.name to {name}. Prefer 'clad'.")

    shape = yamlize.Attribute(type=str)

    @shape.validator
    def shape(self, shape):
        normalizedShape = shape.strip().lower()
        if normalizedShape not in components.ComponentType.TYPES and normalizedShape != COMPONENT_GROUP_SHAPE:
            raise ValueError(f"Cannot set ComponentBlueprint.shape to unknown shape: {shape}")

    material = yamlize.Attribute(type=str, default=None)
    Tinput = yamlize.Attribute(type=float, default=None)
    Thot = yamlize.Attribute(type=float, default=None)
    isotopics = yamlize.Attribute(type=str, default=None)
    latticeIDs = yamlize.Attribute(type=list, default=None)
    origin = yamlize.Attribute(type=list, default=None)
    orientation = yamlize.Attribute(type=str, default=None)
    mergeWith = yamlize.Attribute(type=str, default=None)
    area = yamlize.Attribute(type=float, default=None)

    def construct(self, blueprint, matMods, inputHeightsConsideredHot):
        """Construct a component or group.

        .. impl:: User-defined on material alterations are applied here.
            :id: I_ARMI_MAT_USER_INPUT1
            :implements: R_ARMI_MAT_USER_INPUT

            Allows for user input to impact a component's materials by applying
            the "material modifications" section of a blueprints file (see :need:`I_ARMI_MAT_USER_INPUT0`)
            to the material during construction. This takes place during lower
            calls to ``_conformKwargs()`` and subsequently ``_constructMaterial()``,
            which operate using the component blueprint and associated material
            modifications from the component's block.

            Within ``_constructMaterial()``, the material class is resolved into a material
            object by calling :py:func:`~armi.materials.resolveMaterialClassByName`.
            The ``applyInputParams()`` method of that material class is then called,
            passing in the associated material modifications data, which the material
            class can then use to modify the isotopics as necessary.

        Parameters
        ----------
        blueprint : Blueprints
            Blueprints object containing various detailed information, such as nuclides to model

        matMods : dict
            Material modifications to apply to the component.

        inputHeightsConsideredHot : bool
            See the case setting of the same name.
        """
        runLog.debug("Constructing component {}".format(self.name))
        kwargs = self._conformKwargs(blueprint, matMods)
        shape = self.shape.lower().strip()
        if shape == COMPONENT_GROUP_SHAPE:
            group = blueprint.componentGroups[self.name]
            constructedObject = composites.Composite(self.name)
            for groupedComponent in group:
                componentDesign = blueprint.componentDesigns[groupedComponent.name]
                component = componentDesign.construct(blueprint, {}, inputHeightsConsideredHot)
                # override free component multiplicity if it's set based on the group definition
                component.setDimension("mult", groupedComponent.mult)
                _setComponentFlags(component, self.flags, blueprint)
                insertDepletableNuclideKeys(component, blueprint)
                constructedObject.add(component)

        else:
            constructedObject = components.factory(shape, [], kwargs)
            _setComponentFlags(constructedObject, self.flags, blueprint)
            insertDepletableNuclideKeys(constructedObject, blueprint)
            constructedObject.p.theoreticalDensityFrac = constructedObject.material.getTD()

        self._setComponentCustomDensity(
            constructedObject,
            blueprint,
            matMods,
            inputHeightsConsideredHot,
        )

        return constructedObject

    def _setComponentCustomDensity(self, comp, blueprint, matMods, inputHeightsConsideredHot):
        """Apply a custom density to a material with custom isotopics but not a 'custom material'."""
        if self.isotopics is None:
            # No custom isotopics specified
            return

        densityFromCustomIsotopic = blueprint.customIsotopics[self.isotopics].density
        if densityFromCustomIsotopic is None:
            # Nothing to do
            return

        if densityFromCustomIsotopic <= 0:
            runLog.error(
                "A zero or negative density was specified in a custom isotopics input. "
                "This is not permitted, if a 0 density material is needed, use 'Void'. "
                f"The component is {comp} and the isotopics entry is {self.isotopics}."
            )
            raise ValueError("A zero or negative density was specified in the custom isotopics for a component")

        mat = materials.resolveMaterialClassByName(self.material)()
        if not isinstance(mat, materials.Custom):
            # check for some problem cases
            if "TD_frac" in matMods.keys():
                runLog.error(
                    f"Both TD_frac and a custom isotopic with density {blueprint.customIsotopics[self.isotopics]} "
                    f"has been specified for material {self.material}. This is an overspecification."
                )
            if not mat.density(Tc=self.Tinput) > 0:
                runLog.error(
                    f"A custom density has been assigned to material '{self.material}', which has no baseline "
                    "density. Only materials with a starting density may be assigned a density. "
                    "This comes up e.g. if isotopics are assigned to 'Void'."
                )
                raise ValueError("Cannot apply custom densities to materials without density.")

            # Apply a density scaling to account for the temperature change between
            # Tinput and Thot
            if isinstance(mat, materials.Fluid):
                densityRatio = densityFromCustomIsotopic / mat.density(Tc=comp.inputTemperatureInC)
            else:
                # for solids we need to consider if the input heights are hot or
                # cold, in order to get the density correct.
                # There may be a better place in the initialization to determine
                # if the block height will be interpreted as hot dimensions, which would
                # allow us to not have to pass the case settings down this far
                dLL = mat.linearExpansionFactor(Tc=comp.temperatureInC, T0=comp.inputTemperatureInC)
                if inputHeightsConsideredHot:
                    f = 1.0 / (1 + dLL) ** 2
                else:
                    f = 1.0 / (1 + dLL) ** 3

                scaledDensity = comp.density() / f
                densityRatio = densityFromCustomIsotopic / scaledDensity

            comp.changeNDensByFactor(densityRatio)

            runLog.important(
                "A custom material density was specified in the custom isotopics for non-custom "
                f"material {mat}. The component density has been altered to "
                f"{comp.density()} at temperature {comp.temperatureInC} C",
                single=True,
            )

    def _conformKwargs(self, blueprint, matMods):
        """This method gets the relevant kwargs to construct the component."""
        kwargs = {"mergeWith": self.mergeWith or "", "isotopics": self.isotopics or ""}

        for attr in self.attributes:  # yamlize magic
            val = attr.get_value(self)

            if attr.name == "shape" or val == attr.default:
                continue
            elif attr.name == "material":
                # value is a material instance
                value = self._constructMaterial(blueprint, matMods)
            elif attr.name == "latticeIDs":
                # Don't pass latticeIDs on to the component constructor.
                # They're applied during block construction.
                continue
            elif attr.name == "flags":
                # Don't pass these to the component constructor. These are used to
                # override the flags derived from the type, if present.
                continue
            else:
                value = attr.get_value(self)

            # Keep digging until the actual value is found. This is a bit of a hack to get around an
            # issue in yamlize/ComponentDimension where Dimensions can end up chained.
            while isinstance(value, ComponentDimension):
                value = value.value

            kwargs[attr.name] = value

        return kwargs

    def _constructMaterial(self, blueprint, matMods):
        nucsInProblem = blueprint.allNuclidesInProblem
        # make material with defaults
        mat = materials.resolveMaterialClassByName(self.material)()

        if self.isotopics is not None:
            # Apply custom isotopics before processing input mods so
            # the input mods have the final word
            blueprint.customIsotopics.apply(mat, self.isotopics)

        # add mass fraction custom isotopics info, since some material modifications need
        # to see them e.g. in the base Material.applyInputParams
        matMods.update({"customIsotopics": {k: v.massFracs for k, v in blueprint.customIsotopics.items()}})
        if len(matMods) > 1:
            # don't apply if only customIsotopics is in there
            try:
                # update material with updated input params from blueprints file.
                mat.applyInputParams(**matMods)
                # mat.blueprintMaterialMods = matMods
            except TypeError as ee:
                errorMessage = ee.args[0]
                if "got an unexpected keyword argument" in errorMessage:
                    # This component does not accept material modification inputs of the names passed in
                    # Keep going since the modification could work for another component
                    pass
                else:
                    raise ValueError(
                        f"Something went wrong in applying the material modifications {matMods} "
                        f"to component {self.name}.\n"
                        f"Error message is: \n{errorMessage}."
                    )

        expandElementals(mat, blueprint)

        missing = set(mat.massFrac.keys()).difference(nucsInProblem)

        if missing:
            raise ValueError(
                "The nuclides {} are present in material {} by compositions, but are not "
                "specified in the `nuclide flags` section of the input file. "
                "They need to be added, or custom isotopics need to be applied.".format(missing, mat)
            )

        return mat


def expandElementals(mat, blueprint):
    """
    Expand elements to isotopics during material construction.

    Does so as required by modeling options or user input.

    See Also
    --------
    armi.reactor.blueprints.Blueprints._resolveNuclides
        Sets the metadata defining this behavior.
    """
    elementExpansionPairs = []
    for elementToExpand in blueprint.elementsToExpand:
        if elementToExpand.symbol not in mat.massFrac:
            continue
        nucFlags = blueprint.nuclideFlags.get(elementToExpand.symbol)
        nuclidesToBecome = (
            [nuclideBases.byName[nn] for nn in nucFlags.expandTo] if (nucFlags and nucFlags.expandTo) else None
        )
        elementExpansionPairs.append((elementToExpand, nuclidesToBecome))

    densityTools.expandElementalMassFracsToNuclides(mat.massFrac, elementExpansionPairs)


def insertDepletableNuclideKeys(c, blueprint):
    """
    Auto update number density keys on all DEPLETABLE components.

    .. impl:: Insert any depletable blueprint flags onto this component.
        :id: I_ARMI_BP_NUC_FLAGS0
        :implements: R_ARMI_BP_NUC_FLAGS

        This is called during the component construction process for each component from within
        :py:meth:`~armi.reactor.blueprints.componentBlueprint.ComponentBlueprint.construct`.

        For a given initialized component, check its flags to determine if it has been marked as
        depletable. If it is, use
        :py:func:`~armi.nucDirectory.nuclideBases.initReachableActiveNuclidesThroughBurnChain` to
        apply the user-specifications in the "nuclide flags" section of the blueprints to the
        Component such that all active isotopes and derivatives of those isotopes in the burn chain
        are initialized to have an entry in the component's ``nuclides`` array.

        Note that certain case settings, including ``fpModel`` and ``fpModelLibrary``, may trigger
        modifications to the active nuclides specified by the user in the "nuclide flags" section of
        the blueprints.

    Notes
    -----
    This should be moved to a neutronics/depletion plugin hook but requires some refactoring in how
    active nuclides and reactors are initialized first.

    See Also
    --------
    armi.physics.neutronics.isotopicDepletion.isotopicDepletionInterface.isDepletable :
        contains design docs describing the ``DEPLETABLE`` flagging situation
    """
    if c.hasFlags(Flags.DEPLETABLE):
        # depletable components, whether auto-derived or explicitly flagged need expanded nucs
        (
            c.p.nuclides,
            c.p.numberDensities,
        ) = nuclideBases.initReachableActiveNuclidesThroughBurnChain(
            c.p.nuclides,
            c.p.numberDensities,
            blueprint.activeNuclides,
        )


class ComponentKeyedList(yamlize.KeyedList):
    """
    An OrderedDict of ComponentBlueprints keyed on the name.

    This is used within the ``components:`` main entry of the blueprints.

    This is *not* (yet) used when components are defined within a block blueprint. That is handled
    in the blockBlueprint construct method.
    """

    item_type = ComponentBlueprint
    key_attr = ComponentBlueprint.name


class GroupedComponent(yamlize.Object):
    """
    A pointer to a component with a multiplicity to be used in a ComponentGroup.

    Multiplicity can be a fraction (e.g. to set volume fractions)
    """

    name = yamlize.Attribute(type=str)
    mult = yamlize.Attribute(type=float)


class ComponentGroup(yamlize.KeyedList):
    """
    A single component group containing multiple GroupedComponents.

    Example
    -------
    triso:
      kernel:
        mult: 0.7
      buffer:
        mult: 0.3
    """

    group_name = yamlize.Attribute(type=str)
    key_attr = GroupedComponent.name
    item_type = GroupedComponent


class ComponentGroups(yamlize.KeyedList):
    """
    A list of component groups.

    This is used in the top-level blueprints file.
    """

    key_attr = ComponentGroup.group_name
    item_type = ComponentGroup


# This import-time magic requires all possible components
# be imported before this module imports. The intent
# was to make registration basically automatic. This has proven
# to be quite problematic and will be replaced with an
# explicit plugin-level component registration system.
for dimName in set([kw for cType in components.ComponentType.TYPES.values() for kw in cType.DIMENSION_NAMES]):
    setattr(
        ComponentBlueprint,
        dimName,
        yamlize.Attribute(name=dimName, type=ComponentDimension, default=None),
    )


def _setComponentFlags(component, flags, blueprint):
    """Update component flags based on user input in blueprint."""
    # the component __init__ calls setType(), which gives us our initial guess at
    # what the flags should be.
    if flags is not None:
        # override the flags from __init__ with the ones from the blueprint
        component.p.flags = Flags.fromString(flags)
    else:
        # potentially add the DEPLETABLE flag. Don't do this if we set flags
        # explicitly. WARNING: If you add flags explicitly, it will
        # turn off depletion so be sure to add depletable to your list of flags
        # if you expect depletion
        if any(nuc in blueprint.activeNuclides for nuc in component.getNuclides()):
            component.p.flags |= Flags.DEPLETABLE

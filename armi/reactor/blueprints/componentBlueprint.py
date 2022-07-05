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
This module defines the ARMI input for a component definition, and code for constructing an ARMI ``Component``.

Special logic is required for handling component links.
"""
import yamlize

from armi import runLog
from armi import materials
from armi.reactor import components
from armi.reactor import composites
from armi.reactor.flags import Flags
from armi.utils import densityTools
from armi.nucDirectory import nuclideBases

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
                raise ValueError(
                    "Bad component link `{}`, must be in form `name.dimension`".format(
                        value
                    )
                )

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
        Override the ``Yamlizable.to_yaml`` to remove the object-like behavior, otherwise we'd end up with a
        ``{value: ...}`` dictionary.

        This allows someone to programmatically edit the component dimensions without using the ``ComponentDimension``
        class.
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
    This class defines the inputs necessary to build ARMI component objects. It uses ``yamlize`` to enable serialization
    to and from YAML.
    """

    name = yamlize.Attribute(type=str)
    flags = yamlize.Attribute(type=str, default=None)

    @name.validator
    def name(self, name):  # pylint: disable=no-self-use; reason=yamlize requirement
        """Validate component names."""
        if name == "cladding":
            # many users were mixing cladding and clad and it caused issues downstream
            # where physics plugins checked for clad.
            raise ValueError(
                f"Cannot set ComponentBlueprint.name to {name}. Prefer 'clad'."
            )

    shape = yamlize.Attribute(type=str)

    @shape.validator
    def shape(self, shape):  # pylint: disable=no-self-use; reason=yamlize requirement
        normalizedShape = shape.strip().lower()
        if (
            normalizedShape not in components.ComponentType.TYPES
            and normalizedShape != COMPONENT_GROUP_SHAPE
        ):
            raise ValueError(
                f"Cannot set ComponentBlueprint.shape to unknown shape: {shape}"
            )

    material = yamlize.Attribute(type=str, default=None)
    Tinput = yamlize.Attribute(type=float, default=None)
    Thot = yamlize.Attribute(type=float, default=None)
    isotopics = yamlize.Attribute(type=str, default=None)
    latticeIDs = yamlize.Attribute(type=list, default=None)
    origin = yamlize.Attribute(type=list, default=None)
    blends = yamlize.Attribute(type=list, default=None)
    blendFracs = yamlize.Attribute(type=list, default=None)
    orientation = yamlize.Attribute(type=str, default=None)
    mergeWith = yamlize.Attribute(type=str, default=None)
    area = yamlize.Attribute(type=float, default=None)

    def construct(self, blueprint, matMods):
        """Construct a component or group"""
        runLog.debug("Constructing component {}".format(self.name))
        kwargs = self._conformKwargs(blueprint, matMods)
        shape = self.shape.lower().strip()
        if shape == COMPONENT_GROUP_SHAPE:
            group = blueprint.componentGroups[self.name]
            constructedObject = composites.Composite(self.name)
            for groupedComponent in group:
                componentDesign = blueprint.componentDesigns[groupedComponent.name]
                component = componentDesign.construct(blueprint, matMods=dict())
                # override free component multiplicity if it's set based on the group definition
                component.setDimension("mult", groupedComponent.mult)
                _setComponentFlags(component, self.flags, blueprint)
                insertDepletableNuclideKeys(component, blueprint)
                constructedObject.add(component)

        else:
            if self.blends:
                # build a blended object
                for groupName, blendFrac in zip(self.blends, self.blendFracs):
                    # blendFrac is a volume fraction, and so we need to adjust the multiplicities
                    # so that the background component and the child group match up
                    # The area of the background component will be fully determined by its dims and mult.
                    # but internally, its number densities and volumes need to be set to match
                    # the blendFrac
                    group = blueprint.componentGroups[groupName]
                    # strip off the blend/blendFrac args since they aren't valid on any
                    # specific shape's constructor
                    del kwargs["blends"]
                    del kwargs["blendFracs"]
                    # build the background object
                    constructedObject = components.factory(shape, [], kwargs)
                    # build the child objects
                    for groupedComponent in group:
                        componentDesign = blueprint.componentDesigns[
                            groupedComponent.name
                        ]
                        component = componentDesign.construct(blueprint, matMods=dict())
                        # temporarily set grouped component mults to the blend fraction
                        # these will be updated based on parent component volume
                        # during block construction
                        component.setDimension("mult", blendFrac)
                        _setComponentFlags(component, self.flags, blueprint)
                        insertDepletableNuclideKeys(component, blueprint)
                        constructedObject.add(component)
                    children = {c.name: c for c in constructedObject.getChildren()}
                    for child in children.values():
                        child.resolveLinkedDims(children)
            else:
                constructedObject = components.factory(shape, [], kwargs)
                _setComponentFlags(constructedObject, self.flags, blueprint)
                insertDepletableNuclideKeys(constructedObject, blueprint)
        return constructedObject

    def _conformKwargs(self, blueprint, matMods):
        """This method gets the relevant kwargs to construct the component"""
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
        matMods.update(
            {
                "customIsotopics": {
                    k: v.massFracs for k, v in blueprint.customIsotopics.items()
                }
            }
        )
        if len(matMods) > 1:
            # don't apply if only customIsotopics is in there
            try:
                # update material with updated input params from blueprints file.
                mat.applyInputParams(**matMods)
            except TypeError:
                # This component does not accept material modification inputs of the names passed in
                # Keep going since the modification could work for another component
                pass

        expandElementals(mat, blueprint)

        missing = set(mat.p.massFrac.keys()).difference(nucsInProblem)

        if missing:
            raise ValueError(
                "The nuclides {} are present in material {} by compositions, but are not "
                "specified in the `nuclide flags` section of the input file. "
                "They need to be added, or custom isotopics need to be applied.".format(
                    missing, mat
                )
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
        if elementToExpand.symbol not in mat.p.massFrac:
            continue
        nucFlags = blueprint.nuclideFlags.get(elementToExpand.symbol)
        nuclidesToBecome = (
            [nuclideBases.byName[nn] for nn in nucFlags.expandTo]
            if (nucFlags and nucFlags.expandTo)
            else None
        )
        elementExpansionPairs.append((elementToExpand, nuclidesToBecome))

    densityTools.expandElementalMassFracsToNuclides(
        mat.p.massFrac, elementExpansionPairs
    )


def insertDepletableNuclideKeys(c, blueprint):
    """
    Auto update number density keys on all DEPLETABLE components.

    Notes
    -----
    This should be moved to a neutronics/depletion plugin hook but requires some
    refactoring in how active nuclides and reactors are initialized first.

    See Also
    --------
    armi.physics.neutronics.isotopicDepletion.isotopicDepletionInterface.isDepletable :
        contains design docs describing the ``DEPLETABLE`` flagging situation
    """
    if c.hasFlags(Flags.DEPLETABLE):
        # depletable components, whether auto-derived or explicitly flagged need expanded nucs
        nuclideBases.initReachableActiveNuclidesThroughBurnChain(
            c.p.numberDensities, blueprint.activeNuclides
        )


class ComponentKeyedList(yamlize.KeyedList):
    """
    An OrderedDict of ComponentBlueprints keyed on the name.

    This is used within the ``components:`` main entry of the blueprints.

    This is *not* (yet) used when components are defined within a block blueprint.
    That is handled in the blockBlueprint construct method.
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
    A single component group containing multiple GroupedComponents

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
for dimName in set(
    [
        kw
        for cType in components.ComponentType.TYPES.values()
        for kw in cType.DIMENSION_NAMES
    ]
):
    setattr(
        ComponentBlueprint,
        dimName,
        yamlize.Attribute(name=dimName, type=ComponentDimension, default=None),
    )


def _setComponentFlags(component, flags, blueprint):
    """Update component flags based on user input in blueprint"""
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

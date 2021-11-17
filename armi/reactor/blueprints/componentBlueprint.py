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
from math import isclose, inf

import six
import yamlize

from armi import runLog
from armi import materials
from armi.reactor import components
from armi.reactor.flags import Flags
from armi.reactor.particleFuel import ParticleFuel
from armi.utils import densityTools
from armi.nucDirectory import nuclideBases, nucDir


class ComponentParticleFuel(yamlize.Object):
    specifier = yamlize.Attribute(type=str)
    packingFraction = yamlize.Attribute(type=float)

    @packingFraction.validator
    def packingFraction(self, packingFraction):
        if not 0 < packingFraction < 1:
            raise ValueError(
                "Packing fraction must be between 0 and 1, exclusive. Got "
                "{}".format(packingFraction)
            )


class ComponentDimension(yamlize.Object):
    """
    Dummy object for ensuring well-formed component links are specified within the YAML input.

    This can be either a number (float or int), or a conformation string (``name.dimension``).
    """

    def __init__(self, value):
        # note: yamlizable does not call an __init__ method, instead it uses __new__ and setattr
        self.value = value
        if isinstance(value, six.string_types):
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
        if name in {"cladding"}:
            raise ValueError("Cannot set ComponentBlueprint.name to {}".format(name))

    shape = yamlize.Attribute(type=str)

    @shape.validator
    def shape(self, shape):  # pylint: disable=no-self-use; reason=yamlize requirement
        normalizedShape = shape.strip().lower()
        if normalizedShape not in components.ComponentType.TYPES:
            raise ValueError("Cannot set ComponentBlueprint.shape to {}".format(shape))

    material = yamlize.Attribute(type=str)
    Tinput = yamlize.Attribute(type=float)
    Thot = yamlize.Attribute(type=float)
    isotopics = yamlize.Attribute(type=str, default=None)
    latticeIDs = yamlize.Attribute(type=list, default=None)
    origin = yamlize.Attribute(type=list, default=None)
    orientation = yamlize.Attribute(type=str, default=None)
    mergeWith = yamlize.Attribute(type=str, default=None)
    area = yamlize.Attribute(type=float, default=None)
    particleFuelSpec = yamlize.Attribute(type=str, default=None)
    particleFuelPackingFraction = yamlize.Attribute(type=float, default=None)

    def construct(self, blueprint, matMods):
        """Construct a component"""
        runLog.debug("Constructing component {}".format(self.name))
        kwargs = self._conformKwargs(blueprint, matMods)
        component = components.factory(self.shape.strip().lower(), [], kwargs)

        # the component __init__ calls setType(), which gives us our initial guess at
        # what the flags should be.
        if self.flags is not None:
            # override the flags from __init__ with the ones from the blueprint
            component.p.flags = Flags.fromString(self.flags)
        else:
            # potentially add the DEPLETABLE flag. Don't do this if we set flags
            # explicitly. WARNING: If you add flags explicitly, it will
            # turn off depletion so be sure to add depletable to your list of flags
            # if you expect depletion
            if any(nuc in blueprint.activeNuclides for nuc in component.getNuclides()):
                component.p.flags |= Flags.DEPLETABLE

        if component.hasFlags(Flags.DEPLETABLE):
            # depletable components, whether auto-derived or explicitly flagged need expanded nucs
            _insertDepletableNuclideKeys(component, blueprint)

        return component

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
            elif attr.name == "particleFuelSpec":
                design = blueprint.particleFuelDesigns[val]
                value = design.construct(blueprint, matMods)
            elif attr.name == "particleFuelPackingFraction":
                value = attr.get_value(self)
                if value <= 0 or value >= 1:
                    raise ValueError(
                        f"Packing fraction {value} not allowed: must be between "
                        "0 and 1 exclusive",
                    )
            else:
                value = attr.get_value(self)

            # Keep digging until the actual value is found. This is a bit of a hack to get around an
            # issue in yamlize/ComponentDimension where Dimensions can end up chained.
            while isinstance(value, ComponentDimension):
                value = value.value

            kwargs[attr.name] = value

        return kwargs

    def _constructMaterial(self, blueprint, matMods):
        return constructMaterial(self.material, blueprint, matMods, self.isotopics)


def constructMaterial(name, blueprint, matMods, isotopics):
    """Create a material from blueprint, applying material modifications as necessary

    Parameters
    ----------
    name : str
        Name of this material. ARMI must know how to resolve the material
        class given the string name
    blueprint : Blueprints
        Various detailed information, such as nuclides to model
    matMods : dict
        Material modifications to be applied to this material
    isotopics : dict or none
        Isotopics to apply to this material, if given. Must conform to
        ``custom isotopics`` blueprints specification.

    Returns
    -------
    armi.materials.Material

    Raises
    ------
    ValueError
        Nuclides found in the material aren't modelled in the ``nuclide flags``
        section of the blueprints problem

    """
    # make material with defaults
    mat = materials.resolveMaterialClassByName(name)()

    if isotopics is not None:
        # Apply custom isotopics before processing input mods so
        # the input mods have the final word
        blueprint.customIsotopics.apply(mat, isotopics)

    # add mass fraction custom isotopics info, since some material modifications need to see them
    # e.g. in the base Material.applyInputParams
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

    missing = set(mat.p.massFrac.keys()).difference(blueprint.allNuclidesInProblem)

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


def _insertDepletableNuclideKeys(c, blueprint):
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
    nuclideBases.initReachableActiveNuclidesThroughBurnChain(
        c.p.numberDensities, blueprint.activeNuclides
    )


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


class _ParticleFuelLayer(yamlize.Object):
    """Component-like specification for a single layer in particle fuel"""

    name = yamlize.Attribute(key="name", type=str)
    material = yamlize.Attribute(type=str)
    innerDiam = yamlize.Attribute(key="id", type=float, default=0)
    od = yamlize.Attribute(key="od", type=float)
    Tinput = yamlize.Attribute(type=float)
    Thot = yamlize.Attribute(type=float)
    # Need this to pick up flags like depletable
    flags = yamlize.Attribute(type=str, default=None)

    def construct(self, blueprint, matMods):
        """Construct a sphere and assign to a parent"""
        # Very similar to ComponentBlueprint.construct, maybe share?
        runLog.debug(f"Constructing particle fuel layer {self.name}")
        kwargs = self._conformKwargs(blueprint, matMods)
        component = components.factory("sphere", [], kwargs)

        # the component __init__ calls setType(), which gives us our initial guess at
        # what the flags should be.
        if self.flags is not None:
            # override the flags from __init__ with the ones from the blueprint
            component.p.flags = Flags.fromString(self.flags)
        else:
            # potentially add the DEPLETABLE flag. Don't do this if we set flags
            # explicitly. WARNING: If you add flags explicitly, it will
            # turn off depletion so be sure to add depletable to your list of flags
            # if you expect depletion
            if any(nuc in blueprint.activeNuclides for nuc in component.getNuclides()):
                component.p.flags |= Flags.DEPLETABLE

        if component.hasFlags(Flags.DEPLETABLE):
            # depletable components, whether auto-derived or explicitly flagged
            # need expanded nucs
            _insertDepletableNuclideKeys(component, blueprint)

        if any(nucDir.isHeavyMetal(nucName) for nucName in component.getNuclides()):
            component.p.flags |= Flags.FUEL

        return component

    def _conformKwargs(self, blueprint, matMods) -> dict:
        """Return dictionary of arguments to help with component construction"""
        kwargs = {}
        for attr in self.attributes:
            key = attr.name
            if key == "innerDiam":
                key = "id"
            elif key == "flags":
                continue
            val = attr.get_value(self)
            if key == "material":
                value = constructMaterial(val, blueprint, matMods, None)
            else:
                value = attr.get_value(self)
            kwargs[key] = value
        return kwargs


class ParticleFuelSpec(yamlize.KeyedList):
    """Specification for a single particle fuel type"""

    item_type = _ParticleFuelLayer
    key_attr = _ParticleFuelLayer.name
    name = yamlize.Attribute(type=str)

    def construct(self, blueprint, matMods):
        """Produce a particle fuel instance that can be attached to a component"""
        bounds = set()

        layers = sorted(self.values(), key=lambda spec: spec.od)
        spec = ParticleFuel(self.name)

        prevInner = -inf
        for layer in layers:
            comp = layer.construct(blueprint, matMods)
            innerDim = comp.getDimension("id")
            if innerDim < 0:
                raise ValueError(
                    f"{layer.name} inner diameter must be non-negative, got "
                    f"{innerDim}"
                )
            if innerDim <= prevInner:
                inners = [ring.innerDiam for ring in layers]
                raise ValueError(
                    f"{self.name} has inconsistent inner diameters: not "
                    f"increasing {inners}"
                )
            od = comp.getDimension("od")
            if innerDim >= od:
                raise ValueError(
                    f"{layer.name} outer diameter must be greater than inner diameter. "
                    f"Got {od} {innerDim}"
                )

            bounds.update((innerDim, od))
            spec.add(comp)
            prevInner = innerDim

        nLayers = len(self)
        if len(bounds) != nLayers + 1:
            names = [m.name for m in spec]
            raise ValueError(
                f"{self.name} does not have consistent boundaries. Bounds: "
                f"{sorted(bounds)}, compositions: {names}"
            )

        if not isclose(min(bounds), 0):
            raise ValueError(
                f"Particle fuel {self.name} does not start at radius of zero"
            )

        return spec


class ParticleFuelKeyedList(yamlize.KeyedList):
    """Keyed list to enable the ``particleFuel`` section

    Structure
    ---------

    ..code:: yaml

        particle fuel:
            <specifier>:
                <layer>:  # not strictly in increasing order
                    material: <string>
                    id: <float>
                    od: <float>
                    Tinput: <float>
                    Thot: <float>
                    flags: <optional list of strings>

    Example
    -------

    ..code:: yaml

        particle fuel:
            TRISO:
                kernel:
                    material: UO2
                    id: 0.6
                    od: 0.61
                    Tinput: 900
                    Thot: 900
                    flags: DEPLETABLE
                buffer:
                    material: SiC
                    id: 0.6
                    od: 0.62
                    Tinput: 900
                    Thot: 900
                ...

    This enables components to have a ``particle fuel`` section in the
    blueprints file, indicating a material like a matrix is filled with particle
    fuel

    ..code:: yaml

        <block>:
            <component>:
                name:  matrix
                material: Graphite
                # more options
                particleFuelSpec: TRISO
                particleFuelPackingFraction: 0.4  # 40% packing

    """

    item_type = ParticleFuelSpec
    key_attr = ParticleFuelSpec.name

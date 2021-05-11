from armi.reactor import flags
from armi.reactor.components import component
from armi.cases.inputModifiers import inputModifiers

from armi.reactor.converters import pinTypeBlockConverters


class _PinTypeAssemblyModifier(inputModifiers.InputModifier):
    """
    Abstract class for modifying something about a pin, within a block.

    This will construct blocks, determine if the block should be modified by checking
    the ``_getBlockTypesToModify``, and then run ``_adjustBlock(b)``. The ``Blueprints``
    are then updated based on the modification assuming that dimension names match
    exactly to ComponenBlueprint attributes (which is true, because ComponentBlueprint
    attributes are programmatically derived from Component constructors).
    """

    def __init__(self, value):
        inputModifiers.InputModifier.__init__(self, {self.__class__.__name__: value})
        self.value = value

    def __call__(self, cs, blueprints, geom):
        for bDesign in blueprints.blockDesigns:
            # bDesign construct requires lots of arguments, many of which have no impact.
            # The following can safely be defaulted to meaningless inputs:
            # axialIndex: a block can be reused at any axial index, modifications made
            #     dependent on will not translate back to the input in a  meaningful
            #     fashion
            # axialMeshPoints: similar to above, this is specified by the assembly, and
            #     a block can be within any section of an assembly.
            # height: similar to above. a block can have any height specified by an
            #     assembly. if height-specific modifications are required, then a new
            #     block definition should be created in the input
            # xsType: similar to above. a block can have any xsType specified through
            #     the assembly definition assembly. if xsType-specific modifications are
            #     required, then a new block definition should be created in the input
            # materialInput: this is the materialModifications from the assembly
            #     definition. if material modifications are required on a block-specific
            #     basis, they should be edited directly
            b = bDesign.construct(
                cs,
                blueprints,
                axialIndex=1,
                axialMeshPoints=1,
                height=1,
                xsType="A",
                materialInput={},
            )

            if not b.hasFlags(self._getBlockTypesToModify()):
                continue

            self._adjustBlock(b)

            for cDesign, c in zip(bDesign, b):
                for dimName in c.DIMENSION_NAMES:
                    inpDim = getattr(cDesign, dimName)
                    newDim = getattr(c.p, dimName)
                    if isinstance(newDim, tuple):
                        # map linked component dimension
                        link = component._DimensionLink(newDim)
                        newDim = str(link)
                    if inpDim != newDim:
                        setattr(cDesign, dimName, newDim)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        raise NotImplementedError

    def _adjustBlock(self, b):
        """Hook method for `__call__` template method."""
        raise NotImplementedError


class SmearDensityModifier(_PinTypeAssemblyModifier):
    """
    Adjust the smeared density to the specified value.

    This is effectively how much of the space inside the cladding tube is occupied by
    fuel at fabrication.
    """

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return flags.Flags.FUEL

    def _adjustBlock(self, b):
        """Hook method for `__call__` template method."""
        pinTypeBlockConverters.adjustSmearDensity(b, self.value)


class CladThicknessByODModifier(_PinTypeAssemblyModifier):
    """
    Adjust the cladding thickness by adjusting the inner diameter of all cladding components.
    """

    FAIL_IF_AFTER = (SmearDensityModifier,)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return ""

    def _adjustBlock(self, b):
        pinTypeBlockConverters.adjustCladThicknessByOD(b, self.value)


class CladThicknessByIDModifier(_PinTypeAssemblyModifier):
    """
    Adjust the cladding thickness by adjusting the outer diameter of the cladding component.
    """

    FAIL_IF_AFTER = (SmearDensityModifier,)

    def _getBlockTypesToModify(self):
        """Hook method to determine blocks that should be modified."""
        return ""

    def _adjustBlock(self, b):
        pinTypeBlockConverters.adjustCladThicknessByID(b, self.value)

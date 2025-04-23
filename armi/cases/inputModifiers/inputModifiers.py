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
"""Modifies inputs."""


class InputModifier:
    """
    Object that modifies input definitions in some well-defined way.

    .. impl:: A generic tool to modify user inputs on multiple cases.
        :id: I_ARMI_CASE_MOD1
        :implements: R_ARMI_CASE_MOD

        This class serves as an abstract base class for modifying the inputs of a case, typically
        case settings. Child classes must implement a ``__call__`` method accepting a
        :py:class:`~armi.settings.caseSettings.Settings` and
        :py:class:`~armi.reactor.blueprints.Blueprints` and return the appropriately modified
        version of these objects. The class attribute ``FAIL_IF_AFTER`` should be a tuple defining
        what, if any, modifications this should fail if performed after. For example, one should not
        adjust the smear density (a function of Cladding ID) before adjusting the Cladding ID. Some
        generic child classes are provided in this module, but it is expected that design-specific
        modifiers are built individually.
    """

    FAIL_IF_AFTER = ()

    def __init__(self, independentVariable=None):
        """
        Constructor.

        Parameters
        ----------
        independentVariable : dict or None, optional
            Name/value pairs to associate with the independent variable being modified by this
            object. Will be analyzed and plotted against other modifiers with the same name.
        """
        if independentVariable is None:
            independentVariable = {}
        self.independentVariable = independentVariable

    def __call__(self, cs, bp):
        """Perform the desired modifications to input objects."""
        raise NotImplementedError


class SamplingInputModifier(InputModifier):
    """
    Object that modifies input definitions in some well-defined way.

    (This class is abstract.)

    Subclasses must implement a ``__call__`` method accepting a ``Settings``,
    ``Blueprints``, and ``SystemLayoutInput``.

    This is a modified version of the InputModifier abstract class that imposes structure for
    parameters in a design space that will be sampled by a quasi-random sampling algorithm. These
    algorithms require input modifiers to specify if the parameter is continuous or discrete and
    have the bounds specified.
    """

    def __init__(
        self, name: str, paramType: str, bounds: list, independentVariable=None
    ):
        """Constructor for the Sampling input modifier.

        Parameters
        ----------
        name: str
            Name of input modifier.
        paramType : str
            specify if parameter is 'continuous' or 'discrete'
        bounds : list
            If continuous, provide floating points [a, b] specifying the inclusive bounds.
            If discrete, provide a list of potential values [a, b, c, ...]
        independentVariable : [type], optional
            Name/value pairs to associate with the independent variable being modified
            by this object.  Will be analyzed and plotted against other modifiers with
            the same name, by default None
        """
        InputModifier.__init__(self, independentVariable=independentVariable)
        self.name = name
        self.paramType = paramType
        self.bounds = bounds

    def __call__(self, cs, blueprints):
        """Perform the desired modifications to input objects."""
        raise NotImplementedError


class FullCoreModifier(InputModifier):
    """
    Grow the SystemLayoutInput to from a symmetric core to a full core.

    Notes
    -----
    Besides the Core, other grids may also be of interest for expansion, like a grid that defines
    fuel management. However, the expansion of a fuel management schedule to full core is less
    trivial than just expanding the core itself. Thus, this modifier currently does not attempt to
    update fuel management grids, but an expanded implementation could do so in the future if
    needed. For now, users must expand fuel management grids to full core themself.
    """

    def __call__(self, cs, bp):
        coreBp = bp.gridDesigns["core"]
        coreBp.expandToFull()

        return cs, bp


class SettingsModifier(InputModifier):
    """Adjust setting to specified value."""

    def __init__(self, settingName, value):
        InputModifier.__init__(self, independentVariable={settingName: value})
        self.settingName = settingName
        self.value = value

    def __call__(self, cs, bp):
        cs = cs.modified(newSettings={self.settingName: self.value})
        return cs, bp


class MultiSettingModifier(InputModifier):
    """
    Adjust multiple settings to specified values.

    Examples
    --------
    >>> inputModifiers.MultiSettingModifier(
    ...    {CONF_NEUTRONICS_TYPE: "both", CONF_COARSE_MESH_REBALANCE: -1}
    ... )

    """

    def __init__(self, settingVals: dict):
        InputModifier.__init__(self, independentVariable=settingVals)
        self.settings = settingVals

    def __call__(self, cs, bp):
        newSettings = {}
        for name, val in self.settings.items():
            newSettings[name] = val

        cs = cs.modified(newSettings=newSettings)
        return cs, bp


class BluePrintBlockModifier(InputModifier):
    """Adjust blueprint block->component->dimension to specified value."""

    def __init__(self, block, component, dimension, value):
        InputModifier.__init__(self, independentVariable={dimension: value})
        self.block = block
        self.component = component
        self.dimension = dimension
        self.value = value

    def __call__(self, cs, bp):
        # parse block
        for blockDesign in bp.blockDesigns:
            if blockDesign.name == self.block:
                # parse component
                for componentDesign in blockDesign:
                    if componentDesign.name == self.component:
                        # set new value
                        setattr(componentDesign, self.dimension, self.value)
                        return cs, bp

        return cs, bp

"""Modifies inputs."""


class InputModifier:
    """
    Object that modifies input definitions in some well-defined way.

    (This class is abstract.)

    Subclasses must implement a ``__call__`` method accepting a ``CaseSettings``,
    ``Blueprints``, and ``SystemLayoutInput``.

    The class attribute ``FAIL_IF_AFTER`` should be a tuple defining what, if any,
    modifications this should fail if performed after. For example, one should not
    adjust the smear density (a function of Cladding ID) before adjusting the Cladding
    ID.

    Some subclasses are provided, but you are expected to make your own design-specific
    modifiers in most cases.
    """

    FAIL_IF_AFTER = ()

    def __init__(self, independentVariable=None):
        """
        Constuctor.

        Parameters
        ----------
        independentVariable : dict or None, optional
            Name/value pairs to associate with the independent variable being modified
            by this object.  Will be analyzed and plotted against other modifiers with
            the same name.
        """
        if independentVariable is None:
            independentVariable = {}
        self.independentVariable = independentVariable

    def __call__(self, cs, blueprints, geom):
        """Perform the desired modifications to input objects."""
        raise NotImplementedError


class FullCoreModifier(InputModifier):
    """
    Grow the SystemLayoutInput to from a symmetric core to a full core.

    Notes
    -----
    Besides the core, other grids may also be of interest for expansion, like
    a grid that defines fuel management. However, the expansion of a fuel
    management schedule to full core is less trivial than just expanding
    the core itself. Thus, this modifier currently does not attempt
    to update fuel management grids, but an expanded implementation could
    do so in the future if needed. For now, users must expand fuel management
    grids to full core themself.
    """

    def __call__(self, cs, blueprints, geom):
        """Core might be on a geom object or a grid blueprint"""
        if geom:
            geom.growToFullCore()
        else:
            coreBp = blueprints.gridDesigns["core"]
            coreBp.expandToFull()


class SettingsModifier(InputModifier):
    """
    Adjust setting to specified value.
    """

    def __init__(self, settingName, value):
        InputModifier.__init__(self, independentVariable={settingName: value})
        self.settingName = settingName
        self.value = value

    def __call__(self, cs, blueprints, geom):
        cs[self.settingName] = self.value


class MultiSettingModifier(InputModifier):
    """
    Adjust multiple settings to specified values.

    Examples
    --------
    inputModifiers.MultiSettingModifier(
        {CONF_NEUTRONICS_TYPE: "both", CONF_COARSE_MESH_REBALANCE: -1}
    )
    """

    def __init__(self, settingVals: dict):
        InputModifier.__init__(self, independentVariable=settingVals)
        self.settings = settingVals

    def __call__(self, cs, blueprints, geom):
        for name, val in self.settings.items():
            cs[name] = val

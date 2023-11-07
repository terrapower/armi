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
The material package defines compositions and material-specific properties.

Properties in scope include temperature dependent thermo/mechanical properties 
(like heat capacity, linear expansion coefficients, viscosity, density),
and material-specific nuclear properties that can't exist at the nuclide level 
alone (like :py:mod:`thermal scattering laws <armi.nucDirectory.thermalScattering>`).

As the fundamental macroscopic building blocks of any physical object,
these are highly important to reactor analysis.

This module handles the dynamic importing of all the materials defined here at the framework
level as well as in all the attached plugins. It is expected that most teams will
have special material definitions that they will want to define.

It may also make sense in the future to support user-input materials that are not
hard-coded into the app.

The base class for all materials is in :py:mod:`armi.materials.material`.
"""
import pkgutil
import importlib
from typing import List
import inspect

from armi.materials.material import Material

# this will frequently be updated by the CONF_MATERIAL_NAMESPACE_ORDER setting
# during reactor construction (see armi.reactor.reactors.factory)
# This may also be replaced by a more global material registry at some point.
_MATERIAL_NAMESPACE_ORDER = ["armi.materials"]


def setMaterialNamespaceOrder(order):
    """
    Set the material namespace order at the Python interpretter, global level.

    .. impl:: Materials can be searched across packages in a defined namespace.
        :id: I_ARMI_MAT_NAMESPACE
        :implements: R_ARMI_MAT_NAMESPACE
    """
    global _MATERIAL_NAMESPACE_ORDER
    _MATERIAL_NAMESPACE_ORDER = order


def importMaterialsIntoModuleNamespace(path, name, namespace, updateSource=None):
    """
    Import all Material subclasses into the top subpackage.

    This allows devs to use ``from armi.materials import HT9``

    This can be used in plugins for similar purposes.

    .. warning::
        Do not directly import materials from this namespace in code. Use the full module
        import instead. This is just for material resolution. This will be replaced with a more
        formal material registry in the future.

    Parameters
    ----------
    path : str
        Path to package/module being imported
    name : str
        module name
    namespace : dict
        The namespace
    updateSource : str, optional
        Change DATA_SOURCE on import to a different string.
        Useful for saying where plugin materials are coming from.
    """
    for _modImporter, modname, _ispkg in pkgutil.walk_packages(
        path=path, prefix=name + "."
    ):
        if "test" not in modname:
            mod = importlib.import_module(modname)
            for item, obj in mod.__dict__.items():
                try:
                    if issubclass(obj, Material):
                        namespace[item] = obj
                        if updateSource:
                            obj.DATA_SOURCE = updateSource
                except TypeError:
                    # some non-class local
                    pass


importMaterialsIntoModuleNamespace(__path__, __name__, globals())


def iterAllMaterialClassesInNamespace(namespace):
    """
    Iterate over all Material subclasses found in a namespace.

    Notes
    -----
    Useful for testing.
    """
    for obj in namespace.__dict__.values():
        if inspect.isclass(obj):
            if issubclass(obj, Material):
                yield obj


def resolveMaterialClassByName(name: str, namespaceOrder: List[str] = None):
    """
    Find the first material class that matches a name in an ordered namespace.

    Names can either be fully resolved class paths (e.g. ``armi.materials.uZr:UZr``)
    or simple class names (e.g. ``UZr``). In the latter case, the ``CONF_MATERIAL_NAMESPACE_ORDER``
    setting to allows users to choose which particular material of a common name (like UO2 or HT9)
    gets used.

    Input files usually specify a material like UO2. Which particular implementation
    gets used (Framework's UO2 vs. a user plugins UO2 vs. the Kentucky Transportation
    Cabinet's UO2) is up to the user at runtime.

    .. impl:: Material collections are defined with an order of precedence in the case of duplicates.
        :id: I_ARMI_MAT_ORDER
        :implements: R_ARMI_MAT_ORDER

    Parameters
    ----------
    name : str
        The material class name to find, e.g. ``"UO2"``. Optionally, a module path
        and class name can be provided with a colon separator as ``module:className``, e.g.
        ``armi.materials.uraniumOxide:UO2`` for direct specification.
    namespaceOrder : list of str, optional
        A list of namespaces in order of preference in which to search for the material.
        If not passed, the value in the global ``MATERIAL_NAMESPACE_ORDER`` will be used,
        which is often set by the ``CONF_MATERIAL_NAMESPACE_ORDER`` setting (e.g.
        during reactor construction). Any value passed into this argument will be ignored
        if the ``name`` is provided with a ``modulePath``.

    Returns
    -------
    matCls : Material
        The material

    Raises
    ------
    KeyError
        When material of name cannot be found in namespaces.

    Examples
    --------
    >>> resolveMaterialClassByName("UO2", ["something.else.materials", "armi.materials"])
    <class 'something.else.materials.UO2'>

    See Also
    --------
    armi.reactor.reactors.factory
        Applies user settings to default namespace order.
    """
    if ":" in name:
        # assume direct package path like `armi.materials.uZr:UZr`
        modPath, clsName = name.split(":")
        mod = importlib.import_module(modPath)
        return getattr(mod, clsName)

    namespaceOrder = namespaceOrder or _MATERIAL_NAMESPACE_ORDER
    for namespace in namespaceOrder:
        mod = importlib.import_module(namespace)
        if hasattr(mod, name):
            return getattr(mod, name)

    raise KeyError(
        f"Cannot find material named `{name}` in any of: {str(namespaceOrder)}. "
        "Please update inputs or plugins. See CONF_MATERIAL_NAMESPACE_ORDER setting."
    )

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
The material package defines macroscopic material compositions and their properties.

Properties in scope include temperature dependent thermo/mechanical properties (like heat capacity, linear expansion
coefficients, viscosity, density), and material-specific nuclear properties that can not exist at the nuclide level
alone (like :py:mod:`thermal scattering laws <armi.nucDirectory.thermalScattering>`).

Material definitions are crucial to any nuclear analysis. This module handles the dynamic importing of all the materials
defined here and in attached plugins. It is expected that most teams will have special material definitions that they
will want to define.

In ARMI, materials can be defined purely in the ``armi.matProps`` YAML format. Or materials can be defined purely in
Python code. To support this, the material class :py:mod:`armi.materials.material` subclasses the ``matProp`` material
class.

You will find that ARMI comes provided with a set of material YAML files at ``armi/resources/materials``. These
materials are well-attributed from open-source references. They also serve as great examples of a variety of features
that the ``armi.matProps`` YAML files support. ARMI also maintains a few examples of complicated material definitions in
``armi/materials/``. You will find examples like :py:class:`armi.materials.water.SaturatedWater` and
:py:class:`armi.materials.uranium.Uranium`.
"""

import importlib
import inspect
import os
import pkgutil
import sysconfig
from typing import List

from armi import runLog
from armi.materials.material import Material
from armi.matProps import MatPropsMaterial
from armi.matProps import getPaths as getYamlPaths

# This can be updated by the CONF_MATERIAL_NAMESPACE_ORDER setting during reactor construction (see
# armi.reactor.reactors.factory).
_MATERIAL_NAMESPACE_ORDER = ["armi.materials"]

# dictionary of loaded materials: d[mat directory][mat name] = instance of Material object
_loadedYamlDirs = {}


def clear() -> None:
    """Clears all loaded YAML materials in ARMI."""
    global _loadedYamlDirs
    _loadedYamlDirs.clear()


def importYamlMaterialDir(dirPath, overwriteExisting=True, clearFirst=True):
    """
    Import all Materials defined by YAML files in the defined directory into this package.

    Parameters
    ----------
    dirPath : str
        Path to directory, filled with material YAML files, to be imported.
        If this is left as None, we will look for the "materials_data" directory in the venv.
    overwriteExisting : bool, optional
        If True, will overwrite existing YAML materials loaded from the same location. Default True.
    clearFirst : bool, optional
        A popular safety option is to first clear out the YAML materials loaded into memory before loading new ones.
        This is particularly popular during unit testing.
    """
    # Needs to be a local import to prevent circular imports
    from armi import getPluginManager

    global _loadedYamlDirs

    if not os.path.exists(dirPath) or not os.path.isdir(dirPath):
        msg = f"No material directory provided, or directory not found: {dirPath}"
        runLog.error(msg)
        raise FileNotFoundError(msg)

    if clearFirst:
        # clear the loaded materials before loading this new directory
        clear()

    if dirPath in _loadedYamlDirs and not overwriteExisting:
        return

    # recursively get all the *.yaml and *.yml files from the provided directory
    _loadedYamlDirs[dirPath] = {}
    paths = getYamlPaths(dirPath)
    for yamlPath in paths:
        # This makes us load a given YAML twice per material if they have a custom class
        # but I can't think of a better way to get the type from the material file.
        mat = Material(yamlPath=yamlPath)
        pm = getPluginManager()
        if pm:
            baseClassList = getPluginManager().hook.setMaterialBaseClass(materialType=mat.materialType)
            if baseClassList:
                # only one plugin can define this hook
                baseClass = baseClassList[0]
                mat = baseClass(yamlPath=yamlPath)
        mat.DATA_SOURCE = dirPath
        # If a class with this name already exists in the package, continue
        _loadedYamlDirs[dirPath][mat.name] = mat


def setMaterialNamespaceOrder(order):
    """
    Set the material namespace order at the Python interpreter, global level.

    .. impl:: Material collections are defined with an order of precedence in the case
        of duplicates.
        :id: I_ARMI_MAT_ORDER
        :implements: R_ARMI_MAT_ORDER

        An ARMI application will need materials. Materials can be imported from any code the application has access to,
        like plugin packages. This leads to the situation where one ARMI application will want to import multiple
        collections of materials. To handle this, ARMI keeps an ordered list of Python namespaces and directories from
        which to import materials.
    """
    global _loadedYamlDirs
    global _MATERIAL_NAMESPACE_ORDER
    _MATERIAL_NAMESPACE_ORDER = order

    # Check that venv and dir: YAML directories have been imported
    for namespace in order:
        if namespace.startswith("dir:"):
            yDir = namespace[4:]
        elif namespace.startswith("venv:"):
            yDir = os.path.join(sysconfig.get_paths()["purelib"], namespace[5:])
        else:
            continue

        if yDir not in _loadedYamlDirs:
            importYamlMaterialDir(yDir)


def getloadedYamlDirs() -> dict:
    """
    Returns the materials yaml directories that are loaded. The structure is:
    ``_loadedYamlDirs[<MAT DB PATH>][<MAT NAME>] = <MAT OBJ>``.

    Returns
    -------
    dict of dict
        Dictionary of directories, which are dictionaries of material yaml files
    """
    global _loadedYamlDirs
    return _loadedYamlDirs.copy()


def getMaterialNamespaceOrder() -> list:
    """
    Returns the material namespace order.

    Returns
    -------
    list of str
        Materials namespaces
    """
    global _MATERIAL_NAMESPACE_ORDER
    return _MATERIAL_NAMESPACE_ORDER.copy()


def importMaterialsIntoModuleNamespace(path, modName, namespace, updateSource=None):
    """
    Import all Material subclasses into the top subpackage. This only works for materials defined in Python.

    This allows devs to use ``from armi.materials import HT9``. This can be used in plugins for similar purposes.

    Parameters
    ----------
    path : str or list
        Path or list of paths to package/module being imported
    modName : str
        module name
    namespace : dict
        The namespace
    updateSource : str, optional
        Change DATA_SOURCE on import to a different string. Useful for saying where plugin materials are coming from.
    """
    # load materials from pure Python files
    for _modImporter, modname, _ispkg in pkgutil.walk_packages(path=path, prefix=modName + "."):
        if "test" in modname:
            continue

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


def createMaterialByName(name: str, namespaceOrder: List[str] = None):
    """
    Find the first material that matches a name in an ordered namespace.

    Names can either be fully resolved class paths (e.g. ``armi.materials.uZr:UZr``) or simple class names (e.g.
    ``UZr``). In the latter case, the ``CONF_MATERIAL_NAMESPACE_ORDER`` setting to allows users to choose which
    particular material of a common name (like UO2 or HT9) gets used.

    Input files usually specify a material like UO2. Which particular implementation gets used (Framework's UO2 vs. a
    user plugins UO2 vs. the Kentucky Transportation Cabinet's UO2) is up to the user at runtime.

    .. impl:: Materials can be searched across packages in a defined namespace.
        :id: I_ARMI_MAT_NAMESPACE
        :implements: R_ARMI_MAT_NAMESPACE

        During the runtime of an ARMI application, but particularly during the construction of the reactor in memory,
        materials will be requested by name. At that point, this code is called to search for that material name. The
        search goes through the ordered list of Python namespaces provided. The first time an instance of that material
        is found, it is returned. In this way, the first items in the material namespace list take precedence.

        When a material name is passed to this function, it may be either a simple name like the string ``"Water"`` or
        it may be much more specific, like ``armi.materials.water:Water``.

    Parameters
    ----------
    name : str
        The material class name to find, e.g. ``"Water"``. Optionally, a module path and class name can be provided with
        a colon separator as ``module:className``, e.g. ``armi.materials.water:Water`` for direct specification.
    namespaceOrder : list of str, optional
        A list of namespaces in order of preference in which to search for the material. If not passed, the value in the
        global ``MATERIAL_NAMESPACE_ORDER`` will be used, which is often set by the ``CONF_MATERIAL_NAMESPACE_ORDER``
        setting (e.g. during reactor construction). Any value passed into this argument will be ignored if the ``name``
        is provided with a ``modulePath``.

    Returns
    -------
    armi.materials.material.Material
        The material, which will always be of the ARMI Material class, which subclasses MatPropsMaterial.

    Raises
    ------
    KeyError
        When material of name cannot be found in namespaces.

    Examples
    --------
    >>> createMaterialByName("UO2", ["something.else.materials", "armi.materials"])
    <Material UO2>
    """
    # Needs to be a local import to prevent circular imports
    from armi import getPluginManager

    global _loadedYamlDirs
    global _MATERIAL_NAMESPACE_ORDER

    # 1. Try to import the material from a path like `armi.materials.uZr:UZr`
    if ":" in name:
        modPath, clsName = name.split(":")
        mod = importlib.import_module(modPath)
        return getattr(mod, clsName)()

    # 2. Select your namespace ordering
    namespaceOrder = namespaceOrder or _MATERIAL_NAMESPACE_ORDER

    # 3. Try to import the material from a namespace defined above
    for namespace in namespaceOrder:
        if namespace.startswith("venv:") or namespace.startswith("dir:"):
            # get the directory in question
            if namespace.startswith("dir:"):
                yDir = namespace[4:]
            elif namespace.startswith("venv:"):
                yDir = os.path.join(sysconfig.get_paths()["purelib"], namespace[5:])

            # check and see if you can find the material
            if yDir not in _loadedYamlDirs:
                continue
            elif name not in _loadedYamlDirs[yDir]:
                continue

            # grab the global material, and copy it over to a new material to return
            mat0 = _loadedYamlDirs[yDir][name]
            pm = getPluginManager()
            baseClass = Material
            if pm:
                baseClassList = getPluginManager().hook.setMaterialBaseClass(materialType=mat0.materialType)
                if baseClassList:
                    baseClass = baseClassList[0]

            newMat = baseClass(updateMassFracs=False)
            newMat.__dict__.update(mat0.__dict__)
            return newMat
        else:
            # check and see if this is an importable material
            mod = importlib.import_module(namespace)
            materialsList = inspect.getmembers(mod, lambda c: inspect.isclass(c) and issubclass(c, MatPropsMaterial))
            materialsList = [material[0] for material in materialsList]
            if name in materialsList:
                return getattr(mod, name)()

    raise KeyError(
        f"Cannot find material named `{name}` in any of: {str(namespaceOrder)}. Please update inputs or plugins. See "
        "CONF_MATERIAL_NAMESPACE_ORDER setting."
    )

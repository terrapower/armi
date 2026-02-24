# Copyright 2026 TerraPower, LLC
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
The package armi.matProps is a material library capable of representing and computing material properties.

The matProps package allows users to define materials in a custom YAML format. The format is simple, extensible, and
easy to use. Each material has a list of "properties" (like density, specific heat, vapor pressure, etc). Each of those
properties be an arbitrary function of multiple independent variables, or a look up table of one or more variables. Each
of these properties can define their own set of references, to allow for trustworthy modeling. A major idea in matProps
is that we separate out materials as "data", rather than representing them directly in Python as "code".

This package does not include any material data files. The unit tests in this package have many example YAML files, and ARMI
comes packaged with more real world examples at: ``armi/resources/materials/``. The user may create their own data files to use 
with ``matProps`` in a directory, and pass in that path via ``armi.matProps.loadAll(path)``. 

A Note on Design
================
At the high-level, the ``matProps`` API exposes the functions in this file (``loadAll``, ``loadSafe``, ``getMaterials``, etc). And
these functions all work off three global data collections: ``armi.matProps.loadedRootDirs``, ``armi.matProps.materials``, and
``armi.matProps.prop.properties``.

It is worth noting that this design centers around global data. This could have a more object-oriented
approach where the functions below and these three data sets are all stored in a class, e.g. via a
``MaterialLibrary`` class. This would be more Pythonic, and allow for multiple collections of materials, say
for testing. So far, no one has ever needed multiple colletions of materials from mat-props, because a single scientific
model generally only needs one source of truth for what materials are.
"""

import os
import sysconfig
import warnings
from glob import glob

from armi.matProps.material import Material

loadedRootDirs = []
materials = {}


def getPaths(rootDir: str) -> list:
    """Get the paths of all the YAML files in a given directory."""
    if not os.path.exists(rootDir):
        raise FileNotFoundError(f"Directory {rootDir} not found")
    elif not os.path.isdir(rootDir):
        raise NotADirectoryError(f"Input path {rootDir} is not a directory")

    patterns = ["*.yaml", "*.yml"]
    matFiles = []
    for pattern in patterns:
        matFiles.extend(glob(os.path.join(rootDir, "**", pattern), recursive=True))

    return matFiles


def addMaterial(yamlPath: str, mat):
    """
    Adds Material object instance to matProps.materials dict.

    Parameters
    ----------
    yamlPath: str
        Yaml file path whose information is being parsed.
    mat: Material
        Material object whose data will be saved.
    """
    global materials
    if mat.name in materials:
        msg = f"A material with the name `{mat.name}` as defined in ({yamlPath}) already exists."
        raise KeyError(msg)

    materials[mat.name] = mat
    mat.save()


def loadAll(rootDir: str = None) -> None:
    """
    Loads all material files from a particular directory. If a materials directory is not provided, this function will
    attempt to find materials in the default location in the virtual environment.

    Parameters
    ----------
    rootDir: str
        Directory whose YAML files will be loaded into matProps. The default is the materials_data location in the venv.

    Notes
    -----
    Hidden in here is a default directory which you can load your YAML files from. Inside your Python virtual
    environment, you can create a data directory named "materials_data", and store all your mat-props formatted YAML
    files. This is optional, of course, you can just explicitly pass a directory path into this method.
    """
    global loadedRootDirs

    if rootDir is None:
        rootDir = os.path.join(sysconfig.getPaths()["purelib"], "materials_data")
        if not os.path.exists(rootDir):
            raise OSError(f"No material directory provided, and default not found: {rootDir}")

    paths = getPaths(rootDir)
    for yamlPath in paths:
        mat = Material()
        try:
            mat.loadFile(yamlPath)
        except Exception as exc:
            msg = f"Failed to load `{yamlPath}`."
            raise RuntimeError(msg) from exc
        addMaterial(yamlPath, mat)

    loadedRootDirs.append(rootDir)


def clear() -> None:
    """Clears all loaded materials in matProps."""
    global materials
    global loadedRootDirs
    loadedRootDirs.clear()
    materials.clear()


def loadSafe(rootDir: str = None) -> None:
    """
    Safely load a single directory of matProps materials.

    Loading a materials directory via this function will first clear out any other materials that are loaded into
    matProps. If a materials directory is not provided, this function will attempt to find materials in the default
    location in the virtual environment. This is meant to be a helpful tool for testing.

    Parameters
    ----------
    rootDir: str
        Directory whose yaml files will be loaded into matProps.
        The default is the materials_data location in the venv.

    See Also
    --------
    loadAll : More flexible way to load materials into matProps.
    """
    clear()
    loadAll(rootDir)


def getHashes() -> dict:
    """Calls Material.hash() for each Material object in materials."""
    global materials
    hashes = {}
    for material in materials.values():
        hashes[material.name] = material.hash()

    return hashes


def getMaterial(name: str) -> Material:
    """
    Returns a material object with the given name from matProps.materials.

    Parameters
    ----------
    name: str
        Name of material whose data user wishes to retrieve.

    Returns
    -------
    Material
        Material object returned from matProps.materials.
    """
    global materials
    try:
        return materials[name]
    except KeyError:
        msg = f"No material named `{name}` was loaded within loaded data."
        raise KeyError(msg) from None


def loadMaterial(yamlPath: str, saveMaterial: bool = False) -> Material:
    """
    Loads an individual material file.

    Parameters
    ----------
    yamlPath: str
        Path to YAML file that will be parsed into this object instance.
    saveMaterial: bool
        If True, Material object instance will be saved into matProps.materials.

    Returns
    -------
    Material
        Material object whose data is parsed from material file provided by yamlPath.
    """
    mat = Material()
    mat.loadFile(yamlPath)
    if saveMaterial:
        addMaterial(yamlPath, mat)
    else:
        msg = f"Loading material {mat} {mat.hash()}"
        try:
            # If possible, keep matProps free of ARMI imports
            from armi import runLog

            runLog.info(msg)
        except ImportError:
            print(msg)

    return mat


def loadedMaterials() -> list:
    """
    Returns all the Material objects that have been loaded into matProps.materials.

    Returns
    -------
    list of Material
        Loaded Material objects
    """
    global materials
    mats = []
    for mat in materials.values():
        mats.append(mat)

    return mats


def getLoadedRootDirs() -> list:
    """
    Returns a list of all of the loaded root directories.

    Returns
    -------
    list of str
        Loaded root directories
    """
    global loadedRootDirs
    return loadedRootDirs


def load_all(rootDir: str = None) -> None:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.loadAll, not matProps.load_all.", DeprecationWarning)
    loadAll(rootDir)


def load_safe(rootDir: str = None) -> None:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.loadSafe, not matProps.load_safe.", DeprecationWarning)
    loadSafe(rootDir)


def get_material(name: str) -> Material:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.getMaterial, not matProps.get_material.", DeprecationWarning)
    return getMaterial(name)


def load_material(yamlPath: str, saveMaterial: bool = False) -> Material:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.loadMaterial, not matProps.load_material.", DeprecationWarning)
    return loadMaterial(yamlPath, saveMaterial)


def loaded_materials() -> list:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.loadedMaterials, not matProps.loaded_materials.", DeprecationWarning)
    return loadedMaterials()


def get_loaded_root_dirs() -> list:
    """Pass-through to temporarily support an old API."""
    warnings.warn("Please use matProps.getLoadedRootDirs, not matProps.get_loaded_root_dirs.", DeprecationWarning)
    return getLoadedRootDirs()

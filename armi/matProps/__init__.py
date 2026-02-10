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
The package matProps is a material library capable of computing material property quantities.

The package uses resource files (YAML) to define Material objects with Property Function attributes. This package does
not include any material data files. The user may create their own data files to use with matProps by passing a path in
armi.matProps.loadAll(path). ARMI does come with a set of material data files at armi.testing.materials that are useful
examples of how these YAML files are structured.
"""

import os
import sysconfig
import warnings
from glob import glob

from armi.matProps import material as material_file
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
        Directory whose YAML files will be loaded into matProps.
        The default is the materials_data location in the venv.
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


def gethashes() -> dict:
    """Calls Material.hash() for each Material object in materials."""
    global materials
    hashes = {}
    for material in materials.values():
        hashes[material.name] = material.hash()

    return hashes


def getMaterial(name: str) -> Material:
    """
    Returns a material object with the given name from armi.matProps.materials.

    Parameters
    ----------
    name: str
        Name of material whose data user wishes to retrieve.

    Returns
    -------
    Material
        Material object returned from armi.matProps.materials.
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


def getValidFileFormatVersions():
    """Get a vector of strings with all of the valid file format versions."""
    return material_file.getValidFileFormatVersions()


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

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
This module contains commonly used functions relating to directories, files and path
manipulations.
"""

import os
import shutil
import inspect
import importlib
import pathlib

from armi import runLog
from armi.context import ROOT


def getFullFileNames(directory=os.curdir, recursive=False):
    r"""Returns the fully qualified file names from the specified directory."""
    directory = os.path.abspath(directory)
    paths = []
    if recursive:
        for root, _, filenames in os.walk(directory):
            paths.extend([os.path.join(root, f) for f in filenames])
    else:
        paths.extend(os.path.join(directory, ff) for ff in os.listdir(directory))
    return paths


def armiAbsPath(*pathParts):
    """
    Convert a list of path components to an absolute path, without drive letters if possible.

    This is mostly useful on Windows systems, where drive letters are not well defined
    across systems. In these cases, it is useful to try to convert to a UNC path if
    possible.
    """
    # imported here to prevent cluster failures, unsure why this causes an error
    result = os.path.abspath(os.path.join(*pathParts))
    try:
        from ccl import common_operations

        return common_operations.convert_to_unc_path(result)
    except:  # pylint: disable=broad-except;reason=avoid pywin32 p.load parallel issues
        return result


def fitPathToFormat(input_path, fmt):
    """Clean string paths to end with the designated extension"""
    base, xtn = os.path.splitext(input_path)
    if xtn != format:
        input_path = base + fmt
    return input_path


def viewLocalFiles(fmt):
    """Show available fmt files in the current directory"""
    found = []
    for item in os.listdir("."):
        if item.endswith(fmt):
            found.append(item)
    if not found:
        return "No {} files found in the current directory".format(fmt)
    else:
        return found


def copyOrWarn(fileDescription, sourcePath, destinationPath):
    """Copy a file, or warn if the file doesn't exist.

    Parameters
    ----------
    fileDescription : str
        a description of the file and/or operation being performed.

    sourcePath : str
        Path of the file to be copied.

    destinationPath : str
        Path for the copied file.
    """
    try:
        shutil.copy(sourcePath, destinationPath)
        runLog.debug(
            "Copied {}: {} -> {}".format(fileDescription, sourcePath, destinationPath)
        )
    except Exception as e:
        runLog.warning(
            "Could not copy {} from {} to {}\nError was: {}".format(
                fileDescription, sourcePath, destinationPath, e)
        )


def armiAbsDirFromName(modName):
    """
    Convert a module name to a path.

    Notes
    -----
    This is often required in a Cython'd pyd extension where ``__file__`` is otherwise invalid.
    """
    if modName == "__main__":
        # allows it to work when a file is called directly (Python only, not cython).
        # But this fails when running via the Pydev debugger because the stack's non-standard
        # so we loop until we find a non-debugger file.
        for item in reversed(inspect.stack()):
            fname = inspect.getfile(item[0])
            if "pydevd" not in fname:
                return os.path.abspath(os.path.dirname(fname))
    return os.path.join(*([ROOT] + modName.split(".")[1:-1]))


def isFilePathNewer(path1, path2):
    r"""Returns true if path1 is newer than path2.

    Returns true if path1 is newer than path2, or if path1 exists and path2 does not, otherwise
    raises an IOError.
    """
    exist1 = os.path.exists(path1)
    exist2 = os.path.exists(path2)
    if exist1 and exist2:
        path1stat = os.stat(path1)
        path2stat = os.stat(path2)
        return path1stat.st_mtime > path2stat.st_mtime
    elif exist1 and not exist2:
        return True
    else:
        raise IOError("Path 1 does not exist: {}".format(path1))


def isAccessible(path):
    """Check whether user has access to a given path.

    Parameters
    ----------
    path : str
        a directory or file
    """
    if os.path.exists(path):
        # This can potentially return a false positive in Python 2 if the path
        # exists but the user does not have access. As a workaround, we attempt
        # to list the contents of the containing directory, which will throw an
        # OSError if the user doesn't have access.
        try:
            if not os.path.isdir(path):
                path = os.path.dirname(path)
            os.listdir(path)
            return True
        except OSError:
            return False
    else:
        return False


def getModAndClassFromPath(path):
    """
    Return the path to the module specified and the name of the class in the module.

    Raises
    ------
    ValueError:
        If the path does not exist or


    """
    pass


def separateModuleAndAttribute(pathAttr):
    """
    Return True of the specified python module, and attribute of the module exist.
    
    
    Parameters
    ----------
    pathAttr : str
        Path to a python module followed by the desired attribute.
        e.g.: `/path/to/my/thing.py:MyClass`
    
    Notes
    -----
    The attribute of the module could be a class, function, variable, etc.
    
    Raises
    ------
    ValueError:
        If there is no `:` separating the path and attr.
    """
    # rindex gives last index.
    # The last is needed because the first colon index could be mapped drives in windows.
    lastColonIndex = pathAttr.rindex(":")  # this raises a valueError
    # there should be at least 1 colon. 2 is possible due to mapped drives in windows.
    return (pathAttr[:lastColonIndex]), pathAttr[lastColonIndex + 1 :]


def importCustomPyModule(modulePath):
    """
    Dynamically import a custom module.
    
    Parameters
    ----------
    modulePath : str
        Path to a python module.
        
    Returns
    -------
    userSpecifiedModule : module
        The imported python module.
    """
    _dir, moduleName = os.path.split(modulePath)
    moduleName = os.path.splitext(moduleName)[0]  # take off the extension
    spec = importlib.util.spec_from_file_location(moduleName, modulePath)
    userSpecifiedModule = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(userSpecifiedModule)
    return userSpecifiedModule


def moduleAndAttributeExist(pathAttr):
    """
    Return True if the specified python module, and attribute of the module exist.
    
    
    Parameters
    ----------
    pathAttr : str
        Path to a python module followed by the desired attribute.
        e.g.: `/path/to/my/thing.py:MyClass`
        
    Returns 
    -------
    bool 
        True if the specified python module, and attribute of the module exist.
    
    Notes
    -----
    The attribute of the module could be a class, function, variable, etc.
    """
    try:
        modulePath, moduleAttributeName = separateModuleAndAttribute(pathAttr)
    except ValueError:
        return False

    modulePath = pathlib.Path(modulePath)
    if not modulePath.is_file():
        return False

    try:
        userSpecifiedModule = importCustomPyModule(modulePath)
    # Blanket except is okay since we are checking to see if a custom import will work.
    except:
        return False
    return moduleAttributeName in userSpecifiedModule.__dict__

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
TerraPower Calculation Results Cache (CRC)

This helps avoid duplicated time/energy in running cases.
In test systems and analysis, it's possible that the same calc will be done
over and over, always giving the same result. This system allows the results
to be cached and returned instantly instead of re-running, for example, MC2.

API usage
---------
Getting a cached file::

    exe = 'MC2-2018-blah.exe'
    inpFiles = ['mccAA.inp', 'rmzflx']
    outputFound = crc.retrieveOutput(exe, inp, output)
    if not outputFound:
        mc2.run(exe, inp, output)

Storing a file to the cache::

    crc.store(exe, inp, outFiles)

Notes
------
Could probably be, like, a decorate on subprocess but we call subprocess a bunch of
different ways.
"""

import os
import shutil
import hashlib
import json
import subprocess

from armi import runLog

MANIFEST_NAME = "CRC-manifest.json"


def retrieveOutput(exePath, inputPaths, cacheDir, locToRetrieveTo=None):
    """
    Check the cache for a valid file and copy it if it exists.

    Notes
    -----
    Input paths need to be in the same order each time if the same cached folder is expected to be found.
    """
    cachedFolder = _getCachedFolder(exePath, inputPaths, cacheDir)
    if os.path.exists(cachedFolder):
        if locToRetrieveTo is None:
            locToRetrieveTo = os.path.dirname(inputPaths[0])
        successful = _copyOutputs(cachedFolder, locToRetrieveTo)
        if successful:
            runLog.extra("Retrieved cached outputs for {}".format(exePath))
            return True
        else:
            # outputs didn't match manifest. Just delete to save checking next time.
            runLog.warning(
                "Outputs in {} were inconsistent with manifest. "
                "Deleting and reproducing".format(cachedFolder)
            )
            deleteCache(cachedFolder)
    return False


def _copyOutputs(cachedFolder, locToRetrieveTo):
    """Check that the outputs have the expectect hashes and copy them if they do."""
    manifest = os.path.join(cachedFolder, MANIFEST_NAME)
    if not os.path.exists(manifest):
        return False

    with open(manifest) as manifestJSON:
        storedOutputNamesToHashes = json.load(manifestJSON)
    copies = []
    for storedOutputName, expectedHash in storedOutputNamesToHashes.items():
        storedOutputPath = os.path.join(cachedFolder, storedOutputName)
        if _hashFiles([storedOutputPath]) != expectedHash:
            return False
        copyPath = os.path.join(locToRetrieveTo, storedOutputName)
        copies.append([storedOutputPath, copyPath])

    for copy in copies:
        storedOutputPath, copyPath = copy
        shutil.copy(storedOutputPath, copyPath)
    return True


def _getCachedFolder(exePath, inputPaths, cacheDir):
    """Return the the folder name expected for this executable and set of inputs."""
    exeName = os.path.basename(os.path.splitext(exePath)[0])
    exeHash = _hashFiles([exePath])
    inputHash = _hashFiles(inputPaths)

    # first 2 helps with reducing the number of folders in a folder
    first2, remainder = (inputHash[:2], inputHash[2:])
    return os.path.join(cacheDir, exeName, exeHash, first2, remainder)


def _hashFiles(paths):
    """Return a MD5 hash of a file's contents."""
    with open(paths[0], "rb") as binaryF:
        md5Hash = hashlib.md5(binaryF.read())

    for path in paths[1:]:
        with open(path, "rb") as binaryF:
            md5Hash.update(binaryF.read())
    return md5Hash.hexdigest()


def _makeOutputManifest(outputFiles, folderLocation):
    """Make a json file with the output names and expected hash."""
    manifest = {outputFile: _hashFiles([outputFile]) for outputFile in outputFiles}
    with open(os.path.join(folderLocation, MANIFEST_NAME), "w") as manifestJSON:
        json.dump(manifest, manifestJSON)


def store(exePath, inputPaths, outputFiles, cacheDir):
    """
    Store an output file in the cache.

    Notes
    -----
    Input paths need to be in the same order each time if the same cached folder is expected to be found.
    It is difficult to know what outputs will exist from a specific run, so only
    outputs that do exist will attempt to be copied.
    This function should be supplied with a greedy list of outputs.
    """
    # outputFilePaths is a greedy list and they might not all be produced
    outputsThatExist = [
        outputFile for outputFile in outputFiles if os.path.exists(outputFile)
    ]

    folderLoc = _getCachedFolder(exePath, inputPaths, cacheDir)
    if os.path.exists(folderLoc):
        deleteCache(folderLoc)
    os.makedirs(folderLoc)
    _makeOutputManifest(outputsThatExist, folderLoc)

    for outputFile in outputsThatExist:
        baseName = os.path.basename(outputFile)
        cachedLoc = os.path.join(folderLoc, baseName)
        shutil.copy(outputFile, cachedLoc)
    runLog.extra("Added outputs for {} to the cache.".format(exePath))


def deleteCache(cachedFolder):
    """
    Remove this folder.

    Requires safeword because this is potentially extremely destructive.
    """
    if "Output_Cache" not in cachedFolder:
        raise RuntimeError("Cache location must contain safeword: `Output_Cache`.")
    shutil.rmtree(cachedFolder)


def cacheCall(
    cs, executablePath, inputPaths, outputFileNames, execute=None, tearDown=None
):
    """
    Checks the cache to see if there are outputs for the run and returns them, otherwise calls the execute command.

    Notes
    -----
    It is non-trivial to determine the exact set of outputs an executable will produce
    without running the executable. Therefore, ``outputFileNames`` is expected to be a
    greedy list and cache will attempt to copy all the files, but not fail if the
    file is not present. When copying outputs back, all files copied previously will
    be targeted.
    """
    if execute is None:
        execute = lambda: subprocess.call([executablePath] + inputPaths)

    cacheDir = cs["outputCacheLocation"]
    if not cacheDir:
        runLog.info("Executing {}".format(executablePath))
        execute()
        return

    try:
        if retrieveOutput(executablePath, inputPaths, cacheDir):
            return
    except Exception as e:
        runLog.warning(
            "Outputs existed in cache, but failed to retrieve outputs from: "
            "{} \nerror: {}".format(
                _getCachedFolder(executablePath, inputPaths, cacheDir), e
            )
        )

    runLog.warning("Cached outputs were not found, executing {}".format(executablePath))
    execute()
    if tearDown is not None:
        tearDown()

    try:
        store(executablePath, inputPaths, outputFileNames, cacheDir)
    except Exception as e:
        # something went wrong in storage.
        # This is okay as the manifest will be inconsistent with the outputs and not used in the future.
        runLog.warning(
            "Failed to store outputs in: {}\nerror: {}".format(
                _getCachedFolder(executablePath, inputPaths, cacheDir), e
            )
        )

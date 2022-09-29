import os
import re

from armi import runLog
from armi.physics.fuelCycle import translationFunctions
from armi.utils.customExceptions import InputError


def getRepeatShuffle(
    fuelHandler,
    fileName,
    updateExistingEnrichment=False,
):
    r"""
    This function returns a shuffle data structure based on a previous ARMI run.

    Parameters
    ----------
    fuelHandler : Object
        An object for moving fuel around the core and reactor.

    fileName : str
        The file name of the shuffle history to be repeated

    updateExistingEnrichment : bool, optional
        Logic switch controling if enrichment levels from the previous ARMI run
        are copied to the current ARMI run.
        Default is False

    Returns
    -------
    shuffleDataStructure: array
        An array of assemblies to be sent to the swapCascade function of the fuel handler
    """

    # Import translations
    translations = readMoves(fileName)
    translationList = translations[fuelHandler.cycle + 1]
    TranslationDataStructure = processTranslationList(fuelHandler, translationList)
    # Update enrichment of existing assemblies
    if updateExistingEnrichment:
        for cascade in TranslationDataStructure:
            for assembly in cascade:
                if "SFP" in assembly.getLocation():
                    enrichment = [
                        i[3] for i in translationList if i[0] in assembly.getName()
                    ]
                elif assembly.getLocation()[:3].isnumeric():
                    enrichment = [
                        i[3] for i in translationList if i[1] in assembly.getLocation()
                    ]

                translationFunctions.changeBlockLevelEnrichment(assembly, enrichment)

    return TranslationDataStructure


def readMoves(fName):
    r"""
    This function gathers moves from a given shuffle report.

    Parameters
    ----------
    fname : str
        The shuffles file to read

    Returns
    -------
    moves : dict
        A dictionary of all the moves. Keys are the cycle number. Values are a list
        of tuples, one tuple for each individual move that happened in the cycle. The
        items in the tuple are (oldLoc, newLoc, enrichList, assemType). Where oldLoc
        and newLoc are str representations of the locations and enrichList is a list
        of mass enrichments from bottom to top.

    See Also
    --------
    repeatShufflePattern : reads this file and repeats the shuffling
    outage : creates the moveList in the first place.
    makeShuffleReport : writes the file that is read here.

    """

    try:
        f = open(fName)
    except:
        raise RuntimeError(
            "Could not find/open repeat shuffle file {} in working directory {}"
            "".format(fName, os.getcwd())
        )

    translations = {}
    numTranslations = 0
    headerText = r"Before cycle (\d+)"
    pat1Text = r"([A-Za-z0-9!\-]+) moved from ([A-Za-z0-9!\-]+) to ([A-Za-z0-9!\-]+) with assembly type ([A-Za-z0-9!\s]+) with enrich list: (.+)"

    for line in f:
        if "Before cycle" in line:
            m = re.search(headerText, line)
            if not m:
                raise InputError(
                    'Failed to parse line "{0}" in shuffle file'.format(line)
                )
            cycle = int(m.group(1))
            translations[cycle] = []
        elif "moved from" in line:
            m = re.search(pat1Text, line)
            if not m:
                raise InputError(
                    'Failed to parse line "{0}" in shuffle file'.format(line)
                )
            movingAssemName = m.group(1)
            oldLoc = m.group(2)
            newLoc = m.group(3)
            assemType = m.group(4).strip()
            enrichList = [float(i) for i in m.group(5).split()]
            translations[cycle].append(
                (movingAssemName, oldLoc, newLoc, enrichList, assemType)
            )
            numTranslations += 1
        elif "rotated from" in line or line == "\n":
            pass

        else:
            runLog.info('Failed to parse line "{0}" in shuffle file'.format(line))

    f.close()

    runLog.info(
        "Read {0} translations over {1} cycles".format(
            numTranslations, len(translations.keys())
        )
    )

    return translations


def processTranslationList(
    fuelHandler,
    translationList,
):
    r"""
    This function converts the translations provided by readMoves into a shuffle data structure
    """

    shuffleList = []
    fromList = []

    for i in translationList:
        if "LoadQueue" in i[1]:
            fromList.append("new: {0}; enrichment: {1}".format(i[4], i[3]))
        elif "SFP" in i[1]:
            fromList.append("sfp: {}".format(i[0]))
        else:
            fromList.append(i[1])

    toList = [i[2] for i in translationList]
    cashed = []

    # create shuffle cascades from the imported move list
    for location in fromList:
        if not location in cashed:
            cascade = _forwardSearch(location, fromList, toList, location)
            _backwardSearch(cascade, fromList, toList)
            cashed += cascade
            shuffleList.append(cascade)

    # Check cascades
    for cascade in shuffleList:
        if "SFP" in cascade[0]:
            if cascade[-1][:3].lower() in ["new", "sfp"]:
                cascade.remove("SFP")
            else:
                raise InputError(
                    "Cascade incomplete, missing charge assembly: " "{}".format(cascade)
                )
    # Convert string to data structure
    return translationFunctions.getCascadesFromLocations(fuelHandler, shuffleList)


def _forwardSearch(value, fromLoc, toLoc, initialValue):
    if value in fromLoc:
        index = fromLoc.index(value)
        if initialValue == toLoc[index]:
            chain = [value]
        else:
            chain = _forwardSearch(toLoc[index], fromLoc, toLoc, initialValue)
            chain.append(value)
    else:
        chain = [value]

    return chain


def _backwardSearch(chain, fromLoc, toLoc):
    if chain[-1] in toLoc:
        index = toLoc.index(chain[-1])
        if fromLoc[index] in chain:
            runLog.info("Found Cascade Loop: {0}".format(chain))
        else:
            chain.append(fromLoc[index])
            _backwardSearch(chain, fromLoc, toLoc)

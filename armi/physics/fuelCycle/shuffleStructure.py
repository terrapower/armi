from multiprocessing.sharedctypes import Value
from armi.physics.fuelCycle import translationFunctions
from armi.physics.fuelCycle import repeatShuffleFunctions
from armi.reactor.assemblies import Assembly


class shuffleDataStructure:
    def __init__(self, fuelHandler) -> None:
        self.fuelHandler = fuelHandler
        self.translations = [[]]
        self.rotations = []

    def buildRingShuffle(self, settings={}):
        r"""
        Builds a ring shuffle based on user settings.
        """
        # initalize settings
        internalRing = settings.get("internalRing", 1)
        externalRing = settings.get("externalRing", None)
        diverging = settings.get("diverging", False)
        jumpRingFrom = settings.get("jumpRingFrom", None)
        jumpRingTo = settings.get("jumpRingTo", None)
        coarseFactor = settings.get("coarseFactor", 0.0)
        newFuelName = settings.get("newFuelName", None)

        ringList = translationFunctions.buildRingSchedule(
            fuelHandler=self.fuelHandler,
            internalRing=internalRing,
            externalRing=externalRing,
            diverging=diverging,
            jumpRingFrom=jumpRingFrom,
            jumpRingTo=jumpRingTo,
            coarseFactor=coarseFactor,
        )
        ringAssemblies = translationFunctions.getRingAssemblies(
            self.fuelHandler, ringList
        )
        self.translations = translationFunctions.buildBatchCascades(
            ringAssemblies, newFuelName=newFuelName
        )

    def buildRepeatShuffle(self, updateExistingEnrichment=False):
        r"""
        Updates translations to repeat shuffles based on the case setting "explicitRepeatShuffles"
        """

        self.translations = repeatShuffleFunctions.getRepeatShuffle(
            self.fuelHandler,
            self.fuelHandler.cs["explicitRepeatShuffles"],
            updateExistingEnrichment=updateExistingEnrichment,
        )

    def checkTranslations(self):
        r"""
        Validate all entries in the self.swap.
        Check for any duplicates in the swap list and check that all elements are valid assemblies.
        """

        allAsssemblies = [
            assembly for assemblyList in self.translations for assembly in assemblyList
        ]

        # Check for duplicates
        if len(allAsssemblies) == len(set(allAsssemblies)):
            # Check that all elements are valid assemblies
            for assembly in allAsssemblies:
                if not issubclass(type(assembly), Assembly):
                    raise ValueError("{} is not a valid assembly".format(assembly))
        else:
            for assembly in allAsssemblies:
                if allAsssemblies.count(assembly) > 1:
                    raise ValueError(
                        "{} set to translate more than once".format(assembly)
                    )

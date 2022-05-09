# Copyright 2022 TerraPower, LLC
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

"""factory for the FuelHandler"""
from armi.operators import RunTypes
from armi.utils import directoryChangers, pathTools
from armi.physics.fuelCycle import fuelHandlers


def fuelHandlerFactory(operator):
    """
    Return an instantiated FuelHandler object based on user settings.

    The FuelHandler is expected to be a short-lived object that only lives for
    the cycle upon which it acts. At the next cycle, this factory will be
    called again to instantiate a new FuelHandler.
    """
    cs = operator.cs
    fuelHandlerClassName = cs["fuelHandlerName"]
    fuelHandlerModulePath = cs["shuffleLogic"]

    if not fuelHandlerClassName:
        # User did not request a custom fuel handler.
        # This is code coupling that should be untangled.
        # Special case for equilibrium-mode shuffling
        if cs["eqDirect"] and cs["runType"].lower() == RunTypes.STANDARD.lower():
            from terrapower.physics.neutronics.equilibrium import fuelHandler as efh

            return efh.EqDirectFuelHandler(operator)
        else:
            # give the default FuelHandler. This does not have an implemented outage, but
            # still offers moving capabilities. Useful when you just need to make explicit
            # moves but do not have a fully-defined fuel management input.
            return fuelHandlers.FuelHandler(operator)

    # User did request a custom fuel handler. We must go find and import it
    # from the input directory.
    with directoryChangers.DirectoryChanger(cs.inputDirectory, dumpOnException=False):
        try:
            module = pathTools.importCustomPyModule(fuelHandlerModulePath)

            if not hasattr(module, fuelHandlerClassName):
                raise KeyError(
                    "The requested fuel handler object {0} is not "
                    "found in the fuel management input file {1} from CWD {2}. "
                    "Check input"
                    "".format(
                        fuelHandlerClassName, fuelHandlerModulePath, cs.inputDirectory
                    )
                )
            # instantiate the custom object
            fuelHandlerCls = getattr(module, fuelHandlerClassName)
            fuelHandler = fuelHandlerCls(operator)

            # also get getFactorList function from module level if it's there.
            # This is a legacy input option, getFactorList should now generally
            # be an method of the FuelHandler object
            if hasattr(module, "getFactorList"):
                # staticmethod binds the provided getFactorList function to the
                # fuelHandler object without passing the implicit self argument.
                # The __get__ pulls the actual function out from the descriptor.
                fuelHandler.getFactorList = staticmethod(module.getFactorList).__get__(
                    fuelHandlerCls
                )

        except IOError:
            raise ValueError(
                "Either the file specified in the `shuffleLogic` setting ({}) or the "
                "fuel handler class name specified in the `fuelHandlerName` setting ({}) "
                "cannot be found. CWD is: {}. Update input.".format(
                    fuelHandlerModulePath, fuelHandlerClassName, cs.inputDirectory
                )
            )
    return fuelHandler

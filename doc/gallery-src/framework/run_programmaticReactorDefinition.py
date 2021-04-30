"""
Build Reactor Inputs Programmatically
=====================================

Sometimes it's desirable to build input definitions for ARMI using
code rather than by writing the textual input files directly.
In ARMI you can either make the ARMI reactor objects directly,
or you can define Blueprints objects. The benefit of making Blueprints
objects is that they can in turn be used to create both ARMI reactor
objects as well as textual input itself. This is nice when you want to
have traceable input files associated with a run that was developed
programmatically (e.g. for parameter sweeps).

This example shows how to make Blueprints objects programmatically completely
from scratch.

"""
import matplotlib.pyplot as plt
from armi import configure

configure(permissive=True)
# pylint: disable=wrong-import-position
from armi.reactor import blueprints
from armi import settings
from armi.settings import caseSettings
from armi.reactor.blueprints import isotopicOptions
from armi.reactor.blueprints import assemblyBlueprint
from armi.reactor.blueprints import blockBlueprint
from armi.reactor.blueprints import componentBlueprint
from armi.reactor.blueprints import gridBlueprint
from armi.reactor.blueprints import reactorBlueprint
from armi.utils import plotting
from armi import cases


def buildCase():
    """Build input components and a case."""
    bp = blueprints.Blueprints()
    bp.customIsotopics = isotopicOptions.CustomIsotopics()
    bp.nuclideFlags = isotopicOptions.genDefaultNucFlags()

    components = buildComponents()
    bp.blockDesigns = buildBlocks(components)
    bp.assemDesigns = buildAssemblies(bp.blockDesigns)
    bp.gridDesigns = buildGrids()
    bp.systemDesigns = buildSystems()

    cs = caseSettings.Settings()
    settings.setMasterCs(cs)  # remove once we eliminate masterCs
    cs.path = None
    cs.caseTitle = "scripted-case"
    case = cases.Case(cs=cs, bp=bp)

    return case


def buildComponents():
    ISOTHERMAL_TEMPERATURE_IN_C = 450.0
    fuel = componentBlueprint.ComponentBlueprint()
    fuel.name = "fuel"
    fuel.shape = "Circle"
    fuel.mult = 217
    fuel.material = "Custom"
    fuel.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    fuel.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    fuel.id = 0.0
    fuel.od = 0.4

    clad = componentBlueprint.ComponentBlueprint()
    clad.name = "clad"
    clad.mult = "fuel.mult"
    clad.shape = "Circle"
    clad.material = "HT9"
    clad.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    clad.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    clad.id = 0.508
    clad.od = 0.5842

    gap = componentBlueprint.ComponentBlueprint()
    gap.name = "gap"
    gap.shape = "Circle"
    gap.mult = "fuel.mult"
    gap.material = "Void"
    gap.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    gap.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    gap.id = "fuel.od"
    gap.od = "clad.id"

    wire = componentBlueprint.ComponentBlueprint()
    wire.name = "wire"
    wire.mult = "fuel.mult"
    wire.shape = "Helix"
    wire.material = "HT9"
    wire.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    wire.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    wire.id = 0.0
    wire.od = 0.14224
    wire.axialPitch = 30.48
    wire.helixDiameter = 0.72644

    duct = componentBlueprint.ComponentBlueprint()
    duct.name = "duct"
    duct.mult = 1
    duct.shape = "Hexagon"
    duct.material = "HT9"
    duct.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    duct.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    duct.ip = 11.0109
    duct.op = 11.6205

    intercoolant = componentBlueprint.ComponentBlueprint()
    intercoolant.name = "intercoolant"
    intercoolant.mult = 1
    intercoolant.shape = "Hexagon"
    intercoolant.material = "Sodium"
    intercoolant.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    intercoolant.Thot = ISOTHERMAL_TEMPERATURE_IN_C
    intercoolant.ip = "duct.op"
    intercoolant.op = 12.01420

    coolant = componentBlueprint.ComponentBlueprint()
    coolant.name = "coolant"
    coolant.shape = "DerivedShape"
    coolant.material = "Sodium"
    coolant.Tinput = ISOTHERMAL_TEMPERATURE_IN_C
    coolant.Thot = ISOTHERMAL_TEMPERATURE_IN_C

    componentBlueprints = {
        c.name: c for c in [fuel, gap, clad, wire, duct, intercoolant, coolant]
    }

    return componentBlueprints


def buildBlocks(components):
    """Build block blueprints"""
    blocks = blockBlueprint.BlockKeyedList()
    fuel = blockBlueprint.BlockBlueprint()
    fuel.name = "fuel"
    for cname, c in components.items():
        fuel[cname] = c
    blocks[fuel.name] = fuel

    reflector = blockBlueprint.BlockBlueprint()
    reflector.name = "reflector"
    reflector["coolant"] = components["coolant"]
    reflector["duct"] = components["duct"]
    blocks[reflector.name] = reflector

    return blocks


def buildAssemblies(blockDesigns):
    """Build assembly blueprints"""
    fuelBock, reflectorBlock = blockDesigns["fuel"], blockDesigns["reflector"]

    assemblies = assemblyBlueprint.AssemblyKeyedList()

    fuelAssem = assemblyBlueprint.AssemblyBlueprint()
    fuelAssem.name = "Fuel"
    fuelAssem.specifier = "IC"

    fuelAssem.blocks = blockBlueprint.BlockList()
    fuelAssem.blocks.extend(
        [reflectorBlock, fuelBock, fuelBock, fuelBock, reflectorBlock]
    )
    fuelAssem.height = [10, 20, 20, 20, 10]
    fuelAssem.xsTypes = ["A"] * 5
    fuelAssem.axialMeshPoints = [1] * 5

    assemblies[fuelAssem.name] = fuelAssem

    reflectorAssem = assemblyBlueprint.AssemblyBlueprint()
    reflectorAssem.name = "Reflector"
    reflectorAssem.specifier = "RR"
    reflectorAssem.blocks = blockBlueprint.BlockList()
    reflectorAssem.blocks.extend([reflectorBlock] * 5)
    reflectorAssem.height = [10, 20, 20, 20, 10]
    reflectorAssem.xsTypes = ["A"] * 5
    reflectorAssem.axialMeshPoints = [1] * 5
    assemblies[reflectorAssem.name] = reflectorAssem

    return assemblies


def buildGrids():
    """Build the core map grid"""

    coreGrid = gridBlueprint.GridBlueprint("core")
    coreGrid.geom = "hex"
    coreGrid.symmetry = "third periodic"
    coreGrid.origin = gridBlueprint.Triplet()

    coreGrid.latticeMap = """
         RR   RR
           IC   RR
         IC   IC   RR"""

    grids = gridBlueprint.Grids()
    grids["core"] = coreGrid
    return grids


def buildSystems():
    """Build the core system"""
    systems = reactorBlueprint.Systems()
    core = reactorBlueprint.SystemBlueprint("core", "core", gridBlueprint.Triplet())
    systems["core"] = core
    return systems


if __name__ == "__main__":
    case = buildCase()
    # build ARMI objects
    o = case.initializeOperator()
    fig = plotting.plotAssemblyTypes(
        case.bp,
        None,
        showBlockAxMesh=True,
    )
    plt.show()

    # also write input files
    case.writeInputs()

# Meant to be run from directory containing database

import sys
import nala
nala.configure()
from armi.bookkeeping import db

def updateTableParameters(cycle, node, tableParameters, o=None):
    if o is None:
        o = db.loadOperator(casefile, cycle, node)
    repInt = o.getInterface(name='report')
    repInt.tableParameters = tableParameters.copy()
    repInt.interactEveryNode(cycle, node)
    tableParameters = repInt.tableParameters.copy()
    return tableParameters

"""
Expects something like
    python ../get-parameter-table.py refTestBase
to be run from refTestBase/
"""
case = sys.argv[1]
if case[-3:] == '.h5':
    casefile = case
else:
    casefile = case + '.h5'

# If nCycles and nNodes unset, use 0th cycle to get that info
o = db.loadOperator(casefile, 0, 0)
tableParameters = []
tableParameters = updateTableParameters(0, 0, tableParameters, o=o)
nArgs = len(sys.argv)
if nArgs == 4:
    nCycles = int(sys.argv[2])
    nNodes = int(sys.argv[3])
elif nArgs == 3:
    nCycles = int(sys.argv[2])
    nNodes = o.cs['burnSteps'] + 1
else:
    nCycles = o.cs['nCycles']
    nNodes = o.cs['burnSteps'] + 1
for node in range(1, nNodes):
    tableParameters = updateTableParameters(0, node, tableParameters)


for cycle in range(1, nCycles):
    for node in range(nNodes):
        tableParameters = updateTableParameters(cycle, node, tableParameters) 


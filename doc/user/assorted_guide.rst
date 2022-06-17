Branch Searching
----------------
A powerful ARMI feature that exists in the :py:class:`Operator` is the branch search.
This runs multiple possible fuel management options in parallel and then
selects the one that is preferred by the user before going on to the
next time step. A branch search involves several methods.

A branch search starts when the :py:meth:`branchSearch <armi.operators.Operator.branchSearch>`
method is called on the primary node. It backs up the reactor state and that
of all the interfaces to allow the primary node to participate in the branch search.
It then calls :py:meth:`spawnCritShuffleSearch <armi.operators.Operator.spawnCritShuffleSearch>`
and restores the original reactor after the branch search is complete.

The :py:meth:`spawnCritShuffleSearch` method orchestrates
the number of search passes requested by the user (via the factorSearchFlags
mechanism), builds the distribution of control numbers for each case,
calls :py:meth:`runCritShuffleSearch <armi.operators.OperatorMPI.runCritShuffleSearch>`
to actually do the runs, and finally wraps up and chooses the best case.

The :py:meth:`runCritShuffleSearch <armi.operators.OperatorMPI.runCritShuffleSearch>`
only runs on the primary node as well. It distributes the current reactor and
interface state to all MPI processes and then broadcasts the command
to inform the MPI nodes to prepare to do a branch search (with the ``rebusShuffle``
command). On the primary and all the workers, the
:py:meth:`armi.operators.OperatorMPI.runShuffleBranch` method is called at the same
time to run the neutronics cases.

Physics Coupling
----------------
Loose coupled physics can be activated though the ``numCoupledIterations``
setting. This is handled in the :py:meth:`mainOperate <armi.operators.Operator.mainOperate>`
method.

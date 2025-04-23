*********************
Parallel Code in ARMI
*********************

ARMI simulations can be parallelized using the `mpi4py <https://mpi4py.readthedocs.io/en/stable/mpi4py.html>`_
module. You should go there and read about collective and point-to-point communication if you want to
understand everything in-depth.

The OS-level ``mpiexec`` command is used to run ARMI on, say, 10 parallel processors. This fires up 10 identical
and independent runs of ARMI; they do not share memory. If you change the reactor on one process, the reactors
don't change on the others.

Never fear. You can communicate between these processes using the Message Passing Interface (MPI) driver
via the Python ``mpi4py`` module. In fact, ARMI is set up to do a lot of the MPI work for you, so if you follow
these instructions, you can have your code working in parallel in no time. In ARMI, there's the primary processor
(which is the one that does most of the organization) and then there are the worker processors, which do whatever
you need them to in parallel.

MPI communication crash course
==============================
First, let's do a crash course in MPI communications. We'll only discuss a few important ideas, you can read
about more on the ``mpi4py`` web page. The first method of communication is called the ``broadcast``, which
happens when the primary processor sends information to all others. An example of this would be when you want to
sync up the settings object (``self.cs``) among all processors. An even more common example is when you want to
send a simple string command to all other processors. This is used all the time to inform the workers what they
are expected to do next.

Here is an example::

    from armi import context

    cmd = f"val{context.MPI_RANK}"

    if context.MPI_RANK == 0:
        # The primary node will send the string 'bob' to all others
        cmd = "bob"
        context.MPI_COMM.bcast(cmd, root=0)
    else:
        # These are the workers.
        # They receive a value and set it to the variable cmd
        context.MPI_COMM = comm.bcast(None, root=0)

Note that the ``comm`` object is from the ``mpi4py`` module that deals with the MPI drivers. The value of cmd on
the worker before and after the ``bcast`` command are shown in the table.

+--------------+-------+--------+--------+--------+
|              | Proc0 | Proc1  | Proc2  | Proc3  |
+--------------+-------+--------+--------+--------+
| Before bcast | "bob" | "val1" | "val2" | "val3" |
+--------------+-------+--------+--------+--------+
| After bcast  | "bob" | "bob"  | "bob"  | "bob"  |
+--------------+-------+--------+--------+--------+

The second important type of communication is the ``scatter``/``gather`` combo. These are used when you have a
big list of work you'd like to get done in parallel and you want to farm it off to a bunch of processors. To do
this, set up a big list of work to get done on the primary. Some real examples are that the list contains things
like run control parameters, assemblies, or blocks. For a trivial example, let's add a bunch of values in parallel.
First, let's create 1000 random numbers to add::

    import random
    workList = [(random.random(), random.random()) for _i in range(1000)]

Now we want to distribute this work to each of the worker processors (and take one for the primary too, so it's
not just sitting around waiting). This is what ``scatter`` will do. But ``scatter`` requires a list that has
length exactly equal to the number of processors available. You have some options here. Assuming there are 10
CPUs, you can either pass the first 10 values out of the list and keep sending groups of  10 values until they
are all sent (multiple sets of transmissions) or you can split the data up into 10 evenly-populated groups (single
transmission to each CPU). This is called *load balancing*. 

ARMI has utilities that can help called :py:func:`armi.utils.iterables.chunk` and :py:func:`armi.utils.iterables.flatten`.
Given an arbitrary list, ``chunk`` breaks it up into a certain number of chunks and ``unchunk`` does
the opposite to reassemble the original list after processing. Let's look at an example script::

    """mpi_example.py"""
    from random import random

    from armi import context
    from armi.utils import iterables

    # Generate a list of random number pairs: [[(v1,v2),(v3,v4),...]]
    workList = [(random(), random()) for _i in range(1000)]

    if context.MPI_RANK == 0:
        # Primary Process: Split the data and send it to the workers
        balanced = iterables.split(workList, context.MPI_SIZE)
        myValsToAdd = context.MPI_COMM.scatter(balanced, root=0)
    else:
        # Worker Process: Receive data, pass a dummy value to scatter
        myValsToAdd = context.MPI_COMM.scatter(None, root=0)


    # All processes do their bit of this work (adding)
    results = []
    for num1, num2 in myValsToAdd:
        results.append(num1 + num2)

    # All processes call gather to send their results back to the
    # root process. (The result lists above are simply added to make
    # one list with MPI_SIZE sub-lists.)
    allResultsLoadBalanced = context.MPI_COMM.gather(results, root=0)

    # Primary Process: Flatten the multiple lists
    # (from each process), and sum them.
    if context.MPI_RANK == 0:
        # Flatten the MPI_SIZE number of sub lists into one list
        allResults = iterables.flatten(allResultsLoadBalanced)
        # Sum the final list, and print the result
        print("The total sum is: {0:10.5f}".format(sum(allResults)))

Remember that this code is running on all processors. So it's just the ``if rank == 0`` statements that differentiate between the primary and the workers. To really understand what this script is doing, try to run it in parallel and see what it prints out::

        mpiexec -n 4 python mpi_example.py


MPI Communication within ARMI
=============================
Now that you understand the basics, here's how you should get your :py:class:`armi.interfaces.Interface`
to run things in parallel in ARMI.

You don't have to worry too much about the ranks, etc. because ARMI will set that up for you. Basically,
the interfaces are executed by the primary node unless you say otherwise. All workers are stalled in an ``MPI.bcast`` waiting
for your command! The best coding practice is to create an :py:class:`~armi.mpiActions.MpiAction` subclass and override
the :py:meth:`~armi.mpiActions.MpiAction.invokeHook` method. `MpiActions` can be broadcast, gathered, etc. and within
the :py:meth:`~armi.mpiActions.MpiAction.invokeHook` method have ``o``, ``r``, and ``cs`` attributes.

.. warning::

    When communicating raw Blocks or Assemblies all references to parents are lost. If a whole reactor is needed
    use ``DistributeStateAction`` and ``syncMpiState`` (shown in last example). Additionally, note that if a ``self.r`` 
    exists on the ``MpiAction`` prior to transmission it will be removed when ``invoke()`` is called.

If you have a bunch of blocks that you need independent work done on, always remember that unless you explicitly
MPI transmit the results, they will not survive on the primary node. For instance, if each CPU computes and sets
a block parameter (e.g. ``b.p.paramName = 10.0)``, these **will not** be set on the primary! There are a few
mechanisms that can help you get the data back to the primary reactor.

.. note:: If you want similar capabilities for objects that are not blocks, take another look at :py:func:`armi.utils.iterables.chunk`.


Example using ``bcast``
-----------------------

Some actions that perform the same task are best distributed through a broadcast. This makes sense for if your are
parallelizing code that is a function of an individual assembly, or block. In the following example, the interface simply
creates an ``Action`` and broadcasts it as appropriate::

    from armi import context

    class SomeInterface(interfaces.Interface):

        def interactEverNode(self, cycle, node):
            action = BcastAction()
            context.MPI_COMM.bcast(action)
            results = action.invoke(self.o, self.r, self.cs)

            # allResults is a list of len(self.r)
            for aResult in results:
                a.p.someParam = aResult

    class BcastAction(mpiActions.MpiAction):
      
        def invokeHook(self):
            # do something with the local self.r, self.o, and self.cs.
            # in this example... do stuff for assemblies.
            results = []
            for a in self.mpiIter(self.r):
                results.append(someFunction(a))

            # in this usage, it makes sense to gather the results
            allResults = self.gather(results)

            # Only primary node has allResults
            if allResults:
                # Flatten results returns the original order after
                # having made lists of mpiIter results.
                return self.mpiFlatten(allResults)


.. warning::

    Currently, there is no guarantee that the reactor state is the same across all nodes. Consequently, the above code
    should really contain a ``mpiActions.DistributeStateAction.invokeAsMaster`` call prior to broadcasting the
    ``action``. See example below.


Example using ``scatter``
-------------------------

When trying two independent actions at the same time, you can use ``scatter`` to distribute the work. The following example
shows how different operations can be performed in parallel::

    class SomeInterface(interfaces.Interface):

        def interactEveryNode(self, cycle, node):
            actions = []
            # pseudo code for getting a bunch of different actions
            for opt in self.cs['someSetting']:
                actions.append(factory(opt))
            
            distrib = mpiActions.DistributeStateAction()
            distrib.broadcast()
            
            # this line any existing reactor on workers to ensure consistency
            distrib.invoke(self.o, self.r, self.cs)
            # the 3 lines above are equivalent to:
            # mpiActions.DistributeStateAction.invokeAsMaster(self.o, self.r, self.cs)

            results = mpiActions.runActions(self.o, self.r, self.cs, actions)

            # do something to apply the results.
            for bi, b in enumerate(self.r.getBlocks():
                b.p.what = extractBlockResult(results, bi)

    def factory(opt):
        if opt == 'WHAT':
            return WhatAction()

    class WhatAction(mpiActions.MpiAction):

        def invokeHook(self):
            # does something
            # somehow gathers results.
            return self.gather(results)


A simplified approach
---------------------

Transferring state to and from a Reactor can be complicated and add a lot of code. An alternative approach is to ensure
that the reactor state is synchronized across all nodes, and then use the reactor instead of raw data::

    class SomeInterface(interfaces.Interface):

        def interactEveryNode(self, cycle, node):
            actions = []
            # pseudo code for getting a bunch of different actions
            for opt in self.cs['someSetting']:
                actions.append(factory(opt))
            
            mpiActions.DistributeStateAction.invokeAsMaster(self.o, self.r, self.cs)
            results = mpiActions.runActions(self.o, self.r, self.cs, actions)

    class WhatAction(mpiActions.MpiAction):

        def invokeHook(self):

            # do something
            for a in self.generateMyObjects(self.r):
                a.p.someParam = func(a)
                for b in a:
                    b.p.someParam = func(b)

            # notice we don't return an value, but instead just sync
            # the state, which updates the primary node with the
            # params that the workers changed.
            self.r.syncMpiState()

.. warning::

    Only parameters that are set are synchronized to the primary node. Consequently if a mutable 
    parameter (e.g. ``b.p.depletionMatrix`` which is of type ``BurnMatrix``) is changed, it will not
    natively be synced. To flag it to be synced, ``b.p.paramName`` must be set, even if it is to the
    same object. For this reason, setting parameters to mutable objects should be avoided. Further,
    if the mutable object has a reference to a large object, such as a composite or cross section
    library, it can be very computationally expensive to pass all this data to the primary node. See
    also: :py:mod:`armi.reactor.parameters`

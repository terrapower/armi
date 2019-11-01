*********************
Fuel Management Input
*********************

Fuel management in ARMI is specified through custom Python scripts that often reside
in the working directory of a run (but can be anywhere if you use full paths). During a normal run,
ARMI checks for two fuel management settings:

``shuffleLogic``
	The path to the Python source file that contains the user's custom fuel
	management logic

``fuelHandlerName``
	The name of a FuelHandler class that ARMI will look for in the Fuel Management Input file
	pointed to by the ``shuffleLogic`` path. Since it's input, it's the user's responsibility	
	to design and place that object in that file.
	
.. note:: We consider the limited syntax needed to express fuel management in Python
	code itself	to be sufficiently expressive and simple for non-programmers to
	actually use. Indeed, this has been our experience. 

The ARMI Operator will call its fuel handler's ``outage`` method before each cycle (and, if requested, during branch
search calculations). The :py:meth:`~armi.physics.fuelCycle.fuelHandlers.FuelHandler.outage` method
will perform bookkeeping operations, and eventually
call the user-defined ``chooseSwaps`` method (located in Fuel Management Input). ``chooseSwaps`` will
generally contain calls to :py:meth:`~armi.physics.fuelCycle.fuelHandlers.FuelHandler.findAssembly`,
:py:meth:`~armi.physics.fuelCycle.fuelHandlers.FuelHandler.swapAssemblies` ,
:py:meth:`~armi.physics.fuelCycle.fuelHandlers.FuelHandler.swapCascade`, and
:py:meth:`~armi.physics.fuelCycle.fuelHandlers.FuelHandler.dischargeSwap`, which are the primary
fuel management operations and can be found in the fuel management module.

Also found in the user-defined Fuel Management Input module is a ``getFactors`` method, which is used to control which
shuffling routines get called and at which time.

.. note::

    See the :py:mod:`fuelHandlers module <armi.physics.fuelCycle.fuelHandlers>` for more details.

Fuel Management Operations
==========================
In the ARMI, the assemblies can be moved as units around the reactor with swapAssemblies,
dischargeSwap, and swapCascade of a ``FuelHandler`` interface.

swapAssemblies
--------------
swapAssemblies is the simplest fuel management operation. Given two assembly objects, this method will switch
their locations. ::

    self.swapAssemblies(a1,a2)

dischargeSwap
-------------
A discharge swap is a simple operation that puts a new assembly into the reactor while discharging an
outgoing one. ::

    self.dischargeSwap(newIncoming,oldOutgoing)

This operation keeps track of the outgoing assembly in a AssemblyList object that the Reactor object has access to so you can see how much of what you discharged.

swapCascade
-----------
SwapCascade is a more powerful swapping function that can swap a list of assemblies in a "daisy-chain" type
of operation. These are useful for doing the main overtone shuffling operations such as convergent shuffling
and/or convergent-divergent shuffling. If we load up the list of assemblies, the first one will be put in the
last one's position, and all others will shift accordingly.

As an example, consider assemblies 1 through 5 in core positions A through E.::

    self.swapCascade([a1,a2,a3,a4,a5])

This table shows the positions of the assemblies before and after the swap cascade.


========    ============================    ===========================
Assembly    Position Before Swap Cascade    Position After Swap Cascade
========    ============================    ===========================
1           A                                   E
2           B                                   A
3           C                                   B
4           D                                   C
5           E                                   D
========    ============================    ===========================

Arbitrarily complex cascades can thusly be assembled by choosing the order of the assemblies passed into swapCascade.

Choosing Assemblies to Move
===========================

The methods described in the previous section require known assemblies to shuffle. Choosing these assemblies is
the essence of fuel shuffling design. The single method used for these purposes is the FuelHandler's ``findAssembly``
method. This method is very general purpose, and ranks in the top 3 most important
methods of the ARMI altogether.

To use it, just say::

    a = self.findAssembly(param='maxPercentBu',compareTo=20)

This will return the assembly in the reactor that has a maximum burnup closest to 20%. Other
inputs to findAssembly include:

================== ====================== ==============================
Argument             Example               Description
================== ====================== ==============================
targetRing          6                     Assemblies returned will be close to this ring. How close is determined by the width argument.
width              (4,1)                  First number is how many rings away from the targetRing are acceptable. Second number is direction. -1 will return rings lower than the targetRing, 1 will return rings higher than the targetRing, and 0 will return rings on either side of the targetRing.
param              'maxPercentBu'         An assembly-level parameter that will be searched for and compared with the compareTo argument.
compareTo           (aRef,0.6) or 20.5    A value to compare param to. If a single floating point number is given, it will be used a expected. If an (refAssembly, multiplier) tuple is given, the code will search for a value that is multiplier times the refAssembly's param. For instance, if you want to find an assembly that has a burnup near 50% of another assemblies burnup, you would give (anotherAssembly,0.5).
forceSide           -1,0, or 1            Requires the returned assembly to have either 1: higher, 1: lower, or None: either param than what's in compareTo.
exclusions          [a1,a2,a3]            Won't return any assembly in this list
minParam            'kInf'                A parameter to compare to minVal for setting lower bounds
minVal              0.99                  Sets the lower limit for minParam. The example values show will result in now assemblies with kInf<0.99 will be returned.
maxParam            'maxPercentBu'        A parameter to compare to minVal for setting upper bounds
maxVal              20                    Sets the lower limit for maxParam. The example values show will result in now assemblies with burnup>20% will be returned.
mandatoryLocations  ['A1010','B2001']     Will only return assemblies if they are in a location in this list.
excludedLocations   ['A1010','B2001']     Will only return assemblies that are not in these locations.
coords              (24.34,23.65)         Return assembly that is closest to this point in the x-y plane (in cm).
================== ====================== ==============================

Fuel Management Examples
========================

Convergent-Divergent
--------------------

Convergent-divergent shuffling is when fresh assemblies march in from the outside until they approach the jump ring,
at which point they jump to the center and diverge until they reach the jump ring again, where they now jump to the
outer periphery of the core, or become discharged.

If the jump ring is 6,  the order of target rings is::

    [6, 5, 4, 3, 2, 1, 6, 7, 8, 9, 10, 11, 12, 13]

In this case, assemblies converge from ring 13 to 12, to 11, to 10, ..., to 6, and then jump to 1 and diverge
until they get back to 6. In a discharging equilibrium case, the highest burned assembly in the jumpRing should
get discharged and the lowest should jump by calling a dischargeSwap on cascade[0] and a fresh feed after this
cascade is run.

The convergent rings in this case are 7 through 13 and the divergent ones are 1 through 5 are the divergent ones.


Fuel Management Tips
====================
Some mistakes are common. Follow these tips.

    * Always make sure your assembly-level types in the settings file are up to date with your geometry input file. Otherwise you'll be moving feeds when you want to move igniters, or something.
    * Use the exclusions list! If you move a cascade and then the next cascade tries to run, it will choose your newly-moved assemblies if they fit your criteria in findAssemblies. This leads to very confusing results. Therefore, once you move assemblies, you should default to adding them to the exclusions list.
    * Print cascades during debugging. After you've built a cascade to swap, print it out and check the locations and types of each assembly in it. Is it what you want?
    * Watch typeNum in the database. You can get good intuition about what is getting moved by viewing this parameter.

Running a branch search
=======================
ARMI can perform a branch search where a number of fuel management operations
are performed in parallel and the preferred one is chosen and proceeded with.
The key to any branch search is writing a fuel handler that can interpret
**fuel management factors**, defined as keyed values between 0 and 1.

As an example, a fuel handler may be written to interpret two factors, ``numDischarges``
and ``chargeEnrich``. One method in the fuel handler would then take
the value of ``factors['numDischarges']`` and multiply it by the maximum
number of discharges (often set by another user setting) and then discharge
this many assemblies. Similarly, another method would take the ``factors['chargeEnrich']``
value (between 0 and 1) and multiply it by the maximum allowable enrichment
(again, usually controlled by a user setting) to determine which enrichment
should be used to fabricate new assemblies.

Given a fuel handler that can thusly interpret factors between 0 and 1, the
concept of branch searches is simple. They simply build uniformly distributed
lists between 0 and 1 across however many CPUs are available and cases on all
of them, passing one of each of the factors to each CPU in parallel. When the cases finish,
the branch search determines the optimal result and selects the corresponding
value of the factor to proceed.

Branch searches are controlled by custom `getFactorList` methods specified in the
`shuffleLogic` input files. This method should return two things:

    * A ``defaultFactors``; a dictionary with user-defined keys and values between
      0 and 1 for each key. These factors will be passed to the ``chooseSwaps``
      method, which is typically overridden by the user in custom fuel handling code.
      The fuel handling code should interpret the values and move the fuel
      according to what is sent.

    * A ``factorSearchFlags`` list, which lists the keys to be branch searched.
      The search will optimize the first key first, and then do a second pass
      on the second key, holding the optimal first value constant, and so on.

Such a method may look like this::

    def getFactorList(cycle,cs=None):

        # init default shuffling factors
        defaultFactors = {'chargeEnrich':0,'numDischarges':1}
        factorSearchFlags=[] # init factors to run branch searches on

        # determine when to activate various factors / searches
        if cycle not in [0,5,6]:
            # shuffling happens before neutronics so skip the first cycle.
            defaultFactors['chargeEnrich']=1
        else:
            defaultFactors['numDischarges']=0
            factorSearchFlags = ['chargeEnrich']

        return defaultFactors,factorSearchFlags

Once a proper ``getFactorList`` method exists and a fuel handler object
exists that can interpret the factors, activate a branch search
during a regular run by selecting the **Branch Search** option on the GUI.

The **best** result from the branch search is determined by comparing the *keff* values
with the ``targetK`` setting, which is available for setting in the GUI. The branch
with *keff* closest to the setting, while still being above 1.0 is chosen.

If you want to do branch searches from within an interface, just call
the :py:meth:`o.branchSearch <armi.operators.Operator.branchSearch>` method.

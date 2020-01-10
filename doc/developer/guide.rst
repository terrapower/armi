**********************
Framework Architecture
**********************

Here we will discuss some big-picture elements of the ARMI architecture. Throughout,
links to the API docs will lead to additional details.

-----------------
The Reactor Model
-----------------

The :py:mod:`~armi.reactor` package is the central representation of a nuclear reactor
in ARMI.  All modules can be expected to want access to some element of the state data
in a run, and should be enabled to find the data present somewhere in the ``reactor``
package's code during runtime.

An approximation of `Composite Design Pattern
<http://en.wikipedia.org/wiki/Composite_pattern>`_ is used to represent the **Reactor**
in ARMI. In this hierarchy the **Reactor** object is a **Core** object, and potentially
many generic **Composite** objects representing ex-core structures. The **Core** is made
of **Assembly** objects, which are in turn made up as a collection of **Block** objects.
:term:`State <reactor state>` variables may be stored at any level of this heirarchy
using the :py:mod:`armi.reactor.parameters` system to contain results (e.g., ``keff``, ``flow rates``,
``power``, ``flux``, etc.). Within each block are **Components** which define the
pin-level geometry.  Associated with each Component are **Material** objects that
contain material properties (``density``, ``conductivity``, ``heat capacity``, etc.) and
isotopic mass fractions.

.. note:: Non-core structures (spent fuel pools, core restraint, heat exchangers, etc.)
   may be represented analogously to the **Core**, but this feature is new and under
   development. Historically, the **Core** and **Reactor** were the same thing, and some
   information in the documentation still reflects this.

.. figure:: /.static/armi_reactor_objects.png
    :align: center

    **Figure 1.** The primary data containers in ARMI

Each level of the composite pattern hierarchy contains most of its state data in a
collection of parameters detailing considerations of how the reactor has progressed
through time to any given point. This information also constitutes the majority of what
gets written to the database for evaluation and/or follow-on analysis.

Review the :doc:`/user/tutorials/data_model` section for examples
exploring a populated instance of the **Reactor** model.

Parameters
----------

One of the main benefits to ARMI is that it enables simple interfaces to extract data
from the reactor, do something with it, and add new results to the reactor. This enables
specialized developers to write code that uses ARMI as input and output.

Most data is stored in ARMI as :py:mod:`~armi.reactor.parameters`. Most parameters will
become persistent, meaning they will be saved to the database during database
interactions, and therefore it will also be loaded when a database is loaded.

Details of the use and design can be found at :py:mod:`~armi.reactor.parameters`.

Converters
----------

The :py:mod:`~armi.reactor.converters` subpackage contains a variety of utilities that
can convert a reactor model in various ways. Some converters change designs at the block
level, adjusting pin dimensions or fuel composition. Others adjust the reactor geometry
at large, changing a 1/3-symmetric model to a full core, or changing a hexagonal
geometry to a R-Z geometry. Converters are used for parameter sweeps as well as during
various physics operations.

For example, some lattice physics routines convert the full core to a 2D R-Z model and
compute flux with thousands of energy groups to properly capture the spectral-spatial
coupling in a core/reflector interface. The converters are used heavily in these
operations.

Blueprints
----------

As seen in the User Guide, :py:mod:`~armi.reactor.blueprints` are how reactor models are
defined. During a run, they can be used to create new instances of reactor model pieces,
such as when a new assembly is fabricated during a fuel management operation in a later
cycle.

---------
Operators
---------

Operators conduct the execution sequence of an ARMI run. They basically contain the main
loop. When any operator is instantiated, several actions occur:

    1. Some environmental detail is printed out,
    2. A Reactor object is instantiated
    3. Loading and geometry input files are processed and the reactor object is
       populated with assemblies,
    4. The **interfaces** are instantiated
       and placed in the **Interface Stack** during the :py:meth:`createInterfaces
       method<armi.operators.Operator.createInterfaces>` call,
    5. The ``interactInit`` method is called on all interfaces, and
    6. Restart information is processed (if this is a restart run).

These operations are depicted in the following image.

    .. image:: /.static/armi_objects_2.png
           :width: 100%

After that, depending on the type of Operator at hand, one of several operational loops
will begin via ``operate()``. Operator types are chosen by the ``runType`` setting,
which is featured on the first tab of the ARMI GUI.

The Standard Operator
---------------------

The two primary types of operators are the Standard Operator (along with its parallel
version, the :py:class:`OperatorMPI <armi.operators.OperatorMPI>`), and the
:py:class:`OperatorSnapshots <armi.operators.OperatorSnapshots>`. The former runs a
typical operational loop, which calls all the interfaces through their interaction hooks
in a sequential manner, marching from beginning-of-life through the number of cycles
requested. This is how most quasistatic fuel cycle calculations are performed, which
inform much of the analysis done during reactor design. The main code for this loop is
found in the :py:meth:`mainOperate method <armi.operators.Operator.mainOperate>`. This 
operator supports restart/continuation of past runs from an arbitrary time step.

The Snapshots Operator
----------------------

Alternatively, OperatorSnapshots is designed to allow for additional analyses at
specific time steps. It simply loops through all snapshots that have been requested via
the Snapshot Request functionality (Lists -> Edit snapshot requests in the GUI). At each
snapshot request, the state is loaded from a previous case, as determined by the
``reloadDBName`` setting and then the BOC, EveryNode, and EOC interaction hooks are
executed from all the interfaces. Snapshots are intended to analyze an exact reactor 
configuration. Therefore, interfaces which would significantly change the reactor 
configuration (such as Fuel management, and depletion) are disabled.

The Interface Stack
-------------------
*Interfaces* (:py:class:`armi.interfaces.Interface`) operate upon the Reactor Model to
do analysis.  They're designed to allow expansion of the code in a natural and
well-organized manner. Interfaces are useful to link external codes to ARMI as well for
adding new internal physics into the rest of the system. As a result, very many aspects
of ARMI are contained within interfaces.

The flow of any ARMI calculation depends on the order of the interfaces, which is set at
initialization according to the user settings and the corresponding ``ORDER`` attributes
in interface modules. The collection of the interfaces is known as the **Interface
Stack** and is prominently featured at the beginning of the standard output of each run,
like this::

    [R  0 ] -------------------------------------------------------------------------------
    [R  0 ]                        ***  Interface Stack Report  ***
    [R  0 ] NUM   TYPE                 NAME                 ENABLED    BOL FORCE  EOL ORDER
    [R  0 ] -------------------------------------------------------------------------------
    [R  0 ] 00    Main                 "main"               Yes        No         Reversed
    [R  0 ] 01    Software Testing     "softwareTests"      Yes        No         Reversed
    [R  0 ] 02    ReportInterface      "report"             Yes        No         Reversed
    [R  0 ] 03    FuelHandler          "fuelHandler"        Yes        No         Normal
    [R  0 ] 04    Depletion            "depletion"          Yes        Yes        Normal
    [R  0 ] 05    MC2-2                "mc2"                Yes        No         Normal
    [R  0 ] 06    DIF3D                "dif3d"              Yes        No         Normal
    [R  0 ] 07    Thermo               "thermo"             Yes        No         Normal
    [R  0 ] 08    OrificedOptimized    "orificer"           Yes        Yes        Normal
    [R  0 ] 09    AlchemyLite          "alchemyLite"        Yes        No         Normal
    [R  0 ] 10    Alchemy              "alchemy"            Yes        No         Normal
    [R  0 ] 11    Economics            "economics"          Yes        No         Normal
    [R  0 ] 12    History              "history"            Yes        No         Normal
    [R  0 ] 13    Database             "database"           Yes        Yes        Normal
    [R  0 ] -------------------------------------------------------------------------------


Any interface that exists on the interface stack is accessible from the ``operator`` or
from any other interface object through the :py:meth:`getInterface method
<armi.operators.Operator.getInterface>`.

Interface Interaction Hooks
---------------------------
Various interfaces need to interact with ARMI at various times. The point at which
routines are called during a run set by developers in interface *hooks*, as seen below.
At each point in the flow chart, interfaces are interacted with one-by-one as the
interface stack is traversed in order.

.. figure:: /.static/armi_general_flowchart.png
    :align: center

    **Figure 1.** The computational flow of the interface hooks

For example, input checking routines would run at beginning-of-life (BOL), calculation
modules might run at every time node, etc. To accommodate these various needs, interface
hooks include:

* :py:meth:`interactInit <armi.interfaces.Interface.interactInit>` occurs right after
  all interfaces are initialized.

* :py:meth:`interactBOL <armi.interfaces.Interface.interactBOL>` -- Beginning of life.
  Happens once as the run is starting up.

* :py:meth:`interactBOC <armi.interfaces.Interface.interactBOC>` -- Beginning of cycle.
  Happens once per cycle.

* :py:meth:`interactEveryNode <armi.interfaces.Interface.interactEveryNode>` -- happens
  after every node step/flux calculation

* :py:meth:`interactEOC <armi.interfaces.Interface.interactEOC>` -- End of cycle.

* :py:meth:`interactEOL <armi.interfaces.Interface.interactEOL>` -- End of life.

* :py:meth:`interactError <armi.interfaces.Interface.interactError>` -- When an error
  occurs, this can run to clean up or print debugging info.

These interaction points are optional in every interface, and you may override one or
more of them to suit your needs.  You should not change the arguments to the hooks,
which are integers.

Each interface has a ``enabled`` flag. If this is set to ``False``, then the interface's
hook code will not be called even though the interface exists in the problem. This is
useful for interfaces that use code from other interfaces. For example, if ``subchan``
is activated, it still uses some code in the ``thermo`` module to compute the fuel
temperatures, so the ``thermo`` interface must be available in a ``getInterface`` call.


Adding a new interface
----------------------
When using the Operators that come with ARMI, Interfaces are discovered using the
:py:mod:`Plugin API <armi.plugins>` and inserted into the interface stack during the
:py:meth:`createInterfaces <armi.operators.operator.Operator.createInterfaces>` method.



How interfaces get called
-------------------------

The hooks of interfaces are called during the main loop in
:py:meth:`armi.operators.Operator.mainOperate`. There are a few special operator calls
in there to methods like :py:meth:`armi.operators.Operator.interactAllBOL` that loop
through the interface stack and call each enabled interface's ``interactBOL()`` method.
If you override ``mainOperate`` in a custom operator, you will need to add these calls
as deemed necessary to have the interfaces work properly.

To use interfaces in parallel, please refer to :py:mod:`armi.mpiActions`.


-------
Plugins
-------

Plugins are higher-level objects that can bring in one or more Interfaces, settings
definitions, parameters, validations, etc. They are documented in
:doc:`/developer/making_armi_based_apps` and :py:mod:`armi.plugins`.


Entry Points
------------
ARMI has a set of :py:mod:`Entry Points <armi.cli.entryPoint.EntryPoint>` that can run
cases, launch the GUI, and perform various testing and utility operations. When you
invoke ARMI with ``python -m armi run``, the ``__main__.py`` file is loaded and all
valid Entry Points are dynamically loaded. The proper entry point (in this case,
:py:class:`armi.cli.run.RunEntryPoint`) is invoked. As ARMI initializes itself, settings
are loaded into a :py:class:`CaseSettings <armi.settings.caseSettings.CaseSettings>`
object.  From those settings, an :py:class:`Operator <armi.operators.operator.Operator>`
subclass is built by a factory and its ``operate`` method is called. This fires up the
main ARMI analysis loop and its interface stack is looped over as indicated by user
input.


------------------
Finding assemblies
------------------
There are a few ways to get the assemblies you're interested in.

    * `r.core.whichAssemblyIsIn(ring,position)` returns whichever assembly is in
      (ring,position)

    * `r.core.getLocationContents(locList)` returns the assemblies or blocks that correspond
      to the location list. This can be much faster that `whichAssemblyIsIn` if you need
      many assemblies

    * `r.core.getAssemblies()` loops through all assemblies in the core for when you need to
      do something to all assemblies

    * `hist.getDetailAssemblies()` use the `HistoryInterface` to find the assemblies
      that the user has specifically designated "detail assemblies", meaning assemblies
      that will receive special analysis. This is useful for doing limiting analyses
      that would be too time consuming or otherwise wasteful to apply to all assemblies.



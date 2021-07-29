**********************
Accessing Data in ARMI
**********************

A basic user only needs to know the GUI and can perform basic
analysis and design with just that. But a power user will be more interested
in programmatically building and manipulating inputs and gathering detailed information
out of ARMI results. Let's now go into a bit more detail for the power user.

Settings and State Variables
----------------------------
The following links contain large tables describing the various global settings
and state parameters in use across ARMI.

* :doc:`Table of all global settings </user/inputs/settings_report>`
* :doc:`Reactor Parameters </user/reactor_parameters_report>`
* :doc:`Core Parameters </user/core_parameters_report>`
* :doc:`Assembly Parameters </user/assembly_parameters_report>`
* :doc:`Block Parameters </user/block_parameters_report>`
* :ref:`Component Parameters <componentTypes>`


Accessing Some Interesting Info
-------------------------------
Often times, you may be interested in the geometric dimensions of various blocks. These are stored on the
:py:mod:`components <armi.reactor.components>`, and may be accessed as follows::

    b = o.r.getFirstBlock(Flags.FUEL)
    fuel = b.getComponent(Flags.FUEL)
    od = fuel.getDimension('od',cold=True)  # fuel outer diameter in cm
    odHot = fuel.getDimension('od')  # hot dimension
    id600 = fuel.getDimension('id',Tc=600)  # hot inner diameter at a specific temperature

    clad = b.getComponent(Flags.CLAD)
    numClad = clad.getDimension('mult')  # number of cladding pins (multiplicity)

    cladMat = clad.getProperties()  # get the cladding material (HT9 probably)
    k = cladMat.thermalConductivity(Tc=500)  # get the thermal conductivity of HT9 at 500C.

The dimensions available depend on the shape of the component. Hexagons have op and ip for outer and inner pitch.
Other options are seen at the source at :py:mod:`armi.reactor.components`.


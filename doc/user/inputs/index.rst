******
Inputs
******

ARMI input files define the initial state of the reactor model and tell ARMI what kind of analysis should be
performed on it.

.. note:: We have an :doc:`input walkthrough </tutorials/walkthrough_inputs>` tutorial for a quick 
    overview of th inputs.

There are several input files:

Settings file
	Contains simulation parameters (like full power, cycle length, and which physics modules to
  	activate) and all kind of modeling approximation settings (e.g. convergence criteria)

Blueprints file
	Contains dimensions and composition of the components/blocks/assemblies in your reactor systems, from fuel 
  	pins to heat exchangers
 
Core map file
	Describes where various assemblies (defined in blueprints) exist in a core relative to one another

Fuel management file
	Describes how fuel moves around during a simulation


Depending on the type of analysis, there may be additional inputs required. These include things like
control logic, ex-core models for transients and shielding, etc.

The core map input files can be graphically manipulated with the 
:py:mod:`Grid editor <armi.utils.gridEditor>`.


-----------

.. toctree::

   settings
   blueprints
   facemap_file
   fuel_management
   settings_report

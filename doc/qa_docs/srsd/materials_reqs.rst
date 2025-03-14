.. _armi_mats:

Materials Package
-----------------

This section provides requirements for the :py:mod:`armi.materials` package within the framework, which contains ARMI's system for defining materials. The materials system in ARMI allows for an extreme amount of flexibility in defining materials with temperature-dependent properties like density, linear expansion factor, and the like.

ARMI also comes packaged with a small set of basic materials, though these are meant only as example materials and (because ARMI is open source) these materials can not include proprietary or classified information. As such, we explicitly forbid the use of the example ARMI materials in safety-related modeling and will not be writing requirements on those materials.


Functional Requirements
+++++++++++++++++++++++

.. req:: The materials package shall allow for material classes to be searched across packages in a defined namespace.
    :id: R_ARMI_MAT_NAMESPACE
    :subtype: functional
    :basis: This is just a design choice in ARMI, to define how new material definitions are added to a simulation.
    :acceptance_criteria: Import a material class from a package in the ARMI default namespace.
    :status: accepted

.. req:: The materials package shall allow for multiple material collections to be defined with an order of precedence in the case of duplicates.
    :id: R_ARMI_MAT_ORDER
    :subtype: functional
    :basis: The ability to represent physical material properties is a basic need for nuclear modeling.
    :acceptance_criteria: Only the preferred material class is returned when multiple material classes with the same name are defined.
    :status: accepted

.. req:: The materials package shall provide the capability to retrieve material properties at different temperatures.
    :id: R_ARMI_MAT_PROPERTIES
    :subtype: functional
    :basis: The ability to represent physical material properties is a basic need for nuclear modeling.
    :acceptance_criteria: Instantiate a Material instance and show that the instance has the appropriate method names defined and examine the methods signatures to ensure they allow for temperature inputs.
    :status: accepted

.. req:: The materials package shall allow for user-input to impact the materials in a component.
    :id: R_ARMI_MAT_USER_INPUT
    :subtype: functional
    :basis: The ability to represent physical material properties is a basic need for nuclear modeling.
    :acceptance_criteria: Instantiate a reactor from blueprints that uses the material modifications and show that the modifications are used.
    :status: accepted

.. req:: Materials shall generate nuclide mass fractions at instantiation.
    :id: R_ARMI_MAT_FRACS
    :subtype: functional
    :basis: The ability to represent physical material properties is a basic need for nuclear modeling.
    :acceptance_criteria: Show that the material mass fractions are populated when the object is created.
    :status: accepted

.. req:: The materials package shall provide a class for fluids that defines the thermal expansion coefficient as identically zero.
    :id: R_ARMI_MAT_FLUID
    :subtype: functional
    :basis: Thermal expansion coefficients need to be zero for fluids so that fluid components cannot drive thermal expansion of their own or linked component dimensions.
    :acceptance_criteria: Instantiate a Fluid material and show that its linear expansion is identically zero.
    :status: accepted

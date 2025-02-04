.. _armi_physics:

Physics Package
---------------

This section provides requirements for the :py:mod:`armi.physics` package within the framework, which contains interfaces for important physics modeling and analysis in nuclear reactors. It is important to note that ARMI is a framework, and as such does not generally include the actual science or engineering calculations for these topics. For instance, ARMI has an interface for "safety analysis", but this interface is just a *place* for developers to implement their own safety analysis code. It would be inappropriate to include the actual science or engineering calculations for a detailed safety analysis of a particular reactor in ARMI because ARMI is meant only to house the code to let nuclear modeling and analysis work, not the analysis itself.



Functional Requirements
+++++++++++++++++++++++

.. ## globalFlux ######################

.. req:: placeholder
    :id: R_ARMI_FLUX_CHECK_POWER
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_FLUX_OPTIONS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_FLUX_GEOM_TRANSFORM
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_FLUX_RX_RATES
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_FLUX_DPA
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## isotopicDepletion ######################

.. req:: placeholder
    :id: R_ARMI_DEPL_TABLES
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_DEPL_ABC
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## energyGroups ######################

.. req:: placeholder
    :id: R_ARMI_EG_NE
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_EG_FE
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## macroXSGenerationInterface ######################

.. req:: placeholder
    :id: R_ARMI_MACRO_XS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## executers ######################

.. req:: placeholder
    :id: R_ARMI_EX
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted


.. ## fuelCycle ######################

.. req:: placeholder
    :id: R_ARMI_SHUFFLE
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_SHUFFLE_STATIONARY
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_ROTATE_HEX
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_ROTATE_HEX_BURNUP
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. ## crossSectionGroupManager ######################

.. req:: placeholder
    :id: R_ARMI_XSGM_FREQ
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_XSGM_CREATE_XS_GROUPS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

.. req:: placeholder
    :id: R_ARMI_XSGM_CREATE_REPR_BLOCKS
    :subtype: functional
    :basis: placeholder
    :acceptance_criteria: placeholder
    :status: accepted

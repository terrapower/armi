.. _armi_nuc_dirs:

Nuclide Directory Package
-------------------------

This section provides requirements for the :py:mod:`armi.nucDirectory` package within the framework, which
is responsible for defining elemental and isotopic information that is used for reactor physics evaluations.

Functional Requirements
+++++++++++++++++++++++

.. req:: The nucDirectory package shall provide an interface for querying basic data for elements of the periodic table.
    :id: R_ARMI_ND_ELEMENTS
    :subtype: functional
    :basis: Element data is needed for converting between mass and number fractions, expanding elements into isotopes, and other tasks.
    :acceptance_criteria: Query elements by Z, name, and symbol.
    :status: accepted

.. req:: The nucDirectory package shall provide an interface for querying basic data for important isotopes and isomers.
    :id: R_ARMI_ND_ISOTOPES
    :subtype: functional
    :basis: Isotope data is used to aid in construction of cross-section generation models, to convert between mass and number fractions, and other tasks.
    :acceptance_criteria: Query isotopes and isomers by name, label, MC2-3 ID, MCNP ID, and AAAZZZS ID.
    :status: accepted

.. req:: The nucDirectory package shall store data separately from code.
    :id: R_ARMI_ND_DATA
    :subtype: functional
    :basis: Storing data separately from code is good practice in scientific programs.
    :acceptance_criteria: The nucDirectory element, isotope, and isomer data is stored in plain text files in a folder next to the code.
    :status: accepted

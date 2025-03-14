.. _armi_utils:

Utilities Package
-----------------

This section provides requirements for the :py:mod:`armi.utils` package within the framework, which is one of the smaller high-level packages in ARMI. This package contains a small set of basic utilities which are meant to be generally useful in ARMI and in the wider ARMI ecosystem. While most of the code in this section does not rise to the level of a "requirement", some does.



Functional Requirements
+++++++++++++++++++++++

.. req:: ARMI shall provide a utility to convert mass densities and fractions to number densities.
    :id: R_ARMI_UTIL_MASS2N_DENS
    :subtype: functional
    :basis: This is a widely used utility.
    :acceptance_criteria: Provide a series of mass densities and fractions and verify the returned number densities.
    :status: accepted

.. req:: ARMI shall provide a utility to expand elemental mass fractions to natural nuclides.
    :id: R_ARMI_UTIL_EXP_MASS_FRACS
    :subtype: functional
    :basis: This is a widely used utility.
    :acceptance_criteria: Expand an element's mass into a list of it's naturally occurring nuclides and their corresponding mass fractions.
    :status: accepted

.. req:: ARMI shall provide a utility to format nuclides and densities into an MCNP material card.
    :id: R_ARMI_UTIL_MCNP_MAT_CARD
    :subtype: functional
    :basis: This will be useful for downstream MCNP plugins.
    :acceptance_criteria: Create an MCNP material card from a collection of densities.
    :status: accepted

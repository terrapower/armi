# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This module contains the definition of :py:class:`~Transmutation` and :py:class:`~Decay` classes.

.. inheritance-diagram::
    Transmutation DecayMode

The mappings between active nuclides during transmutation and decay are described in a
``burn-chain.yaml`` file pointed to by the ``burnChainFileName``
setting. This file contains one entry per nuclide that can transmute or decay that
look similar to the example below::

    U238:
    - nuSF: 2.0000
    - transmutation:
        branch: 1.0
        products:
        - NP237
        type: n2n
    - transmutation:
        branch: 1.0
        products:
        - LFP38
        type: fission
    - transmutation:
        branch: 1.0
        products:
        - NP239
        - PU239
        type: nGamma
    - decay:
        branch: 5.45000e-07
        halfLifeInSeconds: 1.4099935680e+17
        products:
        - LFP38
        type: sf

This example defines 3 transmutations (an ``(n,2n)`` reaction, an ``(n,fission)`` reaction, an
``(n,gamma``)`` reaction), and a spontaneous fission decay reaction with a very low branching
ratio. Valid reaction ``type`` values are listed in :py:class:`~armi.nucDirectory.transmutations.Transmutation`
and :py:class:`~armi.nucDirectory.transmutations.DecayMode`.

The ``branch`` entry determines the fraction of the products of a given reaction that will end up
in a particular product. The branches must never sum up to anything other than 1.0.

The ``products`` entry is a list, but only one entry will be the actual product. The list defines
a preference order. For example, if ``NP239`` is being tracked as an active nuclide in the problem
it will be the product of the ``nGamma`` reaction above. Otherwise, ``U238`` will transmute directly
to the alternate product, ``PU239``.

.. warning:: If you track very short-lived decays explicitly then the burn matrix becomes very
             ill-conditioned and numerical solver issues can result. Specialized matrix
             exponential solvers (e.g. CRAM [1]) are required to get adequate solutions in these cases [2].

The example above also defines a ``nuSF`` item, which is how many neutrons are emitted per spontaneous
fission. This is used for intrinsic source term calculations.

[1] Pusa, Maria, and Jaakko Leppanen. "Computing the matrix exponential in burnup calculations."
    Nuclear science and engineering 164.2 (2010): 140-150.

[2] Moler, Cleve, and Charles Van Loan. "Nineteen dubious ways to compute the exponential of a matrix."
    SIAM review 20.4 (1978): 801-836.
"""

import math

from armi import runLog
from armi.utils import iterables

LN2 = math.log(2)

TRANSMUTATION_TYPES = ["n2n", "fission", "nGamma", "nalph", "np", "nd", "nt"]

DECAY_MODES = [
    "bmd",  # beta minus
    "bpd",  # beta plus
    "ad",  # alpha decay
    "ec",  # electron capture
    "sf",
]  # spontaneous-fission

PRODUCT_PARTICLES = {"nalph": "HE4", "np": "H1", "nd": "H2", "nt": "H3", "ad": "HE4"}


class Transmutable:
    """
    Transmutable base class.

    Attributes
    ----------
    parent : NuclideBase
        The parent nuclide in this reaction.
    type : str
        The type name of reaction (e.g. ``n2n``, ``fission``, etc.)
    productNuclides : list
        The names of potential product nuclides of this reaction, in order of preference.
        Multiple options exist to allow the library to specify a transmutation
        to one nuclide if the user is modeling that nuclide, and other ones
        as fallbacks in case the user is not tracking the preferred product.
        Only one of these products will be created.
    productParticle : str
        The outgoing particle of this reaction. Could be HE4 for n,alpha, etc.
        Default is None.
    branch : float
        The fraction of the time that this transmutation occurs. Should be between
        0 and 1. Less than 1 when a decay or reaction can branch between multiple productNuclides.
        Do not make this >1 to get more than one product because it scales the reaction cross section
        which will double-deplete the parent.

    Notes
    -----
    These are used to link two :py:class:`~armi.nucDirectory.nuclideBases.NuclideBase` objects through transmutation or
    decay.

    See Also
    --------
    Transmutation
    DecayMode
    """

    def __init__(self, parent, dataDict):
        self.parent = parent
        self.type = dataDict["type"]
        self.productNuclides = tuple(dataDict["products"])
        self.productParticle = dataDict.get("productParticle", PRODUCT_PARTICLES.get(self.type))
        self.branch = dataDict.get("branch", None)
        if self.branch is None:
            self.branch = 1.0
            runLog.info(f"The branching ratio for {self} was not defined and is assumed to be 1.0.")

    def getPreferredProduct(self, libraryNucNames):
        """
        Get the index of the most preferred transmutation product/decay daughter.

        Notes
        -----
        The ARMI burn chain is not a full burn chain. It short circuits shorter half-lives, and uses lumped nuclides
        as catch-all objects for things that just sit around. Consequently, the "preferred" product/daughter
        may not be actual physical product/daughter.
        """
        for product in self.productNuclides:
            if product in libraryNucNames:
                return product
        groupedNames = iterables.split(libraryNucNames, max(1, int(len(libraryNucNames) / 10)))
        msg = "Could not find suitable product/daughter for {}.\nThe available options were:\n  {}".format(
            self, ",\n  ".join(", ".join(chunk) for chunk in groupedNames)
        )
        raise KeyError(msg)


class Transmutation(Transmutable):
    r"""
    A transmutation from one nuclide to another.

    Notes
    -----
    The supported transmutation types include:

    * :math:`n,2n`
    * :math:`n,fission`
    * :math:`n,\gamma` (``nGamma``)
    * :math:`n,\alpha` (``nalph``)
    * :math:`n,p` (proton) (``np``)
    * :math:`n,d` (deuteron) (``nd``)
    * :math:`n,t` (triton) (``nt``)
    """

    def __init__(self, parent, dataDict):
        Transmutable.__init__(self, parent, dataDict)
        if self.type not in TRANSMUTATION_TYPES:
            raise KeyError("{} not in {}".format(self.type, TRANSMUTATION_TYPES))

    def __repr__(self):
        return "<Transmutation by {} from {:7s} to {} with branching ratio of {:12.5E}>".format(
            self.type, self.parent.name, self.productNuclides, self.branch
        )


class DecayMode(Transmutable):
    r"""Defines a decay from one nuclide to another.

    Notes
    -----
    The supported decay types are also all transmutations, and include:

    * :math:`\beta^-` (``bmd``)
    * :math:`\beta^+` (``bpd``)
    * :math:`\alpha` (``ad``)
    * Electron capture (``ec``)
    * Spontaneous fission (``sf``)

    Of note, the following are not supported:

    * Internal conversion
    * Gamma decay
    """

    def __init__(self, parent, dataDict):
        Transmutable.__init__(self, parent, dataDict)
        self.halfLifeInSeconds = parent.halflife

        # Check for user-defined value of half-life within the burn-chain data. If this is
        # updated then prefer the user change and then note this to the user. Otherwise,
        # maintain the default loaded from the nuclide bases.
        userHalfLife = dataDict.get("halfLifeInSeconds", None)
        if userHalfLife:
            if userHalfLife != parent.halflife:
                runLog.info(
                    f"Half-life provided for {self} will be updated from "
                    f"{parent.halflife:<15.11e} to {userHalfLife:<15.11e} seconds based on "
                    "user provided burn-chain data."
                )

                self.halfLifeInSeconds = userHalfLife
        self.decay = LN2 / self.halfLifeInSeconds * self.branch  # decay constant, reduced by branch to make it accurate

        if self.type not in DECAY_MODES:
            raise KeyError("{} is not in {}".format(self.type, DECAY_MODES))

    def __repr__(self):
        return "<DecayMode by {} from {:7s} to {} with a half-life of {:12.5E} s>".format(
            self.type,
            self.parent.name,
            self.productNuclides,
            self.halfLifeInSeconds,
        )

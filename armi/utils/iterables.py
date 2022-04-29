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
Module of utilities to help dealing with iterable objects in python
"""
import struct
from itertools import tee, chain

from builtins import object  # pylint: disable=redefined-builtin
from six.moves import filterfalse, map, xrange, filter


def flatten(l):
    """Flattens an iterable of iterables by one level

    Examples
    --------
    >>> flatten([[1,2,3,4],[5,6,7,8],[9,10]])
    [1,2,3,4,5,6,7,8,9,10]

    """
    return [item for sublist in l for item in sublist]


def chunk(l, n):
    r"""Returns a generator object that yields lenght-`n` chunks of `l`.
    The last chunk may have a length less than `n` if `n` doesn't divide
    `len(l)`.

    Examples
    --------
    >>> list(chunk([1,2,3,4,5,6,7,8,9,10], 4))
     [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]]

    """
    for i in xrange(0, len(l), n):
        yield l[i : i + n]


def split(a, n, padWith=()):
    r"""
    Split an iterable `a` into `n` sublists.

    Parameters
    ----------
    a : iterable
        The list to be broken into chunks

    n : int
        The number of "even" chunks to break this into. There will be this many
        entries in the returned list no matter what. If len(a) < n,
        error unless padWith has been set. If padWithNones is true, then the output
        will be padded with lists containing a single None.

    padWith : object, optional
        if n > len(a), then the result will be padded to length-n by appending `padWith`.

    Returns
    -------
    chunked : list[len=n] of lists

    Examples
    --------
    >>> split([1,2,3,4,5,6,7,8,9,10],4)
     [[1, 2, 3], [4, 5, 6], [7, 8], [9, 10]]

    >>> split([0,1,2], 5, padWith=None)
     [[0], [1], [2], None, None]
    """

    a = list(a)  # in case `a` is not list-like
    N = len(a)

    assert n > 0, "Cannot chunk into less than 1 chunks. You requested {0}".format(n)

    k, m = divmod(N, n)
    chunked = [
        a[i * k + min(i, m) : (i + 1) * k + min(i + 1, m)] or padWith for i in xrange(n)
    ]
    return chunked


# -------------------------------


def unpackBinaryStrings(binaryRow):
    """Unpacks a row of binary strings to a list of floats"""
    if len(binaryRow) % 8:
        raise ValueError(
            "Cannot unpack binary strings from misformatted row. Expected chunks of size 8."
        )
    return [(struct.unpack("<d", barray)[0]) for barray in chunk(binaryRow, 8)]


def packBinaryStrings(valueDict):
    """Converts a dictionary of lists of floats into a dictionary of lists of byte arrays"""
    bytearrays = {}
    for entry in valueDict:
        bytearrays[entry] = [bytearray()]

        for value in valueDict[entry]:
            bytearrays[entry][0].extend(struct.pack("<d", value))

    return bytearrays


def unpackHexStrings(hexRow):
    """Unpacks a row of binary strings to a list of floats"""
    return [float.fromhex(ss) for ss in hexRow.split() if ss != ""]


def packHexStrings(valueDict):
    """Converts a dictionary of lists of floats into a dictionary of lists of hex values arrays"""
    hexes = {}
    for entry in valueDict:  # uglier loop done for compatability with cython
        hexes[entry] = [" ".join(float.hex(float(value)) for value in valueDict[entry])]
    return hexes


# -------------------------------


class Overlap:
    """common list overlap comparison"""

    def __init__(self, src, ref):
        src_set, ref_set = set(src), set(ref)
        self.matched = ref_set.intersection(src_set)
        self.src_missed = src_set.difference(ref_set)
        self.ref_missed = ref_set.difference(src_set)

    def __bool__(self):
        """Check if content between the lists is a perfect match"""
        return not bool(self.src_missed) and not bool(self.ref_missed)

    __nonzero__ = __bool__  # py2

    def __str__(self):
        return "- Overlap -\n\tmatched: {}\n\tsrc_missed: {}\n\tref_missed: {}".format(
            self.matched, self.src_missed, self.ref_missed
        )


class Sequence:
    """
    The Sequence class partially implements a list-like interface,
    supporting methods like append and extend and also operations like + and +=.
    It also provides some convenience methods such as drop and select to support
    filtering, as well as a transform function to modify the sequence. Note that
    these methods return a "cloned" version of the iterator to support chaining,
    e.g.,
    >>> s = Sequence(range(1000000))
    >>> tuple(s.drop(lambda i: i%2 == 0).select(lambda i: i < 20).transform(lambda i: i*10))
    (10, 30, 50, 70, 90, 110, 130, 150, 170, 190)

    This starts with a Sequence over 1 million elements (not stored in memory),
    drops the even elements, selects only those whose value is less than 20, and
    multiplies the resulting values by 10, all while loading only one element
    at a time into memory. It is only when tuple is called that the operations
    are performed.

    drop, select, and transform act in-place, so the following is equivalent to
    the chained expression given above:
    >>> s = Sequence(range(1000000))
    >>> s.drop(lambda i: i%2 == 0)
    <Sequence at 0x...>
    >>> s.select(lambda i: i < 20)
    <Sequence at 0x...>
    >>> s.transform(lambda i: i*10)
    <Sequence at 0x...>
    >>> tuple(s)
    (10, 30, 50, 70, 90, 110, 130, 150, 170, 190)

    Note: that this class is intended for use with finite sequences. Don't attempt
    to use with infinite generators. For instance, the following will not work:

    >>> def counter():
    ...    i = 0
    ...    while True:
    ...        yield i
    ...        i += 1
    ...
    >>> s = Sequence(counter()).select(lambda i: i < 10)
    >>> tuple(s)  # DON'T DO THIS!

    Although the result should be (0,1,2,3,4,5,6,7,8,9), the select method is not
    smart enough to know that it's a terminal condition and will continue to
    check every number generated forever. One could remedy this by using the
    dropwhile and/or takewhile methods in the itertools module, but this has
    not been done.
    """

    def __init__(self, seq=None):
        """Constructs a new Sequence object from an iterable. This also serves
        as a copy constructor if seq is an instance of Sequence.
        """
        if seq is None:
            seq = []
        elif isinstance(seq, Sequence):
            seq = seq.copy()
        self._iter = iter(seq)

    def copy(self):
        """Return a new iterator that is a copy of self without consuming self."""
        self._iter, copy = tee(self._iter, 2)
        return Sequence(copy)

    def __iter__(self):  # pylint: disable=non-iterator-returned
        return self

    def __repr__(self):
        return "<{:s} at 0x{:x}>".format(self.__class__.__name__, id(self))

    def __next__(self):
        return next(self._iter)

    def select(self, pred):
        """Keep only items for which pred(item) evaluates to True

        Note: returns self so it can be chained with other filters, e.g.,

                newseq = seq.select(...).drop(...).transform(...)
        """
        self._iter = filter(pred, self._iter)
        return self

    def drop(self, pred):
        """Drop items for which pred(item) evaluates to True.

        Note: returns self so it can be chained with other filters, e.g.,

                newseq = seq.select(...).drop(...).transform(...)
        """
        self._iter = filterfalse(pred, self._iter)
        return self

    def transform(self, func):
        """Apply func to this sequence."""
        self._iter = map(func, self._iter)
        return self

    def extend(self, seq):
        self._iter = chain(self._iter, seq)

    def append(self, item):
        self.extend([item])

    def __radd__(self, other):
        new = Sequence(other)
        new += Sequence(self)
        return new

    def __add__(self, other):
        new = Sequence(self)
        new += Sequence(other)
        return new

    def __iadd__(self, other):
        self.extend(Sequence(other))
        return self

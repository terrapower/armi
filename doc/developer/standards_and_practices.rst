**********************************
Standards and Practices for Coding
**********************************

The ARMI coding standards are a set of guidelines for helping to create a more consistent and clear code base.
Subpart 2.7 402 of `NQA-1 <http://nqa-1.com/files/NQA-1%20Nuclear%20Quality%20Manual.pdf>`_ states, "Software
design verification shall evaluate... the design approach and ensure internal completeness, consistency, clarity
and correctness." While these are required by NQA-1, the idea is that an ARMI developer, who is familiar with
these coding standards, should be able to jump from one module to another without changing their coding style
(names, and practices).

.. tip ::
    :class: warning

    The overall theme is: **Balance clarity with conciseness.**

Just try to be as clear as possible, while using as few words as possible.

.. important ::
    Most of the guidelines can be broken, but all deviations need to be justified. It is up to the code reviewers
    to determine whether the justification was adequate.

    Developers and reviewers should consult the standards/guidelines while writing and reviewing code to ensure
    consistency. Code reviewers should make sure to be familiar with the standards, so that their comments are
    consistent with other reviewers.

Code formatting with Black
==========================
ARMI uses the Python code formatter `black <https://pypi.org/project/black/>`_. So while developing code in ARMI
it is important to remember to us the ``black`` formatter before pushing any code to the repo. All changes pushed
to ARMI on github.com will be automatically checked to see if they conform to the ``black`` code formatter standards.

The ``black`` formatter provides 100% consistency in ARMI for: whitespace, line length, trailing commas, and string
formatting.

Remove commented-out code
=========================
If you were testing code and you commented out a block, delete it before sending it in for code review/production.
If you want to see the old code later, it will still be in the Git history.

Avoid hard-coding run parameters
================================
Use the global settings object ``self.cs`` for most user-setable parameters that determine the run environment, etc. This
will help keep the amount of repeated code down.

Also, do not **ever** code the following things into the code: user names, passwords, or file paths on your computer. Use
environmental variables where possible and user-configurable settings elsewhere. You can also use the ``armi.ROOT``
variable (for the active code directory) or ``armi.RES``, and some other useful root-level variables.

Avoid the global keyword
========================
At all costs, avoid use of the ``global`` keyword in your code. Using this keyword can, and usually does, create
extremely fragile code that is nigh-impossible to use a debugger on. Especially as part of object-oriented programming,
this is extremely lazy design. A careful reader might notice that there are several files in ARMI that are currently
using the ``global`` keyword. These are all schedule for a refactor to remove the use of ``global``. But, for now,
changing the code would cause more annoyance for the ARMI ecosystem userbase than fixing it would. Still, all of those
instance in ARMI will be fixed soon.

No new uses of ``global`` will make it through the ARMI pull request process.

Naming conventions
==================

.. note::
   There is a good argument to make that ARMI's use of ``camelCase`` makes the code less readable than if ARMI
   used ``snake_case``. Unfortunately, making the switch now would affect such a large percentage of the API that
   it would be more hassle for our user base than it is worth to change.

Use meaningful names
--------------------
Use descriptive names for variables, functions, methods, classes, and files. This might mean using a longer name like
``correlationMatrix`` instead of a shorter one like ``cm``.

General conventions
-------------------

Here are some general naming guidelines that are always applicable, but particularly applicable to public classes,
functions, and methods and their signatures (the signature includes the parameters):

* Variables that you designate as unused should be prefaced with an underscore (``_``).
* Do not use Python `reserved keywords <https://realpython.com/lessons/reserved-keywords/>`_ as variable names.
* Try to use names that are pronounceable. (Well-established variable names from equations are exceptable.)
* Keep names concise and expressive. (An exception is test method names, which may be longer and more
  descriptive.)
* Avoid abbreviations and acronyms, unless they are well understood by subject-matter experts (e.g. DB for database,
  XS for cross-sections, BU for burn up). When using acronyms or abbreviations with ``camelCase`` or ``PascalCase``:

  * Use the same case for two-letter acronyms/abbreviations (e.g. ``diskIO``, ``ioOperation``)
  * Use different case for acronyms/abbreviations with more than two characters (e.g. ``renderHtml()``, ``path``)

For consistency, use the following naming conventions:

package names
    Python packages, i.e. folders with an ``__init__.py``, **shall** use ``camelCase``.

module names
    Python modules, i.e. python files, **shall** use ``camelCase``.

    **Caveat:** Test modules are prefixed with ``test_``.

module constants
    Module-level "constants" **shall** be all capitals with an underscore separating words.

function names
    Functions **shall** use ``camelCase``. If the function is only intended to be used within that module, prefix
    it with a single leading underscore to indicate it is "module protected."

variable names
    Use ``camelCase``. In the odd scenario that the variable is not used (e.g. a method returns a
    tuple and you only want the first item), prefix it with a single leading underscore to indicate it is
    "module protected."

class names
    Classes **shall** use ``PascalCase``. If the class is only intended to be inherited by other classes within
    the module, prefix the class name with an underscore to indicate it is "module protected."

class attribute, instance attribute and method names
    Use ``camelCase``. If the method is only intended to be used within that module, prefix it with a single
    leading underscore to indicate it is "class protected."

Naming quick-reference
----------------------

.. list-table::
    :widths: 40 30 30
    :header-rows: 1

    * - Item to be named
      - Public
      - Private
    * - package

        (folder with an ``__init__.py``)
      - ``packageName``
      - N/A
    * - module

        (a ``.py`` file)
      - ``moduleName``
      - N/A
    * - module constant
      - ``SPEED_OF_LIGHT_IN_METERS_PER_SECOND``
      - ``_ONE_OVER_PI``
    * - method or function
      - ``doSomeAction()``
      - ``_doSomeAction()``
    * - class or instance attribute
      - ``assemblies``
      - ``_assemblies``
    * - variable names
      - ``linearHeatGenerationRate``
      - ``_unusedDescription``

        There are not "private" variables, use this for an unused variable.

Common naming conventions within ARMI
-------------------------------------
Single character variable names are not usually "clear" or "concise"; however, the following variables are a
well-established convention within ARMI and should be used by developers:

    * ``r`` when referring to a reactor, and
    * ``o`` when referring to a operator

Other names are also consistently used throughout ARMI for specific objects:

* ``cs`` when referring to a :py:class:``armi.settings.Settings`` class; this should not be confused with
  the ``.settings`` attribute of ``ArmiObject``.
* ``lib`` when referring to a cross section library (would have been better as ``xsLib``)


Prefer shorter methods
======================
A method should have one clear purpose. If you are writing a method that does one thing after the other,
break it up into multiple methods and have a primary method call them in order. If your method is longer
than 100 lines, see if you can't break it up. This does a few things:

1. It makes the code easier to read.
2. It makes the code chunks more reusable.
3. It makes the code easier to test.
4. It makes the code easier to profile, for performance.

Avoid repeating code
====================
In other words, don't repeat yourself. (`D. R. Y. <https://en.wikipedia.org/wiki/Don't_repeat_yourself>`_).
Repetitious code is harder to read, and harderd for others to update. If you ever find yourself copying and pasting
code, consider pulling the repeated code out into it's own function, or using a loop.

Public methods should have docstrings
=====================================
Always create the :doc:`proper docstrings </developer/code_practices/documentation_guidelines>` for all public
functions and public classes.

Unit tests
==========
All ARMI developers are required to write unit tests. In particular, if you are adding new code to the code base, you
are required to add unit tests for your new code.

ARMI uses the ``pytest`` library to drive tests, therefore tests need to be runnable from the commandline by
``python -m pytest armi``. Furthermore, for consistency:

* Each individual unit test should take under 10 seconds, on a modern laptop.
* All unit tests together should take under 60 seconds, on a modern laptop.
* All unit tests should be placed into a separate module from production code that is prefixed with ``test_``.
* All unit tests should be written in object-oriented fashion, inheriting from ``unittest.TestCase``.
* All test method names should start with ``test_``.
* All test method names should be descriptive. If the test method is not descriptive enough, add a docstring.
* Unit tests should have at least one assertion.

Import statements
=================
Python allows many variations on the import statement, including relative imports, renaming and others. We prefer:

#. one import per line,
#. no relative imports
#. no periods
#. explicit module/namespace usage

Import ordering
---------------
For consistency, import packages in this order:

1. Python built-in packages
2. External third-party packages
3. ARMI modules

Place a single line between each of these groups, for example:

.. code-block:: python
    :linenos:

    import os
    import math

    import numpy
    from matplotlib import pyplot

    from armi import runLog

Don't create naked exceptions.
==============================
When creating ``try``/``except`` blocks, a naked exception is when the ``except`` command is not
followed by a specific exception type. Naked exceptions hide a lot of sins, particularly unexpected
bugs. `This article <http://www.wilfred.me.uk/blog/2013/11/03/no-naked-excepts/>`_ explains the concept well,
as well as a few exceptions to this general rule.

Examples:

Bad

::

    >>> try:
    >>>     stuff()
    >>> except:
    >>>     runLog.warning('Some error occurred in stuff().')

Good (for one exception type)

::

    >>> try:
    >>>     stuff()
    >>> except AttributeError:
    >>>     runLog.warning('Some error occurred in stuff().')

Good (for multiple exception types)

::

    >>> try:
    >>>     stuff()
    >>> except (ZeroDivisionError, FloatingPointError):
    >>>     runLog.warning('Some error occurred in stuff().')


Data model
==========
Any reactor state information that is created by an ``Interface`` should be stored in the ARMI data model. The goal
is that given minimal information (i.e. case settings and blueprints) ARMI should be able to load an entire reactor
simulation from a given database. If you add state data to your modeling that isn't stored in the reactor, or add
new input files, you will break this paradigm and make everyone's life just a little bit harder.

Input files
===========
ARMI developers **shall** use one of the following well-defined, Python-supported, input file formats.

.json
    JSON files are used for a variety of data-object representations. There are some limitations of JSON, in that it
    does not easily support comments. JSON is also very strict.

.yaml
    YAML files are like JSON files but can have comments in them.

Address the pylint warnings
===========================
Our pull request system integrates with the automatic code checker, pylint. Any new code you add must have
zero pylint warnings or errors.

General do's and don'ts
=======================

do not use ``print``
    ARMI code should not use the ``print`` function; use one of the methods within ``armi.runLog``.

do not use ``super``
    In preference to the ``super`` function, explicitly call the parent object's method. For example, in an
    ``__init__``, use ``ParentClass.__init__(self, plus, additional, arguments)``.

do not leave ``TODO`` statements in production code
    If your ``TODO`` statement is important, perhaps it should be a GitHub Issue.

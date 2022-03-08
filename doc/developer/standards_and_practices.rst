**********************************
Standards and Practices for Coding
**********************************

The ARMI coding standards are a set of *guidelines* for helping to create a more consistent and clear code base.
Subpart 2.7 402 of NQA-1 states, "Software design verification shall evaluate ... the design approach and ensure
internal completeness, consistency, clarity and correctness." While these are required by NQA-1,
the idea is that an ARMI developer, who is familiar with these coding standards, should be able to jump from one
module to another without changing their coding style (names, and practices).

.. tip ::
    :class: warning

    The overall theme is: **Balance clarity with conciseness.**

Just try to be as clear as possible, while using as few words as possible.

.. important ::
    Most of the guidelines can be broken, but all deviations need to be justified as to why it was acceptable to do
    differently. It is up to the code reviewers to determine whether the justification was adequate to deviate from
    these standards.

    Developers and reviewers should consult the standards/guidelines while writing and reviewing code to ensure
    consistency. Code reviewers, specifically, should make sure to be familiar with the standards, so that their
    comments are consistent with other reviewers. Reviewers also need to put personal preference aside for the
    "greater good."

ARMI developers are required to address all PyLint warnings, and remove all PyLint errors. A special PyLint
configuration file is contained within the solution (``/armi/pylintrc``), and it should be used during
development to ensure code quality and consistency. Many of the items identified in this document are enforced
through the PyLint checker.

General do's and don'ts
=======================

do not use ``print``
    ARMI code should not use the ``print`` function; use one of the methods within ``armi.runLog``.

do not use ``super``
    In preference to the ``super`` function, explicitly call the parent object's method. For example, in an
    ``__init__``, use ``ParentClass.__init__(self, plus, additional, arguments)``.

do not create methods using ``*args`` or ``**kwargs``
    The usage of ``*args`` and ``**kwargs`` is generally not very clear, and can lead to inconsistent usage of the
    method.

do not leave ``TODO`` statements in production code
    NQA-1 requires that the code be "complete", and a ``TODO`` statement leaves the code looking
    incomplete. Therefore, do not leave ``TODO`` statements within production code. Instead, open a ticket.

Naming conventions
==================
Generically, all names should be clear and concise. It can take lots of time to determine the correct name for a
package, module, class, method or function. Spending the time is beneficial to fellow developers, users and future
versions of yourself.

.. note::
    There is great debate on the official definition of camel case. We are using the definition that
    ``camelCase`` has the first letter lower case and other words capitalized, and that ``PascalCase`` has
    all words capitalized.

Here are some general naming guidelines that are always applicable, but particularly applicable to public classes,
functions, and methods and their signatures (the signature includes the parameters):

* Try to use names that are pronounceable. If you're performing calculations, using variable names from the
  well-established equation is appropriate.
* Keep names concise and expressive. An exception is test method names, which may be longer and more
  descriptive.
* Avoid abbreviations and acronyms, unless they are well understood by subject-matter experts (e.g. DB for database,
  XS for cross-sections, BU for burn up). When using acronyms or abbreviations with ``camelCase`` or ``PascalCase``:

  * use the same case for two-letter acronyms/abbreviations (e.g. ``diskIO``, ``ioOperation``)
  * use different case for acronyms/abbreviations with more than two characters (e.g. ``renderHtml()``, ``path``)

* In object-oriented design, classes behave as entities which are capable of performing actions (methods) and
  have certain characteristics (attributes). For example, a ``Person`` class may have a ``talk()`` method with a
  ``_nativeLanguage`` attribute.

  Therefore, the following general rules exist for naming:

  * Class names should, under most circumstances, be nouns
  * Function and method names should, under most circumstances, be verbs.
  * Attributes are often nouns or adjectives, but are not as clear as classes, functions, and methods.

For consistency, use the following naming conventions:

package names
    Python packages, i.e. folders with an ``__init__.py``, **shall** use ``camelCase``.

module names
    Python modules, i.e. python files, **shall** use ``camelCase``.

    **Caveat:** Test modules are prefixed with ``test_``.

module constants
    Module "constants" **shall** be all capitals with an underscore separating words.

    .. note::
        There is no such thing as a constant in Python. The idea behind a module constant is that it should
        not be modified by anyone outside the module, and it is considered constant after loading the module.
        There is a caveat for package constants, in that they would be defined while loading the entire package.

function names
    Functions **shall** use ``camelCase``. If the function is only intended to be used within that module, prefix
    it with a single leading underscore to indicate it is "module protected."

    .. note::
        Python will name mangle anything with two leading underscores such that it is **not as easily** accessed
        outside the normal scope of usage. Since PyLint already warns against using "protected", single underscore,
        and we are going to require addressing all PyLint warnings, using a single underscore provides enough
        protection for our intelligent users/developers.

variable names
    Use ``camelCase``. In the odd scenario that the variable is not used (e.g. a method returns a
    tuple and you only want the first item), prefix it with a single leading underscore to indicate it is
    "module protected."

class names
    Classes **shall** inherit from ``object`` and use ``PascalCase``. If the class is only intended to be
    inherited by other classes within the module, prefix the class name with an underscore to indicate it is
    "module protected."

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

        ``lhgr`` if it is commonly used by subject-matter experts.
      - ``_unusedDescription``

        There are not "private" variables, use this for an unused variable.

Common naming conventions within ARMI
-------------------------------------
Single character variable names are not usually "clear" or "concise"; however, the following variables are a
well-established convention within ARMI and should be used by developers:

    * ``r`` when referring to a reactor, and
    * ``o`` when referring to a operator

    This is true for variables, class attributes, and instance attributes.

Other names are also consistently used throughout ARMI for specific objects:

* ``cs`` when referring to a :py:class:``armi.settings.Settings`` class; this should not be confused with
  the ``settings`` attribute of ``ArmiObject``.
* ``lib`` when referring to a cross section library (would have been better as ``xsLib``)


Break large methods into operative sections.
============================================

A method should do one obvious thing. If you are writing a method that does one thing after the other,
break it up into multiple methods and have a master method call them in order. If your method is longer
than two pages (in general), see if you can't break it up. This does a few things:

1. The master method reads like an outline, and another developer can see at a glance the details of
   what the method is doing.
2. The operative chunks might be reusable. If they're broken up nicely, it's very easy to call them from
   somewhere else. If they're all together, you'll end up repeating code.
3. The operative chunks can be individually tested without calling the other code
4. The code is broken up into small self-contained chunks that are easier to keep readable and efficient.
   There aren't hundreds of variable names around, etc. This leads to cleaner code. Also, the
   docstrings explain exactly what is going on at each step.
5. The individual methods will show up in the profiler, allowing you to easily identify
   performance bottlenecks.

Use meaningful, useful names
============================
Give descriptive names. Methods and functions should have verb names and other objects should be nouns.
Prefer ``correlationMatrix`` to ``cm``, etc. Often, it makes sense to put units in the name, like ``heightInCm``.

Avoid repeating code
====================
In other words, keep the code `D. R. Y. <https://en.wikipedia.org/wiki/Don't_repeat_yourself>`_
When repeated code gets updated, it takes the updater x times more time where x is the number of times you repeated the
code. It also has to be tested x times and will break x times if it is buggy. It cannot be stressed enough
that you should not repeat code. Many engineers like to repeat code. Don't do it. A good computer science guide is called
`Design patterns: Elements of reusable object oriented software. <http://www.amazon.com/Design-Patterns-Elements-Reusable-Object-Oriented/dp/0201633612/ref=sr_1_1?ie=UTF8&qid=1377805408&sr=8-1&keywords=design+patterns+reusable+code>`_
If you are copying and pasting code ever, follow these steps:

1.  Delete what you pasted.
2.  Think about how to reuse the original code in a nice elegant fashion (usually, factor it out as a method)
3.  If you can't come up with a way to do it, consult with your coworkers.
4.  Write nice elegant code that isn't repeated.

Use comments only when you cannot express what you're doing with names
======================================================================
Use comments sparingly. This is important because often code gets updated but comments do not, and their obsolescence
adds confusion, misdirection, and a maintenance burden.
Strive to express what the code is doing and why with descriptive variable and method names, and code structure.
Of course, for complex code, comments will invariably be necessary and useful.

Separate object construction into a different object
====================================================
Say you have a big matrix that you can read from a special structured file. There might be a lot of code
to read and write that structured file. Keep this I/O code in a different class than the big matrix itself.
In other words, separate construction from representation.

Avoid hard-coding user-changeable parameters
============================================
Use the global settings object ``self.cs`` for most user-setable parameters that determine the run environment, etc. This
will help keep the amount of repeated code down.

Also, do not **ever** code your username into a shared code-base. Use environmental
variables where possible and user-configurable settings elsewhere. You can also use the
``armi.ROOT`` variable (for the active code directory) or ``armi.RES``, and some other
useful root-level variables.

Public methods should have docstrings
=====================================
Always create the :doc:`proper docstrings </developer/code_practices/documentation_guidelines>`.
See for example, :py:mod:`armi.physics.neutronics.equilibriumCycle` for many more examples. Remember to make them
commands, not descriptions.

Address the pylint warnings
===========================
Our code review system and IDEs integrate with the automatic code checker, pylint.
All warnings that it gives are meaningful. Your code should have zero pylint warnings or errors in it.

Along these lines,
1. Unused variables that you mean to be unused can be prefaced with _ like _unusedVariable to avoid
   a warning there. This way it is clear that you the code writer meant for that to be an unused variable.
   If you have unused variables that you didn't mean to have there, then delete them so the code can be maintained
   easier
2. Don't use reserved words for variable names. Variables like sum, list, time, etc. are used in the
   Python library. While your code may run with them in there, there's no need to have that extra confusion.

Remove commented-out code
=========================
If you were testing code and you commented out a block, delete it before sending it in for code review/production.
If you want to see the old code later, you can find it via revision control.

Import statements
=================
Python allows many variations on the import statement, including relative imports, renaming and others. We prefer:

#. one import per line,
#. explicit relative imports only when the location of the import target is unambiguous,
   and unlikely to be relocated relative to the importing module (this usually makes
   sense within packages where the contained modules are all conceptually linked), and
#. explicit module/namespace usage, and
#. minimal periods!

Import ordering
---------------
For consistency, import packages in this order:

1. Python built-in packages
2. External 3rd party packages
3. ARMI modules

Place a single line between each of these groups, for example:

.. code-block:: python
    :linenos:

    import os
    import math

    import numpy
    from matplotlib import pyplot

    from armi import runLog

If you are not sure whether a package is considered 3rd party, try running this command::

    python -c "import <package>; print <package>.__file__"

The output of the command should show the full directory path to the package. If the path includes the directory
``<Python>\lib\site-pacakges``, then it is considered 3rd party.
More info, see `PEP 8 <http://www.python.org/dev/peps/pep-0008/>`_.

Specific package/namespace imports
----------------------------------
Do not do ``from os import path``; ``os.path`` is specifically handled, and should be used.

Do not use ``from matplotlib import pylab``, use ``from matplotlib import pyplot``. This doesn't violate any of our
guidelines, but the ``matplotlib`` documentation says to use ``pyplot``.

Import examples
---------------
Some examples of good and bad imports follow.

.. list-table:: **Import examples**
    :widths: 30 30 40
    :header-rows: 1

    * - Bad Statement
      - Good Statement
      - Discussion
    * - ``from . import runLog``
      - ``from armi import runLog``
      - The first example violates our desire to have **explicit imports**, and, in this particular instance, it also
        violates our desire to use **minimal periods**. For (a slightly contrived) justification of this distinction,
        XML and the periodic table both have elements, if I were to ``from . import elements`` you'd need knowledge of
        whether I was in the XML package or the periodic table package.

        A less contrived example could arise if we create
        wrappers for MCNP cross sections, in which case we'd have MCNP and MC\*\*2 nuclides with cross sections.

        Under some circumstances it is desirable to use relative imports. For instance,
        when deep inside a package hierarchy, relative imports may reduce the number of
        periods in the import statement. Also, in the case of code that may move,
        relative imports support portability. Use your best judgement when deciding
        between absolute or relative imports.
    * - ``import numpy as np``
      - ``import numpy``
      - The first example violates our desire to have **explicit module usage**; someone may be required to go to the
        top of the module to make sure the author used ``np`` for ``numpy``.

        Also, use of ``np`` throughout a module may be confusing for the author of the famed "non-polynomial" package.
    * - ``from pkg import PkgClass``
      - ``import pkg``
      - The first example violates our desire to have **explicit module usage**.
    * - ``import armi.runLog``
      - ``from armi import runLog``
      - The first example violates our desire to use **minimal periods**. Throughout the module, the developer
        will need to use ``os.path.``, further increasing the number of periods!
    * - ``from pkg import *``
      - ``import pkg``
      - Asterisk imports are unclear at best, and can have unintended side effects at worst.

Unit tests
==========
ARMI developers are required to write unit tests.
ARMI uses Python's ``unittest`` package for driving tests, therefore tests need to be runnable by ``python -m unittest``.
Furthermore, for consistency:

* All individual unit tests should take under 15 seconds.
* All unit tests **shall** be placed into a separate module from production code that is prefixed with ``test_``.
* All unit tests **shall** be written in object-oriented fashion, inheriting from ``unittest.TestCase``.
* All test methods **shall** start with ``test_``.
* All test methods **shall** be descriptive. If the test method is not descriptive enough, add a docstring.
* Unit tests should have at least one assertion. If there is no assertion, add a comment indicating what the test's
  purpose is and why it doesn't have any assertions.

Modifying behavior with arguments
=================================
Generally try to avoid modifying the behavior of methods with flag arguments like ``ignoreErrors=True``.
It's better to have ``doThing`` and ``doThingIgnoringErrors`` as two methods. They can still call
similar underlying code but this is just more explicit.

Spacing and line-length management
==================================
Part of maintaining consistent code is ensuring that anyone can read the with their setup. In order to facilitate this,
the ARMI project has a maximum line length of 120 characters. This is wide enough that it can accommodate concise
naming, but narrow enough that some users will be able to have two editors side-by-side (such as split in eclipse)
on a single monitor. Some rules and examples follow.

.. tip::
    General spacing rules:

    * Place a single space between object operators (e.g. ``+``, ``-``, ``/``, ``%``, ``*``, ``=``, ``|`` etc.),
      except when defining defaults within a method signature.
    * Place a single space after any comma.
    * When using parentheses (``(`` and ``)``), brackets (``[``, ``]``), or braces(``{`` and ``}``) place the
      arguments directly next to the parentheses / brackets /braces.
    * Place a single line between methods in a class. Use two blank lines to separate module-level functions and
      classes.

Adding space between operators is at odds with the 120 character line length, but it helps increase readability.

.. code-block:: python
    :linenos:

    space = between + operators / (butNot * parentheses)

    alsoPlace = space[betweenCommas, butNot, brackets]

    #same is true for braces
    greatDefintions = {'great-adj':'significantly better than average', 'great-n':'distinguished'}

    def methodsWithDefaultHaveNoSpaceAroundEquals(argument1, default=None):
        pass

    # random example
    cartesianPoint = (x, y)


    def methodSignatures(shouldHave, spacesBetween, arguments):
        # do something more amazing than
        pass


    class ThisClassWasSeparatedByTwoBlankLines(object):
        '''Description of this class'''

        def __init__(self):
            # implementation
            pass

        def singleBlankLineBetweenMethods(self):
            pass


    class OnceAgainTwoBlankLinesBetweenClasses(object):
        '''Description of this class'''
        pass

.. tip::
    When writing long log messages, align the ``.format`` inside the parentheses of the initial statement.

Often times log statements end up being pretty long in order to give the user enough information to make sense of the
message. This can lead to very long statements that would exceed 120 characters. This first example, shows a pretty
simple single-line message, with minimal arguments.

.. code-block:: python

    def whatever():
        important = 'irrelevant'
        pay = 'not'
        attention_to = 'care about'
        runLog.important('This message is really {}, you should really {} {} what is going on here!'
                         .format(important, pay, attention_to))
        #                ^ align overflow to inside the parentheses

.. tip::
    When writing really long log messages split it across multiple lines. If you're writing a pseudo-table,
    don't worry too much, but it's possible that information belongs in an ARMI report rather than the log.

Building on the last example, often times messages can be very verbose. It is important to consider the user
at this point, and similar to ARMI's 120 character limit, 120 characters, or less, may be appropriate for any given
line of the output so the user can see the entire message without scrolling within their text editor. Also, remember
that ARMI prefixes all lines with an indication of the line content (e.g. ``[IMPT 000 ] `` is an important message
from the master node).

.. code-block:: python

    def oddStateMessage(r, possibleAssemblyCount):
        runLog.warning('The current state of the reactor, {}, is chaos!\n'
                       'It is unclear whether reactor has any assemblies, or {} assemblies.\n'
                       'This condition should never occur; maybe check the distributeState method for something amiss.'
                       .format(r, possibleAssemblyCount))
        #              ^ align all of these
        # don't need a new line at the end of this one, it is automatically appended                                 ^

.. caution::
    Methods with really long signatures probably indicate some other issue. Specifically, methods with lots of arguments
    require a user (that may be another developer) of that method, to know a great deal about the method. In software
    development, this is called coupling, and the more you need to know the more **tightly** coupled the code is.

With that warning aside, sometimes there are cases where in order to call a method, the line becomes very long,
when this happens break the line for each argument, and align inside the parentheses of the method call.


.. code-block:: python

    def doSomethingWithAnAssembly(a):
        # in this psuedo-example, it would be better to pass the assembly and the additional arguments
        calculateSomething(a.p.height,
                           a.p.width,
                           a.components,
                           somefactor=1.333241,
                           failOnError=True,
                           cs=cs)


Don't create naked exceptions.
==============================
When creating try-except blocks, a naked exception is when the except command is not
followed by a specific exception type or types. In general, these naked exceptions
should be avoided in new code, and fixed in old code. The reason is that you don't
want to bury or ignore exceptions that you might not have anticipated. Try-except
blocks are very powerful, but with great power comes great responsibility.

`This article <http://www.wilfred.me.uk/blog/2013/11/03/no-naked-excepts/>`_ explains the concept well,
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
Any state information that is created by an interface, should be stored in the ARMI data model. The idea here, is that
given a small amount of information (i.e. case settings and geometry definition), ARMI should be able to load the
entire state for a given run from the database, for any time step in the database.

Input files
===========
When needing to read/retrieve information from a user or elsewhere, ARMI developers **shall** use one of the following
well defined, Python supported, input file formats.

.xml
    XML files are used to define the geometry, as well as case settings. XML files are not always considered *easily*
    human-readable, therfore they don't always make sense if you anticipate the user creating it manually.

.json
    JSON files are used for a variety of data-object representations. There are some limitations of JSON, in that it
    does not easily support comments. JSON is also very strict.

.yaml
	YAML files are like JSON files but can have comments in them.

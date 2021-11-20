Tooling and infrastructure
==========================

Packaging and dependency management
-----------------------------------
The process of packaging Python projects and managing their dependencies is somewhat
challenging and nuanced. The contents of our ``setup.py`` follow existing conventions as
much as possible. In particular, we follow `this fantastic article
<https://caremad.io/posts/2013/07/setup-vs-requirement/>`_ about dependecy management in
Python projects.

setup.py
^^^^^^^^
The packages listed in the ``install_requires`` argument to ``setup()`` are meant to
express, as abstractly as possible, the packages that need to be installed **somehow**
for the package to work. In addition, ``extras_require`` are used to specify other
packages that are not strictly required, but if installed enable extra functionality,
like unit testing or building documentation.

requirements.txt
^^^^^^^^^^^^^^^^
The ``requirements***.txt`` files exist to describe a complete environment more
specifically. If specific versions of packages are required, they should be defined here.
Any extra arguments to ``pip`` will also be placed here. For instance, there is a ``-e``
that tells ``pip`` to install ARMI itself and defer to ``setup.py`` for a version-agnostic
list of dependencies. We also have multiple requirements files for different needs, like
testing.

Releasing a New Version of ARMI
-------------------------------
TBD

Module-Level Logging
--------------------
In most of the modules in ``armi``, you will see logging using the ``runLog`` module.
This is a custom, global logging object provided by the import:

.. code-block:: python

    from armi import runLog

If you want a logger specific to a single module, say to provide debug logging for only
one module, that functionality is provided by what might look like a bare Python logging
import, but is actually calling the same underlying ``armi`` logging tooling:

.. code-block:: python

    import logging
    runLog = logging.getLogger(__name__)

In either case, you can then log using the same, easy interface:

.. code-block:: python

    runLog.info('information here')
    runLog.error('extra error info here')

Finally, you can change the logging level in either above scenario by doing:

.. code-block:: python

    runLog.setVerbosity(logging.DEBUG)
    # or
    runLog.setVerbosity('debug')

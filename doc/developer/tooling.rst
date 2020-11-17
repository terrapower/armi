Tooling and infrastructure
==========================

Packaging and dependency management
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The process of packaging and Python projects and managing their dependencies is
somewhat challenging, nuanced, and in the opinion of the author, poorly-documented.
We attempt to follow existing conventions, where they exist, and the contents of our
``setup.py`` follow existing conventions as possible. Of particular note is the way that
we express our dependencies. In this, we take inspiration from `this fantastic article
<https://caremad.io/posts/2013/07/setup-vs-requirement/>`_
about dependecy management in Python projects.

The main points here are that the packages listed in the ``install_requires`` argument to
``setup()`` are meant to express, as abstractly as possible, the packages that need to
be installed **somehow** for the package to work. In addition, ``extras_require`` can be
used to specify other packages that are not strictly required, but if installed enable
extra functionality. On the other hand, ``requirements.txt`` exists to describe a
complete environment more specifically, potentially including extra arguments to ``pip``
to control its behavior. Dependencies specified in ``setup.py`` should include version
bounds sparingly, only when needed to ensure compatibility, whereas ``requirements.txt``
may sometimes point to an alternative package index, and include strict version bounds
for all dependencies.

A common source of concern is that the list of dependencies would be duplicated between
``setup.py`` and ``requirements.txt``. In our particular case, ARMI does not benefit
from pointing to special package indices, and most version bounds are semanic. We
therefore follow the recommendation in the above article of including in
``requirements.txt`` a simple ``-e .``. This tells pip to install ``armi`` itself,
deferring to ``setup.py`` for a list of requiremed dependencies. Non-semantic version
bounds, such as those used to avoid bugs in the dependency, should be specified in
``requirements.txt``, rather than ``setup.py``. ARMI itself has several requirements
files, located at the root of the project, which can be used as jumping-off points for
more complex scenarios.

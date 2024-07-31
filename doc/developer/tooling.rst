.. _armi-tooling:

**************************
Tooling and Infrastructure
**************************

Good Commit Messages
====================
The ARMI project follows a few basic rules for "good" commit messages:

* The purpose of the message is to explain to the changes you made to a stranger 5 years from now.
* Keep your writing short and to the point.
* The first line of each commit must be shorter than 50 characters.
* Commit messages should be active voice, present tense.
* Multi-line comments are allowed, but make sure the second line of the commit is blank:

.. code-block::

    Adding this commit for REASONS.

    Here is some super important extra info.
    Oh, there is so much extra info.
    This section
    * is
    * totally
    * optional.

Good Pull Requests
==================
A good commit is like a sentence; it expresses one complete thought. In that context, a good
Pull Request (PR) is like a paragraph; it contains a few sentences that contain one larger
thought. A good PR is *not* a chapter or an entire book! It should not contain multiple
independent ideas.

One Idea = One PR
-----------------
.. important ::
    If you *can* break a PR into smaller PRs, containing unrelated changes, please do.

It is a discourtesy to your reviewers to make them review a PR with multiple, unrelated changes.
It forces them to look at every line of diff in your PR and figure out which change it belongs to.
They are busy people, and it will save them time and effort if your PR only has one main idea.
If your PRs are smaller, you will notice a great increase in the quality of the reviews you get.

Don't open until it is ready
----------------------------

.. important ::
    Wait until your PR is complete to open it.

Your PR isn't complete when the code works, it is complete when the code is polished and all the
tests are written and working. The idea here is: as soon as you open a PR, people will start
spending their time looking at it. And their time is valuable. Even though GitHub allows you to
`open a Draft PR <https://github.blog/2019-02-14-introducing-draft-pull-requests/>`_, this is
not the default option in ARMI. It should not be your workflow to open a Draft PR by default. We
prefer to keep the PR list as short as possible. A good rule of thumb is: don't open a PR until
you think it is ready for final review.

Test It
-------
.. important ::
    If a PR doesn't have any changes to testing, it probably isn't complete.

Unless a PR is just documentation or linting, it almost certainly needs testing to be complete.
For example:

* If a PR adds new code, that code needs new tests to prove it is working.
* If a PR changes existing code, there needs to be test changes to prove the code still works.
* If a PR fixes a bug, there needs to be a test to prove the bug is fixed.

If the changes in the PR are worth the time to make, they are worth the time to test. Help your
reviewer by proving your code works.

Document It
-----------

.. important ::
    If it isn't documented, it doesn't exist.

We auto-document the API, so don't worry about that. But when it comes to documentation, write
it for somebody who is new to the code base 3 years from now, who needs to understand it in
nitty-gritty detail to fix a bug without you. Think about variable names, comments, and docstrings.
Also consider (if you are making a major change) that you might be making something in the docs
out-of-date.

Watch for Requirements
----------------------
When you are touching code in ARMI, watch out for the docstrings in the methods, classes, or
modules you are editing. These docstrings might have bread crumbs that link back to requirements.
Such breadcrumbs will look like:

.. code-block::

    """
    .. test: This is a requirement test breadcrumb.

    .. impl: This is an requirement implementation breadcrumb.

    """

If you touch any code that has such a docstring, even at the top of the file, you are going to be
responsible for not breaking that code/functionality. And you will be required to explicitly
call out that you touch such a code in your PR.

Your PR reviewer will take an extra look at any PR that touches a requirement test or implementation.
And you will need to add a special release note under the "Changes that Affect Requirements" section header.

Add Release Notes
-----------------
For most PRs, you will need to add release notes to the
`Release Notes documentation <https://github.com/terrapower/armi/tree/main/doc/release>`_. The goal
here is to help track all the important changes that happened in ARMI, so ARMI can document what
has changed during the next `release <https://github.com/terrapower/armi/releases>`_. To that end,
minor PRs won't require a release note.

In particular, in the release notes, you will find four sections in the release notes:

1. **New Features** - A new feature (or major addition to a current feature) was added to the code.
2. **API Changes** - ANY breaking change to the public-facing API of ARMI. (A breaking change is
   when you change the existing API, not when you add something new to the API.)
3. **Bug Fixes** - ANY bug fix in the code (not the documentation), no matter how minor.
4. **Changes that Affect Requirements** - If you touch the code (``impl``) or test (``test``) for
   anything that currently has a requirement crumb. (This must be a non-trivial change.)

If your PR fits more than one of these categories, great! Put a description of your change under
all the categories that apply.


Packaging and dependency management
===================================
The process of packaging Python projects and managing their dependencies is somewhat
challenging and nuanced. The contents of our ``pyproject.toml`` follow existing conventions as
much as possible. In particular, we follow `the official Python packaging guidance
<https://packaging.python.org/en/latest/>`_.

pyproject.toml
--------------
As much as possible, the ARMI team will try to centralize our installation and build systems
through the top-level ``pyproject.toml`` file. The only exception will be our documentation,
which has much customization done through the Sphinx ``doc/conf.py`` file.

The packages listed in the ``install_requires`` argument to ``setup()`` are meant to
express, as abstractly as possible, the packages that need to be installed **somehow**
for the package to work. In addition, ``extras_require`` are used to specify other
packages that are not strictly required, but if installed enable extra functionality,
like unit testing or building documentation.

Third-Party Licensing
---------------------
Be careful when including any dependency in ARMI (say in the ``pyproject.toml`` file) not
to include anything with a license that supercedes our Apache license. For instance,
any third-party Python library included in ARMI with a GPL license will make the whole
project fall under the GPL license. But a lot of potential users of ARMI will want to
keep some of their work private, so we can't allow any GPL tools.

For that reason, it is generally considered best-practice in the ARMI ecosystem to
only use third-party Python libraries that have MIT or BSD licenses.

Releasing a New Version of ARMI
===============================
We use the common ``major.minor.bump`` version scheme where a version string
might look like ``0.1.7``, ``1.0.0``, or ``12.3.123``. Each number has a specific meaning:

* ``major`` - Revved for DOE/NRC-sanctioned release or at the end of a long development cycle.
* ``minor`` - Revved when we decide the code or our API has reached a stable point.
* ``bump`` - Revved every time we modify the API, and any other time we want.

**NOTE**: Changes to documentation or testing probably do not deserve a version bump.

**Any change to a major or minor version is considered a release.**

Only a core member of the ARMI team may release a new version, or add a tag of any kind to
the repository. The rule is *the only tags in the ARMI repo are for official versions*. If
you want to release a version of ARMI, you will need admin privileges to multiple TerraPower
repos on GitHub.

Every release should follow this process:

1. Ensure all unit tests pass and the documentation is building correctly.
2. Bump the ``version`` string in ``pyproject.toml``.
3. Add release notes to the documentation:
   `here <https://github.com/terrapower/armi/tree/main/doc/release>`__.
4. Tag the commit after it goes into the repo:

    - From this commit: ``git tag -a 1.0.0 -m "Release v1.0.0"``
    - Or from another commit: ``git tag <commit-hash> 1.0.0 -m "Release v1.0.0"``
    - Pushing to the repo: ``git push origin 1.0.0``
    - **NOTE** - The ONLY tags in the ARMI repo are for official version releases.

5. Also add the release notes on `the GitHub UI <https://github.com/terrapower/armi/releases>`__.
6. Follow the instructions `here <https://github.com/terrapower/terrapower.github.io>`_ to
   archive the new documentation.
7. Tell everyone!

Module-Level Logging
====================
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

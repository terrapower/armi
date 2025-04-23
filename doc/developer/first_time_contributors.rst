*****************************
First Time Contributors Guide
*****************************

The ARMI team strongly encourages developers to contribute to the codebase.

The ARMI framework code is open source, and your contributions will become open source. Although fewer laws apply to open source materials because they are publicly-available, you still must comply with all applicable laws and regulations.

Help Wanted
===========

There are a lot of places you can get started to help the ARMI project and team:

* Better :ref:`armi-docing`
* Better test coverage
* Many more type annotations are desired. Type issues cause lots of bugs.
* Targeted speedups (e.g. informed by a profiler)
* Additional relevance to thermal reactors

Naturally, you can also look at the open `ARMI issues <https://github.com/terrapower/armi/issues>`_ to see what work needs to be done. In particular, check out the `help wanted tickets <https://github.com/terrapower/armi/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22>`_ and `good first issue tickets <https://github.com/terrapower/armi/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22>`_.

Testing
=======

Any contribution must pass all included unit tests. You will frequently have to fix tests your code changes break. And you should definitely add tests to cover anything new your code does.

The ARMI tests are meant to be run using `pytest <https://docs.pytest.org/en/8.0.x/>`_
locally ::

    $ pip install -e .[test]
    $ pytest -n 4 armi

Submitting Changes
==================

To submit a change to ARMI, you will have to open a Pull Request (PR) on GitHub.com.

The process for opening a PR against ARMI goes something like this:

1. `Fork the ARMI repo <https://docs.github.com/en/get-started/quickstart/fork-a-repo>`_
2. `Create a new branch <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository>`_ in your repo
3. Make your code changes to your new branch
4. Submit a Pull Request against `ARMIs main branch <https://github.com/terrapower/armi/pull/new/main>`_
    a. See `GitHubs general guidance on Pull Requests <https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-a-pull-request>`_
    b. See ARMIs specific guidance on what makes a "good" Pull Request: :ref:`armi-tooling`.
5. Actively engage with your PR reviewer's questions and comments.

> Note that a bot will require that you sign our `Contributor License Agreement <https://github.com/terrapower/armi/blob/main/CONTRIBUTING.md>`_ before we can accept a pull request from you.

See our published documentation for a complete guide to our coding standards and practices: :ref:`armi-stds`.

Also, please check out our (quick) synopsis on good commit messages: :ref:`armi-tooling`.

Licensing of Tools
==================

Be careful when including any dependency in ARMI (say in the ``pyproject.toml`` file) not to include anything with a license that supersedes our Apache license. For instance, any third-party Python library included in ARMI with a GPL license will make the whole project fall under the GPL license. But a lot of potential users of ARMI will want to keep some of their work private, so we can't allow any GPL tools.

For that reason, it is generally considered best-practice in the ARMI ecosystem to only use third-party Python libraries that have MIT or BSD licenses.

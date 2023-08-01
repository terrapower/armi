# How to Contribute

The ARMI team strongly encourages developers to contribute to the codebase.

The ARMI framework code is open source, and your contributions will become open source.
Although fewer laws apply to open source materials because they are publicly-available, you still
must comply with all applicable laws and regulations.

## Help Wanted

There are a lot of places you can get started to help the ARMI project and team:

* Better [documentation](https://terrapower.github.io/armi/developer/documenting.html)
* Better test coverage
* Many more type annotations are desired. Type issues cause lots of bugs.
* Targeted speedups (e.g. informed by a profiler)
* Additional relevance to thermal reactors

Naturally, you can also look at the open [ARMI issues](https://github.com/terrapower/armi/issues) to see what work needs to be done. In particular, check out the ["help wanted" tickets](https://github.com/terrapower/armi/issues?q=is%3Aopen+is%3Aissue+label%3A%22help+wanted%22) and ["good first issue" tickets](https://github.com/terrapower/armi/issues?q=is%3Aopen+is%3Aissue+label%3A%22good+first+issue%22).

## Testing

Any contribution must pass all included unit tests. The tests are built and run with the
`pytest` system. Please add new tests if you add new functionality. You can generally just run
`tox` to build the testing environment and execute all the tests and ruff checks.

## Submitting Changes

To submit a change to ARMI, you will have to open a Pull Request (PR) on GitHub.com.

The process for opening a PR against ARMI goes something like this:

1. [Fork the ARMI repo](https://docs.github.com/en/get-started/quickstart/fork-a-repo)
2. [Create a new branch](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/creating-and-deleting-branches-within-your-repository) in your repo
3. Make your code changes to your new branch
4. Submit a Pull Request against [ARMI's main branch](https://github.com/terrapower/armi/pull/new/main)
    a. See [GitHub's general guidance on Pull Requests](http://help.github.com/pull-requests/)
    b. See [ARMI's specific guidance](https://terrapower.github.io/armi/developer/tooling.html#good-pull-requests) on what makes a "good" Pull Request.
5. Actively engage with your PR reviewer's questions and comments.

> Note that a bot will require that you sign [our Contributor License Agreement](https://gist.github.com/youngmit/8654abcf93f309771ae9296abebe9d4a)
before we can accept a pull request from you.

See our published documentation for a complete guide to our [coding standards and practices](https://terrapower.github.io/armi/developer/standards_and_practices.html).

Also, please check out our (quick) synopsis on [good commit messages](https://terrapower.github.io/armi/developer/tooling.html#good-commit-messages).

## Licensing of Tools

Be careful when including any dependency in ARMI (say in a `requirements.txt` file) not
to include anything with a license that superceeds our Apache license. For instance,
any third-party Python library included in ARMI with a GPL license will make the whole
project fall under the GPL license. But a lot of potential users of ARMI will want to
keep some of their work private, so we can't allow any GPL tools.

For that reason, it is generally considered best-practice in the ARMI ecosystem to
only use third-party Python libraries that have MIT or BSD licenses.

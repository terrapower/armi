# How to contribute

The ARMI framework project strongly encourages developers to help contribute to and build the code. 

The ARMI framework code is open source, and your contributions will become open source.
Although fewer laws apply to open source materials because they are publicly-available, you still
must comply with all applicable laws and regulations.

## Help Wanted

There are a lot of things we need help with right off the bat, to get your feet wet:

* Many more type annotations are desired. Type issues cause lots of bugs.
* Fewer Pylint warnings
* Better documentation
* Additional relevance to thermal reactors
* Better test coverage
* Targeted speedups (e.g. informed by a profiler)

Naturally, we encourage other kinds of contributions as well.

## Testing

Any contribution must pass all included unit tests. The tests are built and run with the 
pytest system. Please add new tests if you add new functionality. You can generally just run
`tox` to build the testing environment and execute all the tests and pylint checks. 

## Submitting changes

Please send a [GitHub Pull Request to the ARMI master branch](https://github.com/terrapower/armi/pull/new/master) with a clear 
list of what you've done (read more about [pull requests](http://help.github.com/pull-requests/)).  Please follow our 
coding conventions (below) and make sure all of your commits are atomic (one feature per commit).

Please write a clear log messages for your commits. One-liners are OK for small changes, but bigger changes should include more:

    $ git commit -m "A brief summary of the commit
    > 
    > A paragraph describing what changed and its impact."
    
Note that a bot will require that you sign [our Contributor License
Agreement](https://gist.github.com/youngmit/8654abcf93f309771ae9296abebe9d4a)
before we can accept a pull request from you.

## Coding conventions

We use the [Black](https://black.readthedocs.io/en/stable/) code formatter so we don't have to argue or worry about trivial
whitespacing conventions during code review. You should always run `black` before submitting a pull request.  

We really like Robert C Martin's [Clean Code](https://www.amazon.com/Clean-Code-Handbook-Software-Craftsmanship/dp/0132350882) book
and at least nominally try to follow some of the advice in there.

  * Consider contacting some ARMI developers before embarking on a major new feature or development on the framework. 
    We may prefer to keep various physics or design-specific developments in modular plugins (which can also be
    open source, of course!). The framework should be focused on frameworky stuff (broad, sharable stuff).
    As the Framework matures, we hope it will stabilize, though we recognize we need work before then.
  * We believe that comments can increase maintenance burdens and should only be used when one fails to explain 
    the entire situation with the code itself. In practice, we fail to do this all the time, and need comments
    to help guide future readers of the code. 
  * Names //really// matter.
  * Your PR will be reviewed and probably need some iteration. We aren't trying to be a pain or discourage you,
    we just want to make sure the code is optimal. 
  
## Documentation
We use Sphinx for our documentation, and numpydoc to parse docstrings into the API docs section of our documentation.
Thus, all docstrings are officially part of the technical documentation and should be written as such.

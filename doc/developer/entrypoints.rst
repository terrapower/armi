Entry Points
============

**Entry Points** are like the verbs that your App can *do*. 
The :py:mod:`built-in entry points <armi.cli>` 
offer basic functionality, like :py:class:`running a case <armi.cli.run.RunEntryPoint>`
or :py:class:`opening up the GUI <armi.cli.gridGui.GridGuiEntryPoint>`, but
the real joy of an application comes when you add your own project-specific 
entry points that do the actions that you commonly need done.

To make a new EntryPoint, first make a new module and subclass 
:py:class:`~armi.cli.entryPoint.EntryPoint`. Set the 
class attributes as follows:

``name``
    What the user types on the CLI to invoke this entry point. 

``settingsArgument``

    * ``"required"`` if a settings input file must be provided,
    * ``"optional"`` if it may be provided but not required, 
    * ``None`` if no settings input is allowed


.. tip:: ARMI apps often collect EntryPoints in a ``cli/`` directory (Command Line Interface)

Next, implement the :py:meth:`~armi.cli.entryPoint.EntryPoint.addOptions` method. Here you can both:

* turn various Settings into command-line arguments with :py:meth:`~armi.cli.entryPoint.EntryPoint.createOptionFromSetting`
* add arbitrary command-line arguments using the standard :py:mod:`python:argparse` library.

The values of the non-setting arguments will become attributes in ``self.args`` for later use.

Finally, implement the :py:meth:`~armi.cli.entryPoint.EntryPoint.invoke` method
with the code you'd like to run upon invocation of this entry point.


.. code-block:: python
    :caption: Example entry point

    from armi.cli import entryPoint

    class SampleEntryPoint(entryPoint.EntryPoint):
        """
        Entry point title here

        Long description of entry point here. This will actually get picked up and used
        as the help text on the command line itself!
        """

        name = "do-my-thing"
        settingsArgument = "required"

        def addOptions(self):
            self.createOptionFromSetting(CONF_CYCLE_LENGTH)
            self.createOptionFromSetting(CONF_BURN_STEPS)
            self.parser.add_argument(
                "--post-process",
                "-p",
                action="store_true",
                default=False,
                help="Just post-process an existing suite; don't run",
            )

        def invoke(self):
            from armi import cases

            inputCase = cases.Case(cs=self.cs)
            print(f"The case is {inputCase}")

            if self.args.post_process:
                print("Post processing...")


When you run your app, you will have this as an option, and you can invoke it with::

    python -m myapp do-my-thing --post-process settingsFile.yaml

or (if ``myapp`` is not in your ``PYTHONPATH``)::

    python path/to/myapp do-my-thing --post-process settingsFile.yaml


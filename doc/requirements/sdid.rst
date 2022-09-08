**************************************************
Software Design and Implementation Document (SDID)
**************************************************


--------
Overview
--------

..
   TODO

Settings Overview
-----------------

The settings package is a long-time feature of ARMI. It was made to fill the niche of gathering
user input on how the user wanted a case to proceed and what results the user is hoping to produce.

A good roadmap to understanding the settings system would be to look at the following principle
design considerations, going into each one in detail.

* Keep the user's experience with settings as simple as possible.
* Remove setting definitions from code, centralize them, and facilitate definition change
* Don't break backwards compatibility
* Improve safety around possible misuses and accidents of the settings
* Facilitate interactions with the GUI

Outside of these points the system should exist in a form trimmed of any superfluous functionality
to keep it clean and unobtrusive.

Keep the user's experience with settings as simple as possible
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
This is the principle design restraint for the settings package. In addition to raw implementation
complexity, asking developers and users to relearn any alterations to the existing system
counts towards total complexity; deeming migration to an equally complex system not worth the effort
without stronger incentives.

Historically developers are used to looking up the name of their setting by using a string fed
into a collection object and having the value associated with the name returned back.
The same behavior was used to assign a new value to the given name in the shared object. This
constitutes the vast majority of external interactions with the settings system.

------
Design
------

TODO

#. The ``blueprints`` package makes extensive use of the ``yamlize`` library, which provides a mechanism for serializing and deserializing blueprints to and from YAML files.

Settings Design
---------------

Dictionary-like behavior
^^^^^^^^^^^^^^^^^^^^^^^^
The settings system functions much like a Python dictionary for most of its interactions.

The two objects to note in this interplay are the ``Settings`` object which is what the vast majority
of interactions are directed at. Then there's the more hidden ``Setting`` object which corresponds to
a single defined entity in the settings system, housed under a ``Settings.settings`` dictionary.

When users perform lookups and value assignments to a key on the settings object, it hides a bit of
the work behind the scenes of applying setting rules.

The lookup fashioned as::

	>>>Settings['mySettingName']
	1

will only return the current value of the setting stored under ``mySettingName``, whereas::

	>>>Settings.settings['mySettingName']
	<IntSetting mySettingName value:1 default:1>

returns the setting object itself. Only more complex relationships with coupled code tools will be concerned with
how the object itself behaves. A prime example of this is the GUI.

Improve safety around possible misuses and accidents of the settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
While simplicity remains a principle concern, some allotment for error prevention has to be allowed. A basic system that can be misused wildly is inherently more complex than one with a little overhead that works to keep nasty surprises as bay.

The settings system is written in a defensive fashion, as it's the most frequent location for possible
developer and user misuse. Given this, any method from accessing non-existent settings to trying to
supply duplicate settings has been written with fail-fast behavior.

In some cases there may be an automated solution to a possible misuse. In general there's nothing overtly wrong
with the litany of checks for safety but it does make the system appear more convoluted to newcomers. Of course,
This small cost is outweighed by the time saved from working through the same resolvable problem in use many times.

There will always be a need for knowledgable users to communicate with however, as it is unreasonable to attempt to
program in a fool-proof understanding of the physics coded for in the settings system. Such an endeavor would
come with great developmental and maintenance costs.

Most problems these days arise when users make typos or simple editing mistakes when
manually adjusting some values in the case settings input files.

Non-dynamic data typing
^^^^^^^^^^^^^^^^^^^^^^^
One specific category of safety in the settings system stems from the nature of data variables in Python.

Because ARMI is written in Python, there's a large issue of dynamic typing polluting setting values.
There can easily be aberrant behavior introduced by a new kind of data being input to a value.

For example it's not uncommon to have code flow based off setting values such as zero.
If some developer makes a mistake and changes the datatype of a value zero from an integer to a
string, it will break the utility of the code flow evaluation without alerting anyone to the change
in behavior.::

	def myFunction(var):
		if var == 0:
	 	   doSomething()
		else:
		    doSomethingSubtlyDifferent()

	myVar = 0
	myFunction(myVar) # doSomething()

	# oops! clumsy str() method used somewhere
	myVar = "0"
	myFunction(myVar) # doSomethingSubtlyDifferent()

These kinds of hard to track mistakes were resolved by creating a more object oriented
division of settings with type protection surrounding the setting's values, so it wouldn't
be possible to set the example variable to a string.

Now there are a finite set of allowable setting types which loosely mirror the
Python primitive data types, namely: ``list``, ``float``, ``int``, ``str``, and ``bool``.

As mutable objects are encompassed in the list of supported data types,
it became important to prevent the perversion of their contained values with alterations
that would bypass the protective methods on setting objects entirely.
Such an example would be when a list is returned from the appropriate list setting object,
and something is appended to it. This would bypass all error prevention methodology in place.
The easiest fix for this was to return a deep copy of the contained value, and only reassign the
contained value on an explicit value assignment statement::

	# note 'cs' is the common term for 'case settings'
	# referring to the settings system main shared object 'Settings'.
	myList = cs['myListSetting']

	myList.append('Some value not allowed by myListSetting!') # bad!
	# if we stop the code here, the value in cs['myListSetting'] will not contain
	# the bad value appended thanks to myList being a deep-copied value

	# the following will run 'myList' against any error checking in the system
	# either crashing the run or accepting the new value for later use.
	cs['myListSetting'] = myList # good!

The customizability of settings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Yet another error prevention tool is the customizability of individual settings. As mentioned previously
a complete understanding of the complex meaning involved in setting values can't be programmed. However by
giving each setting more character in the system to stand up on its own against mistakes (e.g. a temperature below
absolute zero) can chip away at the burden of the user to need to understand the entirety.

Each setting is intended to present a way of answering a question to the user from the system.
For example many settings ask questions like what external code engine to utilize for advanced
calculations, or what temperature to apply to a particular component. These questions are not open ended
and as such usually have a set of rules surrounding their use like no temperatures below absolute zero, or
only code engines specified by the following three strings are valid.

The provided rules for how a setting behaves varies by subtype (i.e. Numeric settings possess
valid maximums and minimums, whereas strings can be matched against a set of acceptable values).
Given the extensibility of the setting system there is no limitation currently imposed by the system on
what rules may apply. Only a basic set of rules currently exists but that has been found to be more
than sufficient in modeling developer specifications for settings thus far.

Most of these customized behaviors are directly linked with how the GUI representation of the settings
restrict interactions with the user. For instance values outside of the allowable range for numeric
settings will reject the change with an immediate reversion to the previously accepted value,
or string settings with a restricted set of acceptable values will only
display those in a drop down menu.

-------------------
Requirements Review
-------------------

..
   TODO

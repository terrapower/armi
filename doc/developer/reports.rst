***************
Reports in ARMI
***************

.. note::  The resulting report itself is an HTML page with table of contents on the left.

ARMI provides the ability to make a variety of plots and tables describing the state of the reactor.
Also, with ARMI's variety of plugins, some plots/analysis could be plugin dependent. If you have certain plugins installed, some new 
different plots may be available or more pertinent to the report.

From this understanding, a plugin hook is created called getReportContents(), which allows for this ability to get special contents
from a specific plugin.

Currently it is implemented in the bookkeeping and neutronics plugin.


The Hook: getReportContents()
=============================
getReportContents takes in 5 arguments (r, cs, report, stage, blueprint)

+---------------+--------------------------------------------------------------------------------------------------------------------------+
| ``r``         | a Reactor                                                                                                                |
+---------------+--------------------------------------------------------------------------------------------------------------------------+
| ``cs``        | Case Settings                                                                                                            |
+---------------+--------------------------------------------------------------------------------------------------------------------------+
| ``stage``     | the stage of the report you are collecting for Begin/BOL, Standard, End/EOL                                              |
+---------------+--------------------------------------------------------------------------------------------------------------------------+
| ``blueprint`` | a blueprint for a reactor, and since not always provided, content is dependent on whether it has the value of None       |
+---------------+--------------------------------------------------------------------------------------------------------------------------+
| ``report``    | a ReportContent object. This is really where all report content is stored and the cornerstone of the workings of reports |
+---------------+--------------------------------------------------------------------------------------------------------------------------+


ReportContent, at its core, is a transient represention of the report itself (until it is fully collected and converted to an html page), so in the call to getReportContents() additions are made to this object. 
Generally, you would want to break up the added contents into stages within the function getReportContents() as so::

        >>> if stage == ReportStage.Begin:
        >>>     newReportUtils.createGeneralReportContent(cs, r, report, blueprint, stage)
        >>>     if blueprint is not None:
        >>>         newReportUtils.blueprintContent(r, cs, report, blueprint)
        >>> elif stage == ReportStage.End:
        >>>     newReportUtils.getEndOfLifeContent(r, report)
        >>> return

In this way, Begin things are general and not time dependent and if ``blueprint`` is available additional contents are made. 
Things like ``TimeSeries`` (Graphs) would want to be accessed at every stage that getReportContents() is called (so they can add a point for every time),
so one can imagine the functionality of the below to allow for ``Standard`` additions.::

    >>> if stage == ReportStage.Standard:
    >>>     neutronicsPlotting(reports, etc, ...)


ReportContent acts as a dicionary of ``Section``'s behind the scenes and the further description of these objects will be found in the following topics. 


What is ReportContent?
======================
At the start of any report creation, creation of the ReportContent object is key.
ReportContent when created, needs the name of the reactor for the title of the report.

To do so, one could do the following::

    >>> report = ReportContent(r.name)


The resulting use of this content to generate the title on the html page:

.. figure:: /.static/titleReportContent.png
    :align: center


``ReportContent`` itself has a dicionary (``.sections``), and so functionality inherent to dictionaries also exists for ``ReportContent``.

Instead of having to directly access the dictionary working behind the scenes through ``report.sections["Design"]``, one can instead just
directly call ``report["Design"]``, since ``__get__()`` has been implemented.


A major component of the ReportContent class is the function to ``writeReports()``. This converts our dictionary/Section/Table/TimeSeries content into an html page for viewing.


Overall, the important functionality examples for ``ReportContent`` additions are summarized below.

Sections
========
The first level of ``ReportContent``'s is made up of ``Section``'s. ``Section``'s have a ``title``, and themselves a dictionary of contents (``.childContents``),
but again the ability to just directly access a sections children like ``report[Comprehensive][Setting]`` exists, as long as the section already exists,
(if not, a key error persists, and so it is safer to do ``report[Comprehensive].get(Setting, Table(...)))``, where ``Table`` would be the default.


Sections can be made of other Sections, Tables, Images, TimeSeries, or Htmltree Elements (for the purpose of directly writing prose).

Each time a Section is written, it's title will be a heading above the enclosed content and it will have a reference in the html page tied to this heading.

Again, the ability to add different plugins content to the same section exists.

The following demonstrates how to add elements to the same Section through a call to ``addChildElement(item, heading)`` ::

    report["Design"]["Block Diagrams"].addChildElement(Image("Diagram of {} Block at Cold Temperature".format(
                            bDesign.name.capitalize()
                        ),
                        fileName,
                        "{}".format(bDesign.name.capitalize()),
                    ),
                    bDesign.name.capitalize(),
                )

It is also possible to do the following through dictionary access for the same result ::

        report["Design"]["Block Diagrams"][bDesign.name.capitalize()](Image("Diagram of {} Block at Cold Temperature".format(
                            bDesign.name.capitalize()
                        ),
                        fileName,
                        "{}".format(bDesign.name.capitalize()),
                    ))


Images
======
Images may generally be things to add at stage = Beg, or stage = End. (For example, a core map at BOL would be inserted at stage = Beg) Images require a ``caption`` and a ``filename`` and have an optional ``title`` argument. (They would also have a call to another function before hand to create the image file (for example))


The ``title`` on an ``Image`` is defaulted to None. This is a decision to deal with some images where maybe it is best to group them together, but overdoing it if each were to be given a title. Title in general has the sole purpose of giving this image a position within the table of contents one the left of the html page. Without ``title``, it will not have a +/- sign for additional drop down reference. If you want to specify an image, give it a caption and mention its name.

There are two examples of additions of images within sections worth mentioning.

Here is an example for adding Assembly Designs Images (where images are grouped but don't have distinct titles, and no direct access, Title is defaulted to None)

.. figure:: /.static/AssemblySectionExample.png
    :align: center


Here is an example for Block Images (in which table of content access was wanted, so ``title`` was given)

.. figure:: /.static/blockDiagramExample.png
    :align: center

In this case, Block Diagrams is the Section Title, and it is expandable, for easy viewing of distinct blocks.


Summary
=======

``ReportContent`` is made up of many different types of elements (``Sections``, ``Tables``, ``Images``, ``HtmlElements``, ``TimeSeries``), that when
``writeReports()`` is called on the ``ReportContent`` object, have the ability to be rendered through their ``render()`` method in order to be translated
to html for the resulting document. This document is saved in a new folder titled reportsOutputFiles.

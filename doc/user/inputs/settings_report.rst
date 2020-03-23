Settings Report
===============
This document lists all the :doc:`settings </user/inputs/settings>` in ARMI.  

They are all accessible to developers
through the :py:class:`armi.settings.caseSettings.Settings` object, which is typically stored in a variable named
``cs``. Interfaces have access to a simulation's settings through ``self.cs``.


.. exec::
    from armi import settings
    import textwrap

    subclassTables = {}
    cs = settings.Settings()
    # User textwrap to split up long words that mess up the table.
    wrapper = textwrap.TextWrapper(width=25, subsequent_indent='')
    content = '\n.. list-table:: ARMI Settings\n   :header-rows: 1\n   :widths: 30 40 30\n    \n'
    content += '   * - Name\n     - Description\n     - Default\n'

    for setting in sorted(cs.settings.values(), key=lambda s: s.name):
        content += '   * - {}\n'.format(' '.join(wrapper.wrap(setting.name)))
        content += '     - {}\n'.format(' '.join(wrapper.wrap(setting.description or '')))
        content += '     - {}\n'.format(' '.join(['``{}``'.format(wrapped) for wrapped in wrapper.wrap(str(getattr(setting,'default','') or ''))]))

    content += '\n'

    return content

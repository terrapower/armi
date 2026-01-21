.. _settings-report:

===============
Settings Report
===============

.. exec::
    from armi import settings
    cs = settings.Settings()
    numSettings = len(cs.values())

    return f"This document lists all {numSettings} `settings <#the-settings-input-file>`_ in ARMI.\n"

They are all accessible to developers through the :py:class:`armi.settings.caseSettings.Settings` object, which is typically stored in a variable named ``cs``. Interfaces have access to a simulation's settings through ``self.cs``.


.. exec::
    import textwrap
    from dochelpers import escapeSpecialCharacters
    from armi import settings

    def looks_like_path(s):
        """Super quick, not robust, check if a string looks like a file path."""
        if s.startswith("\\\\") or s.startswith("//") or s[1:].startswith(":\\"):
            return True
        return False

    subclassTables = {}
    cs = settings.Settings()

    # User textwrap to split up long words that mess up the table.
    ws = "    "
    ws2 = ws + "    "
    ws3 = ws2 + "  "
    wrapper = textwrap.TextWrapper(width=25, subsequent_indent='')
    wrapper2 = textwrap.TextWrapper(width=10, subsequent_indent='')
    content = '\n.. container:: break_before ssp-landscape\n\n'
    content += ws + '.. list-table:: ARMI Settings\n'
    content += ws2 + ':widths: 30 40 15 15\n'
    content += ws2 + ':class: ssp-tiny\n'
    content += ws2 + ':header-rows: 1\n\n'
    content += ws2 + '* - Name\n' + ws3 + '- Description\n' + ws3 + '- Default\n' + ws3 + '- Options\n'

    for setting in sorted(cs.values(), key=lambda s: s.name):
        content += ws2 + '* - {}\n'.format(' '.join(wrapper.wrap(setting.name)))
        description = escapeSpecialCharacters(str(setting.description) or "")
        content += ws3 + "- {}\n".format(" ".join(wrapper.wrap(description)))
        default = str(getattr(setting, 'default', None)).split("/")[-1]
        options = str(getattr(setting,'options','') or '')
        if looks_like_path(default):
            # We don't want to display default file paths in this table.
            default = ""
            options = ""
        content += ws3 + '- {}\n'.format(' '.join(['``{}``'.format(wrapped) for wrapped in wrapper2.wrap(default)]))
        content += ws3 + '- {}\n'.format(' '.join(['``{}``'.format(wrapped) for wrapped in wrapper2.wrap(options)]))

    content += '\n'

    return content
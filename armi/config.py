# Copyright 2019 TerraPower, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Handle the loading and application of configuration values"""
import os
import configparser

import armi
from armi import runLog


TEMPLATE_DATA = os.path.join(armi.RES, "config")


class ConfigHandler(object):  # pylint: disable=missing-docstring
    def __init__(self):  # pass in RES to avoid circular import
        """
        Exposes the contents of the config files in the TEMPLATE_DATA location to pythonic access

        The config files are split logically into "user"/"u" files and "template"/"t"
        files.  Template files define what configuration values ARMI expects to exist, and
        will be duplicated locally for the user, where thereafter they exist as user
        files. User files contain the customizations of the user. Values that don't exist
        in the user file will be defaulted by the template files.

        Configs are not loaded on construction, but rather on first access. This prevents
        potential race conditions when multiple processes are running (MPI, xdist testing,
        etc.)
        """
        self._configs = None
        self.submitter = None

    @property
    def configs(self):
        # Load config upon first access and then return it thereafter.
        # It's undefined whether ``configs`` or some other attribute get accessed first
        # so we trigger loads off of either.
        if self._configs is None:
            self._configs = {}
            self._load_config()
        return self._configs

    def __getattribute__(self, key):
        """
        Get attribute from this object.

        Notes
        -----
        This loads config upon first access and then returns it thereafter.
        The ``__getattribute__`` method is used (vs. ``__getattr__``) because
        many of the attributes of this object are created from config file names
        at runtime and are not known in advance. We need this because we want to intercept
        both the explicitly-managed attributes (``_configs``, ``submitter``) and the
        implicitly-managed ones whose names are discovered at runtime. The strange-looking
        ``object``-based calls are required to avoid infinite recursion.
        """
        if object.__getattribute__(self, "_configs") is None:
            object.__setattr__(self, "_configs", {})
            object.__getattribute__(self, "_load_config")()
        return object.__getattribute__(self, key)

    def _load_config(self):
        if armi.MPI_SIZE > 1:
            # prevent race conditions in parallel cases. Can happen in MPI or other parallel runs (e.g. unit tests)
            runLog.warning(
                "Skipping loading configuration while MPI_SIZE = {}, it should not need a config".format(
                    armi.MPI_SIZE
                )
            )
            return
        t_parsers = self.find_cfg_files(TEMPLATE_DATA)
        try:
            if not os.path.exists(armi.APP_DATA):
                os.makedirs(armi.APP_DATA)
            u_parsers = self.find_cfg_files(armi.APP_DATA)

            self._configs = self.align_user_cfgs(t_parsers, u_parsers)
            self.save()

        except OSError:  # permission denied
            runLog.warning(
                "No accessible appdata resources found nor is creation possible"
            )
            self._configs = (
                t_parsers  # can't do anything besides use the template config values
            )

        for filename, cfg in self._configs.items():
            self._expose_file(filename, cfg)

    def find_cfg_files(self, loc):  # pylint: disable=no-self-use
        """Find config files."""
        parsers = {}
        for dirname, _dirnames, filenames in os.walk(loc):
            for filename in filenames:
                if filename.lower().endswith(".cfg"):
                    cfg_parser = configparser.ConfigParser(
                        allow_no_value=True, interpolation=None
                    )
                    cfgPath = os.path.join(dirname, filename)
                    cfg_parser.read(cfgPath)
                    parsers[filename] = cfg_parser
        return parsers

    def align_user_cfgs(self, templates, users):  # pylint: disable=no-self-use
        """Ensure the user supplied configurations have all the template data, and ignore non-template data."""
        aligned_cfgs = {}

        for (
            filename,
            t_parser,
        ) in templates.items():  # pylint: disable=too-many-nested-blocks

            # file comparisons
            if filename in users:
                u_parser = users[filename]

                # section comparisons
                u_sections = u_parser.sections()
                for t_section in t_parser.sections():
                    if t_section in u_sections:

                        # option comparisons
                        u_options = u_parser.options(t_section)
                        for t_option in t_parser.options(t_section):
                            if t_option in u_options:
                                pass  # all good

                            # no option in user supplied config
                            # use the template values
                            else:
                                u_parser.set(
                                    t_section,
                                    t_option,
                                    t_parser.get(t_section, t_option),
                                )

                    # no template parser section entry in user parser
                    # fill out the user parser's section with template values
                    else:
                        u_parser.add_section(t_section)
                        for t_option in t_parser.options(t_section):
                            u_parser.set(
                                t_section, t_option, t_parser.get(t_section, t_option)
                            )

                # all alterations made, add in complete user parser
                aligned_cfgs[filename] = u_parser

            # no matching user config file to a template file
            # use template values for the missing file
            else:
                aligned_cfgs[filename] = t_parser

        return aligned_cfgs

    def save(self):
        try:
            for filename, cfg in self._configs.items():
                with open(os.path.join(armi.APP_DATA, filename), "w") as configfile:
                    cfg.write(configfile)
        except IOError:  # permissions probably
            runLog.warning(
                "Cannot save user configuration data! Check permissions in APP_DATA location."
            )

    def _expose_file(self, filename, cfg):
        cleaned_filename = os.path.splitext(filename)[0]
        setattr(self, cleaned_filename, _ExposedFile(filename, cleaned_filename, cfg))


class _ExposedFile(object):  # pylint: disable=too-few-public-methods
    def __init__(self, fname, name, cfg):
        self.fname = fname
        self.name = name
        self.cfg = cfg

        getter = lambda option, obj: obj._cfg.get(
            obj._section, option
        )  # pylint: disable=protected-access
        setter = lambda option, obj, value: obj._cfg.set(
            obj._section, option, str(value)
        )  # pylint: disable=protected-access

        def doc(name, section):
            return (
                "Application configuration value access.\n"
                "Encapsulating File: {}\n"
                "Section: {}".format(name, section)
            )

        for section in cfg.sections():

            attrs = {"_cfg": cfg, "_section": section}
            for option in cfg.options(section):
                if option in attrs:
                    raise RuntimeError(
                        "Cannot assign option '{}' to "
                        "exposed config file as it is already claimed!".format(option)
                    )

                opt_getter = lambda obj, opt=option: getter(opt, obj)
                opt_setter = lambda obj, value, opt=option: setter(opt, obj, value)

                attrs[option] = property(opt_getter, opt_setter, doc=doc(name, section))

            access_section = type(str(section), (object,), attrs)
            setattr(self, section, access_section())

    def save(self):
        with open(os.path.join(armi.APP_DATA, self.fname), "w") as configfile:
            self.cfg.write(configfile)

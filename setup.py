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

"""Setup.py script for the Advanced Reactor Modeling Interface (ARMI)"""
from setuptools import setup, find_packages
import os
import pathlib
import re

# grab __version__ from meta.py, without calling __init__.py
this_file = pathlib.Path(__file__).parent.absolute()
exec(open(os.path.join(this_file, "armi", "meta.py"), "r").read())

with open("README.rst") as f:
    README = f.read()


def collectExtraFiles():
    extraFiles = []
    with open("MANIFEST.in", "r") as f:
        # include everything from the MANIFEST.in. MANIFEST.in is somewhat unreliable,
        # in that it only shuffles files around when making an `sdist`; it doesn't
        # install files. `package_data` does though, which we want.
        for l in f:
            extraFiles.append(re.sub(r"^include\s+armi/", "", l).strip())

    return extraFiles


EXTRA_FILES = collectExtraFiles()


setup(
    name="armi",
    version=__version__,
    description="The Advanced Reactor Modeling Interface",
    author="TerraPower, LLC",
    author_email="armi-devs@terrapower.com",
    url="https://github.com/terrapower/armi/",
    license="Apache 2.0",
    long_description=README,
    python_requires=">=3.7",
    packages=find_packages(),
    package_data={"armi": ["resources/*", "resources/**/*"] + EXTRA_FILES},
    entry_points={"console_scripts": ["armi = armi.__main__:main"]},
    install_requires=[
        "configparser",
        "coverage",
        "future",
        "h5py>=3.0",
        "matplotlib",
        "numpy",
        "ordered-set",
        "pillow",
        "pluggy",
        "pyevtk",
        "pympler",
        "scipy",
        "tabulate",
        "voluptuous",
        "xlrd",
        "yamlize",
        "htmltree",
        "pyDOE",
    ],
    extras_require={
        "mpi": ["mpi4py"],
        "grids": ["wxpython"],
        "memprof": ["psutil"],
        "dev": [
            "mako",
            "pytest",
            "pytest-xdist",
            "pytest-cov",
            "pytest-html",
            "pylint",
            "docutils",
            "sphinx",
            "sphinx-rtd-theme",
            "click==8.0.1",  # fixing click problem in black
            "black==20.8b1",
            # for running jupyter dynamically in docs
            "sphinxcontrib-apidoc",
            "jupyter_client",
            "jupyter-contrib-nbextensions",
            "ipykernel",
            "nbsphinx",
            "nbsphinx-link",
            "sphinxext-opengraph",
            "sphinx-gallery",
        ],
    },
    tests_require=["nbconvert", "jupyter_client", "ipykernel"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "License :: OSI Approved :: Apache Software License",
    ],
)

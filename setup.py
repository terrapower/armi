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
import re
from setuptools import setup, find_packages


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
    # duplicating with meta.py for now. See comments there for rationale.
    version="0.1.6",
    description="The Advanced Reactor Modeling Interface",
    author="TerraPower, LLC",
    author_email="armi-devs@terrapower.com",
    url="https://github.com/terrapower/armi/",
    license="Apache 2.0",
    long_description=README,
    python_requres=">=3.6",
    packages=find_packages(),
    package_data={"armi": ["resources/*", "resources/**/*"] + EXTRA_FILES},
    entry_points={"console_scripts": ["armi = armi.__main__:main"]},
    # note that these are duplicated in requirements.txt
    install_requires=[
        "configparser",
        "coverage",
        "future",
        # This is a semantic version bound, because newer h5py versions handle strings
        # differently, and we would need to do some work to support it
        "h5py<3.0",
        "matplotlib",
        "numpy",
        "ordered-set",
        "pillow",
        "pluggy",
        "pyevtk",
        "pympler",
        "pyyaml>=5.1",
        "scipy",
        "tabulate",
        "voluptuous",
        "xlrd",
        "yamlize",
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
            "sphinx>=2.2",
            "sphinx-rtd-theme",
            "black",
            # for running jupyter dynamically in docs
            "sphinxcontrib-apidoc",
            "jupyter_client",
            "jupyter-contrib-nbextensions",
            "ipykernel",
            "nbsphinx",
            "nbsphinx-link",
            "pandoc",
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

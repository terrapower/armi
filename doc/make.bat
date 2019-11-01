@ECHO OFF

pushd %~dp0

REM Command file for Sphinx documentation for ARMI
REM This can be run locally with make html
REM or remotely on a HPC cluster.

if "%PYTHON%" == "" (
	set PYTHON=python
)
set SOURCEDIR=.
if "%BUILDDIR%" == "" (
	set BUILDDIR=_build
)
if "%PYTHONPATH%" == "" (
	set PYTHONPATH=..
)
REM Graphviz and Pandoc binaries are required for
REM auto-generating figures and running notebooks during doc building
if NOT "%GRAPHVIZ%" == "" (
	set PATH="%PATH%";%GRAPHVIZ%
)
if NOT "%PANDOC%" == "" (
	set PATH="%PATH%";%PANDOC%
)

if "%1" == "" goto help

%PYTHON% -m sphinx >NUL 2>NUL
if errorlevel 9009 (
	echo.
	echo.The 'sphinx' package was not found. Make sure you have Sphinx
	echo.installed, then set the SPHINXBUILD environment variable to point
	echo.to the full path of the 'sphinx-build' executable. Alternatively you
	echo.may add the Sphinx directory to PATH.
	echo.
	echo.If you don't have Sphinx installed, grab it from
	echo.http://sphinx-doc.org/
	exit /b 1
)
@ECHO ON
%PYTHON% -m sphinx -b %1 %SOURCEDIR% %BUILDDIR%\%1 %SPHINXOPTS%
@ECHO OFF
goto end

:help
%PYTHON% -m sphinx -h

:end
popd

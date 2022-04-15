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

"""
HTML-formatted reports
"""
import base64
import datetime
import html
import os

from armi import context
from armi import settings


class HTMLFile:
    def __init__(self, *args, **kwds):
        self.args = args
        self.kwds = kwds
        self._file = None

    def __enter__(self):
        self._file = open(*self.args, **self.kwds)
        return self

    def __exit__(self, *args):
        self._file.close()

    def write(self, data):
        self._file.write(data)

    def writeEscaped(self, value):
        self._file.write(html.escape(str(value)))


class Tag:
    tag = NotImplementedError

    def __init__(self, f, attrs=None):
        self.f = f
        self.attrs = attrs

    def __enter__(self):
        attrs = ""
        if self.attrs:
            attrs = " " + " ".join(
                ['{}="{}"'.format(name, value) for name, value in self.attrs.items()]
            )
        self.f.write(r"<{}{}>".format(self.tag, attrs))
        self.f.write("\n")

    def __exit__(self, *args, **kwargs):
        self.f.write(r"</{}>".format(self.tag))
        self.f.write("\n")


class Html(Tag):
    tag = "html"


class Head(Tag):
    tag = "head"


class Body(Tag):
    tag = "body"


class Img(Tag):
    tag = "img"


class B(Tag):
    tag = "b"


class P(Tag):
    tag = "p"


class A(Tag):
    tag = "a"


class Title(Tag):
    tag = "title"


class H1(Tag):
    tag = "h1"


class H2(Tag):
    tag = "h2"


class H3(Tag):
    tag = "h3"


class H4(Tag):
    tag = "h4"


class UL(Tag):
    tag = "ul"


class LI(Tag):
    tag = "li"


class Script(Tag):
    tag = "script"


class Style(Tag):
    tag = "style"


class Div(Tag):
    tag = "div"


class Caption(Tag):
    tag = "caption"


class Table(Tag):
    tag = "table"


class TBody(Tag):
    tag = "tbody"


class THead(Tag):
    tag = "thead"


class TR(Tag):
    tag = "tr"


class TH(Tag):
    tag = "th"


class TD(Tag):
    tag = "td"


class Span(Tag):
    tag = "span"


class Footer(Tag):
    tag = "footer"


class Link(Tag):
    tag = "link"


# ---------------------------


def encode64(file_path):
    """Return the embedded HTML src attribute for an image in base64"""
    xtn = os.path.splitext(file_path)[1][1:]  # [1:] to cut out the period
    if xtn == "pdf":
        from armi import runLog

        runLog.warning(
            "'.pdf' images cannot be embedded into this HTML report. {} will not be inserted.".format(
                file_path
            )
        )
        return "Faulty PDF image inclusion: {} attempted to be inserted but no support is currently offered for such.".format(
            file_path
        )
    with open(file_path, "rb") as img_src:
        return r"data:image/{};base64,{}".format(
            xtn, base64.b64encode(img_src.read()).decode()
        )


# ---------------------------


def writeStandardReportTemplate(f, report):
    f.write(r"<!DOCTYPE html>" + "\n")
    cs = settings.getMasterCs()
    with Html(f):

        with Head(f):
            f.write(r'<meta charset="UTF-8">' + "\n")
            with Title(f):
                f.write(cs.caseTitle)

        with Body(f):

            with Div(
                f,
                attrs={
                    "id": "navbar",
                    "class": "navbar navbar-default navbar-fixed-top",
                },
            ):
                with Div(f, attrs={"class": "container"}):
                    with Div(f, attrs={"class": "navbar-header"}):

                        with Span(
                            f, attrs={"class": "navbar-text navbar-version pull-left"}
                        ):
                            with Img(
                                f,
                                attrs={
                                    "src": encode64(
                                        os.path.join(
                                            context.RES, "images", "armiicon.ico"
                                        )
                                    )
                                },
                            ):
                                pass

                        with A(
                            f,
                            attrs={
                                "class": "navbar-brand",
                                "href": "#",
                                "style": "color: #d9230f;",
                            },
                        ):
                            with B(f):
                                f.write(cs.caseTitle)

                        with Span(
                            f, attrs={"class": "navbar-text navbar-version pull-left"}
                        ):
                            with B(f):
                                f.write(context.USER)

                        with Span(
                            f, attrs={"class": "navbar-text navbar-version pull-left"}
                        ):
                            with B(f):
                                f.write(datetime.datetime.now().isoformat())

            with Div(f, attrs={"class": "container", "style": "padding-top: 20px;"}):

                with Div(f, attrs={"class": "page-header"}):
                    with H1(f):
                        f.write(report.title)
                    with P(f):
                        f.write(cs["comment"])

                report.writeGroupsHTML(f)

                with Footer(
                    f,
                    attrs={
                        "style": "width: 100%; border-top: 1px solid #ccc; padding-top: 10px;"
                    },
                ):
                    with UL(f, attrs={"class": "list-unstyled"}):
                        with LI(f, attrs={"class": "pull-right"}):
                            with A(f, attrs={"href": "#top"}):
                                f.write("Back to top")
                        with LI(f):
                            with A(
                                f,
                                attrs={"href": "https://terrapower.github.io/armi/"},
                            ):
                                f.write("ARMI docs")
                    with P(f):
                        f.write("Automatically generated by ARMI")

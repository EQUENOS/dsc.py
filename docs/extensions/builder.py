# SPDX-License-Identifier: MIT
from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, Any

from docutils import nodes
from sphinx.environment.adapters.indexentries import IndexEntries
from sphinxext.opengraph.descriptionparser import DescriptionParser

if TYPE_CHECKING:
    from _types import SphinxExtensionMeta
    from sphinx.application import Sphinx
    from sphinx.config import Config
    from sphinx.writers.html5 import HTML5Translator

if TYPE_CHECKING:
    translator_base = HTML5Translator
else:
    translator_base = object


class CustomHTML5TranslatorMixin(translator_base):
    def visit_table(self, node: nodes.table) -> None:
        self.body.append('<div class="table-wrapper">')
        super().visit_table(node)

    def depart_table(self, node: nodes.table) -> None:
        super().depart_table(node)
        self.body.append("</div>")


def set_translator(app: Sphinx) -> None:
    if app.builder.format != "html":
        return

    # Insert the `CustomHTML5TranslatorMixin` mixin into all defined
    # translator types, as well as the default translator if not registered already

    translators = app.registry.translators.copy()
    translators.setdefault(app.builder.name, app.builder.default_translator_class)

    for name, cls in translators.items():
        translator = type(
            "CustomHTML5Translator",
            (CustomHTML5TranslatorMixin, cls),
            {},
        )
        app.set_translator(name, translator, override=True)


def patch_genindex(*args: Any) -> None:
    # Instead of overriding `write_genindex` in a custom builder and
    # copying the entire method body while only changing one parameter (group_entries),
    # we just patch the method we want to change instead.
    new_create_index = functools.partialmethod(IndexEntries.create_index, group_entries=False)
    IndexEntries.create_index = new_create_index  # type: ignore


def patch_opengraph(*args: Any) -> None:
    # Patch sphinxext-opengraph's description parser to only take the first section
    # into account, resulting in cleaner descriptions.
    orig = DescriptionParser.dispatch_visit

    def patched_dispatch_visit(self, node: nodes.Element) -> None:
        if isinstance(node, nodes.section):
            if getattr(self, "section_found", False):
                # stop when encountering nested section
                raise nodes.StopTraversal
            self.section_found = True
        return orig(self, node)

    DescriptionParser.dispatch_visit = patched_dispatch_visit


def disable_mathjax(app: Sphinx, config: Config) -> None:
    # prevent installation of mathjax script, which gets installed due to
    # https://github.com/readthedocs/sphinx-hoverxref/commit/7c4655092c482bd414b1816bdb4f393da117062a
    #
    # inspired by https://github.com/readthedocs/sphinx-hoverxref/blob/003b84fee48262f1a969c8143e63c177bd98aa26/hoverxref/extension.py#L151

    for listener in app.events.listeners.get("html-page-context", []):
        module_name = inspect.getmodule(listener.handler).__name__  # type: ignore
        if module_name == "sphinx.ext.mathjax":
            app.disconnect(listener.id)


def setup(app: Sphinx) -> SphinxExtensionMeta:
    app.connect("config-inited", patch_genindex)
    app.connect("config-inited", patch_opengraph)
    app.connect("config-inited", disable_mathjax)
    app.connect("builder-inited", set_translator)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

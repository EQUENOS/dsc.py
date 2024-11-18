# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sphinx.ext.autodoc import AttributeDocumenter

import disnake

if TYPE_CHECKING:
    from sphinx.application import Sphinx

    from ._types import SphinxExtensionMeta


class EnumMemberDocumenter(AttributeDocumenter):
    objtype = "enumattribute"
    directivetype = AttributeDocumenter.objtype
    priority = 10 + AttributeDocumenter.priority

    @classmethod
    def can_document_member(cls, member: Any, membername: str, isattr: bool, parent: Any) -> bool:
        return super().can_document_member(member, membername, isattr, parent) and isinstance(
            member, disnake.enums._EnumValueBase
        )

    def should_suppress_value_header(self) -> bool:
        # always hide enum member values
        return True


def setup(app: Sphinx) -> SphinxExtensionMeta:
    app.setup_extension("sphinx.ext.autodoc")
    app.add_autodocumenter(EnumMemberDocumenter)

    return {
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }

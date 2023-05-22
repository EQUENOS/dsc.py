# SPDX-License-Identifier: MIT

import typing as t

from mypy.plugin import AnalyzeTypeContext, Plugin
from mypy.types import AnyType, EllipsisType, RawExpressionType, Type, TypeOfAny


class DisnakePlugin(Plugin):
    def get_type_analyze_hook(
        self, fullname: str
    ) -> t.Optional[t.Callable[[AnalyzeTypeContext], Type]]:
        if fullname == "disnake.ext.commands.params.Range":
            return range_type_analyze_callback
        if fullname == "disnake.ext.commands.params.String":
            return string_type_analyze_callback
        return None


def range_type_analyze_callback(ctx: AnalyzeTypeContext) -> Type:
    args = ctx.type.args

    if len(args) != 2:
        ctx.api.fail(f'"Range" expected 2 parameters, got {len(args)}', ctx.context)
        return AnyType(TypeOfAny.from_error)

    for arg in args:
        if isinstance(arg, EllipsisType):
            continue
        if not isinstance(arg, RawExpressionType):
            ctx.api.fail('invalid usage of "Range"', ctx.context)
            return AnyType(TypeOfAny.from_error)

        name = arg.simple_name()
        # if one is a float, `Range.underlying_type` returns `float`
        if name == "float":
            return ctx.api.named_type("builtins.float", [])
        # otherwise it should be an int; fail if it isn't
        if name != "int":
            ctx.api.fail(f'"Range" parameters must be int or float, not {name}', ctx.context)
            return AnyType(TypeOfAny.from_error)

    return ctx.api.named_type("builtins.int", [])


def string_type_analyze_callback(ctx: AnalyzeTypeContext) -> Type:
    args = ctx.type.args

    if len(args) != 2:
        ctx.api.fail(f'"String" expected 2 parameters, got {len(args)}', ctx.context)
        return AnyType(TypeOfAny.from_error)

    for arg in args:
        if isinstance(arg, EllipsisType):
            continue
        if not isinstance(arg, RawExpressionType):
            ctx.api.fail('invalid usage of "String"', ctx.context)
            return AnyType(TypeOfAny.from_error)

        name = arg.simple_name()
        if name != "int":
            ctx.api.fail(f'"String" parameters must be int, not {name}', ctx.context)
            return AnyType(TypeOfAny.from_error)

    return ctx.api.named_type("builtins.str", [])


def plugin(version: str) -> t.Type[Plugin]:
    return DisnakePlugin

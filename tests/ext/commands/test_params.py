# SPDX-License-Identifier: MIT

import math
import sys
from typing import Any, Optional, Union
from unittest import mock

import pytest

import disnake
from disnake import Member, Role, User
from disnake.ext import commands

OptionType = disnake.OptionType


class TestParamInfo:
    @pytest.mark.parametrize(
        ("annotation", "expected_type", "arg_types"),
        [
            # should accept user or member
            (disnake.abc.User, OptionType.user, [User, Member]),
            (User, OptionType.user, [User, Member]),
            (Union[User, Member], OptionType.user, [User, Member]),
            # only accepts member, not user
            (Member, OptionType.user, [Member]),
            # only accepts role
            (Role, OptionType.role, [Role]),
            # should accept member or role
            (Union[Member, Role], OptionType.mentionable, [Member, Role]),
            # should accept everything
            (Union[User, Role], OptionType.mentionable, [User, Member, Role]),
            (Union[User, Member, Role], OptionType.mentionable, [User, Member, Role]),
            (disnake.abc.Snowflake, OptionType.mentionable, [User, Member, Role]),
        ],
    )
    @pytest.mark.asyncio
    async def test_verify_type(self, annotation, expected_type, arg_types) -> None:
        # tests that the Discord option type is determined correctly,
        # and that valid argument types are accepted
        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        # type should be valid
        assert info.discord_type is expected_type

        for arg_type in arg_types:
            arg_mock = mock.Mock(arg_type)
            assert await info.verify_type(mock.Mock(), arg_mock) is arg_mock

    @pytest.mark.parametrize(
        ("annotation", "arg_types"),
        [
            (Member, [User]),
            (Union[Member, Role], [User]),
        ],
    )
    @pytest.mark.asyncio
    async def test_verify_type__invalid_member(self, annotation, arg_types) -> None:
        # tests that invalid argument types result in `verify_type` raising an exception
        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        for arg_type in arg_types:
            arg_mock = mock.Mock(arg_type)
            with pytest.raises(commands.errors.MemberNotFound):
                await info.verify_type(mock.Mock(), arg_mock)


# this uses `Range` for testing `_BaseRange`, `String` should work equally
class TestBaseRange:
    @pytest.mark.parametrize("args", [int, (int,), (int, 1, 2, 3)])
    def test_param_count(self, args) -> None:
        with pytest.raises(TypeError, match=r"`Range` expects 3 arguments"):
            commands.Range[args]  # type: ignore

    @pytest.mark.parametrize("value", ["int", 42, Optional[int], Union[int, float]])
    def test_invalid_type(self, value) -> None:
        with pytest.raises(TypeError, match=r"First `Range` argument must be a type"):
            commands.Range[value, 1, 10]

    @pytest.mark.parametrize("value", ["42", int])
    def test_invalid_bound(self, value) -> None:
        with pytest.raises(TypeError, match=r"min value must be int, float"):
            commands.Range[int, value, 1]

        with pytest.raises(TypeError, match=r"max value must be int, float"):
            commands.Range[int, 1, value]

    def test_invalid_min_max(self) -> None:
        with pytest.raises(ValueError, match=r"`Range` bounds cannot both be empty"):
            commands.Range[int, None, ...]

        with pytest.raises(ValueError, match=r"`Range` minimum \(\d+\) must be less"):
            commands.Range[int, 100, 99]

    @pytest.mark.parametrize("empty", [None, ...])
    def test_ellipsis(self, empty) -> None:
        x: Any = commands.Range[int, 1, empty]
        assert x.min_value == 1
        assert x.max_value is None
        assert repr(x) == "Range[int, 1, ...]"

        x: Any = commands.Range[float, empty, -10]
        assert x.min_value is None
        assert x.max_value == -10
        assert repr(x) == "Range[float, ..., -10]"

    @pytest.mark.parametrize(
        ("create", "expected"),
        [
            (lambda: commands.Range[1, 2], (int, 1, 2)),  # type: ignore
            (lambda: commands.Range[0, 10.0], (float, 0, 10.0)),  # type: ignore
            (lambda: commands.Range[..., 10.0], (float, None, 10.0)),
            (lambda: commands.String[5, 10], (str, 5, 10)),  # type: ignore
        ],
    )
    def test_backwards_compatible(self, create: Any, expected) -> None:
        with pytest.warns(DeprecationWarning, match=r"without an explicit type argument"):
            value = create()
            assert (value.underlying_type, value.min_value, value.max_value) == expected


class TestRange:
    def test_disallowed_type(self) -> None:
        with pytest.raises(TypeError, match=r"First `Range` argument must be int/float, not"):
            commands.Range[str, 1, 10]

    def test_int_float_bounds(self) -> None:
        with pytest.raises(TypeError, match=r"Range.* bounds must be int, not float"):
            commands.Range[int, 1.0, 10]

        with pytest.raises(TypeError, match=r"Range.* bounds must be int, not float"):
            commands.Range[int, 1, 10.0]

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
    def test_nan(self, value) -> None:
        with pytest.raises(ValueError, match=r"min value may not be NaN, inf, or -inf"):
            commands.Range[float, value, 100]

    def test_valid(self) -> None:
        x: Any = commands.Range[int, -1, 2]
        assert x.underlying_type is int

        x: Any = commands.Range[float, ..., 23.45]
        assert x.underlying_type is float


class TestString:
    def test_disallowed_type(self) -> None:
        with pytest.raises(TypeError, match=r"First `String` argument must be str, not"):
            commands.String[int, 1, 10]

    def test_float_bound(self) -> None:
        with pytest.raises(TypeError, match=r"String bounds must be int, not float"):
            commands.String[str, 1.0, ...]

    def test_negative_bound(self) -> None:
        with pytest.raises(ValueError, match=r"String bounds may not be negative"):
            commands.String[str, -5, 10]

    def test_valid(self) -> None:
        commands.String[str, 10, 10]
        commands.String[str, 100, 1234]
        commands.String[str, 100, ...]


class TestRangeStringParam:
    @pytest.mark.parametrize(
        "annotation", [commands.Range[int, 1, 2], commands.Range[float, ..., 12.3]]
    )
    def test_range(self, annotation) -> None:
        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        assert info.min_value == annotation.min_value
        assert info.max_value == annotation.max_value
        assert info.type == annotation.underlying_type

    def test_string(self) -> None:
        annotation: Any = commands.String[str, 4, 10]

        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        assert info.min_length == annotation.min_value
        assert info.max_length == annotation.max_value
        assert info.min_value is None
        assert info.max_value is None
        assert info.type == annotation.underlying_type

    @pytest.mark.parametrize(
        "annotation_str",
        [
            "Optional[commands.Range[int, 1, 2]]",
            # 3.10 union syntax
            pytest.param(
                "commands.Range[int, 1, 2] | None",
                marks=pytest.mark.skipif(
                    sys.version_info < (3, 10), reason="syntax requires py3.10"
                ),
            ),
        ],
    )
    def test_optional(self, annotation_str) -> None:
        annotation = disnake.utils.resolve_annotation(annotation_str, globals(), None, None)
        assert type(None) in annotation.__args__

        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        assert info.min_value == 1
        assert info.max_value == 2
        assert info.type is int


class TestIsolateSelf:
    def test_function_simple(self) -> None:
        def func(a: int) -> None:
            ...

        (cog, inter), params = commands.params.isolate_self(func)
        assert cog is None
        assert inter is None
        assert params.keys() == {"a"}

    def test_function_inter(self) -> None:
        def func(inter: disnake.ApplicationCommandInteraction, a: int) -> None:
            ...

        (cog, inter), params = commands.params.isolate_self(func)
        assert cog is None  # should not be set
        assert inter is not None
        assert params.keys() == {"a"}

    def test_unbound_method(self) -> None:
        class Cog(commands.Cog):
            def func(self, inter: disnake.ApplicationCommandInteraction, a: int) -> None:
                ...

        (cog, inter), params = commands.params.isolate_self(Cog.func)
        assert cog is not None  # *should* be set here
        assert inter is not None
        assert params.keys() == {"a"}

    # I don't think the param parsing logic ever handles bound methods, but testing for regressions anyway
    def test_bound_method(self) -> None:
        class Cog(commands.Cog):
            def func(self, inter: disnake.ApplicationCommandInteraction, a: int) -> None:
                ...

        (cog, inter), params = commands.params.isolate_self(Cog().func)
        assert cog is None  # should not be set here, since method is already bound
        assert inter is not None
        assert params.keys() == {"a"}

    def test_generic(self) -> None:
        def func(inter: disnake.ApplicationCommandInteraction[commands.Bot], a: int) -> None:
            ...

        (cog, inter), params = commands.params.isolate_self(func)
        assert cog is None
        assert inter is not None
        assert params.keys() == {"a"}

    def test_inter_union(self) -> None:
        def func(
            inter: Union[commands.Context, disnake.ApplicationCommandInteraction[commands.Bot]],
            a: int,
        ) -> None:
            ...

        (cog, inter), params = commands.params.isolate_self(func)
        assert cog is None
        assert inter is not None
        assert params.keys() == {"a"}

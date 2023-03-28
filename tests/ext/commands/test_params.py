# SPDX-License-Identifier: MIT

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
    @pytest.mark.parametrize("args", [int, (int,), (int, 10), (int, 1, 2, 3)])
    def test_param_count(self, args):
        with pytest.raises(TypeError, match=r"`Range` expects 3 type arguments"):
            commands.Range[args]  # type: ignore

    @pytest.mark.parametrize("value", ["int", 42, Optional[int], Union[int, float]])
    def test_invalid_type(self, value):
        with pytest.raises(TypeError, match=r"First `Range` argument must be a type"):
            commands.Range[value, 1, 10]

    @pytest.mark.parametrize("value", ["42", int])
    def test_invalid_bound(self, value):
        with pytest.raises(TypeError, match=r"min value must be int, float"):
            commands.Range[int, value, 1]

        with pytest.raises(TypeError, match=r"max value must be int, float"):
            commands.Range[int, 1, value]

    def test_invalid_min_max(self):
        with pytest.raises(ValueError, match=r"`Range` bounds cannot both be empty"):
            commands.Range[int, None, ...]

        with pytest.raises(ValueError, match=r"`Range` minimum \(\d+\) must be less"):
            commands.Range[int, 100, 99]

    @pytest.mark.parametrize("empty", [None, ...])
    def test_ellipsis(self, empty):
        x: Any = commands.Range[int, 1, empty]
        assert x.min_value == 1
        assert x.max_value is None
        assert repr(x) == "Range[int, 1, ...]"

        x: Any = commands.Range[float, empty, -10]
        assert x.min_value is None
        assert x.max_value == -10
        assert repr(x) == "Range[float, ..., -10]"


class TestRange:
    def test_disallowed_type(self):
        with pytest.raises(TypeError, match=r"First `Range` argument must be int/float, not"):
            commands.Range[str, 1, 10]

    def test_int_float_bounds(self):
        with pytest.raises(TypeError, match=r"Range.* bounds must be int, not float"):
            commands.Range[int, 1.0, 10]

        with pytest.raises(TypeError, match=r"Range.* bounds must be int, not float"):
            commands.Range[int, 1, 10.0]

    def test_valid(self):
        x: Any = commands.Range[int, -1, 2]
        assert x.underlying_type == int

        x: Any = commands.Range[float, ..., 23.45]
        assert x.underlying_type == float


class TestString:
    def test_disallowed_type(self):
        with pytest.raises(TypeError, match=r"First `String` argument must be str, not"):
            commands.String[int, 1, 10]

    def test_float_bound(self):
        with pytest.raises(TypeError, match=r"String bounds must be int, not float"):
            commands.String[str, 1.0, ...]

    def test_negative_bound(self):
        with pytest.raises(ValueError, match=r"String bounds may not be negative"):
            commands.String[str, -5, 10]

    def test_valid(self):
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

    def test_string(self):
        annotation: Any = commands.String[str, 4, 10]

        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        assert info.min_length == annotation.min_value
        assert info.max_length == annotation.max_value
        assert info.min_value is None
        assert info.max_value is None
        assert info.type == annotation.underlying_type

    # uses lambdas since new union syntax isn't supported on all versions
    @pytest.mark.parametrize(
        "get_annotation",
        [
            lambda: Optional[commands.Range[int, 1, 2]],
            # 3.10 union syntax
            pytest.param(
                lambda: commands.Range[float, 1.2, 3.4] | None,
                marks=pytest.mark.skipif(
                    sys.version_info < (3, 10), reason="syntax requires py3.10"
                ),
            ),
        ],
    )
    def test_optional(self, get_annotation) -> None:
        annotation = get_annotation()
        info = commands.ParamInfo()
        info.parse_annotation(annotation)

        range = annotation.__args__[0]
        assert info.min_value == range.min_value
        assert info.max_value == range.max_value
        assert info.type == range.underlying_type

# SPDX-License-Identifier: MIT

import asyncio
import datetime
import functools
import inspect
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Tuple, TypeVar, Union
from unittest import mock

import pytest
import yarl

import disnake
from disnake import utils

from . import helpers, utils_helper_module

if TYPE_CHECKING:
    from typing_extensions import TypeAliasType
elif sys.version_info >= (3, 12):
    # non-3.12 tests shouldn't be using this
    from typing import TypeAliasType


def test_missing() -> None:
    assert utils.MISSING != utils.MISSING
    assert not bool(utils.MISSING)


def test_cached_property() -> None:
    class Test:
        @utils.cached_property
        def prop(self) -> object:
            """Does things"""
            return object()

    inst = Test()
    assert inst.prop is inst.prop
    assert Test.prop.__doc__ == "Does things"
    assert isinstance(Test.prop, utils.cached_property)


def test_cached_slot_property() -> None:
    class Test:
        __slots__ = ("_cs_prop",)

        @utils.cached_slot_property("_cs_prop")
        def prop(self) -> object:
            """Does things"""
            return object()

    inst = Test()
    assert inst.prop is inst.prop
    assert Test.prop.__doc__ == "Does things"
    assert isinstance(Test.prop, utils.CachedSlotProperty)


def test_parse_time() -> None:
    assert utils.parse_time(None) is None
    assert utils.parse_time("2021-08-29T13:50:00+00:00") == datetime.datetime(
        2021, 8, 29, 13, 50, 0, tzinfo=timezone.utc
    )


def test_copy_doc() -> None:
    def func(num: int, *, arg: str) -> float:
        """Returns the best number"""
        ...

    @utils.copy_doc(func)
    def func2(*args: Any, **kwargs: Any) -> Any: ...

    assert func2.__doc__ == func.__doc__
    assert inspect.signature(func) == inspect.signature(func2)


@mock.patch.object(warnings, "warn")
@pytest.mark.parametrize(
    ("instead", "msg"),
    [(None, "stuff is deprecated."), ("other", "stuff is deprecated, use other instead.")],
)
def test_deprecated(mock_warn: mock.Mock, instead, msg) -> None:
    @utils.deprecated(instead)
    def stuff(num: int) -> int:
        return num

    assert stuff(42) == 42
    mock_warn.assert_called_once_with(msg, stacklevel=3, category=DeprecationWarning)


@mock.patch.object(utils, "_root_module_path", os.path.dirname(__file__))
@pytest.mark.xfail(
    sys.version_info < (3, 12),
    raises=AssertionError,
    strict=True,
    reason="requires 3.12 functionality",
)
def test_deprecated_skip() -> None:
    def func(n: int) -> None:
        if n == 0:
            utils.warn_deprecated("test", skip_internal_frames=True)
        else:
            func(n - 1)

    with warnings.catch_warnings(record=True) as result:
        # show a warning a couple frames deep
        func(10)

    # if we successfully skipped all frames in the current module,
    # we should end up in the mock decorator's frame
    assert len(result) == 1
    assert result[0].filename == mock.__file__


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        (
            {},
            {"scope": "bot"},
        ),
        (
            {
                "permissions": disnake.Permissions(42),
                "guild": disnake.Object(9999),
                "redirect_uri": "http://endless.horse",
                "scopes": ["bot", "applications.commands"],
                "disable_guild_select": True,
                "integration_type": 1,
            },
            {
                "scope": "bot applications.commands",
                "permissions": "42",
                "guild_id": "9999",
                "response_type": "code",
                "redirect_uri": "http://endless.horse",
                "disable_guild_select": "true",
                "integration_type": "1",
            },
        ),
    ],
)
def test_oauth_url(params, expected) -> None:
    url = utils.oauth_url(1234, **params)
    assert dict(yarl.URL(url).query) == {"client_id": "1234", **expected}


@pytest.mark.parametrize(
    ("num", "expected"),
    [
        (0, datetime.datetime(2015, 1, 1, tzinfo=timezone.utc)),
        (881536165478499999, datetime.datetime(2021, 8, 29, 13, 50, 0, tzinfo=timezone.utc)),
        (10000000000000000000, datetime.datetime(2090, 7, 20, 17, 49, 51, tzinfo=timezone.utc)),
    ],
)
def test_snowflake_time(num: int, expected) -> None:
    assert utils.snowflake_time(num).replace(microsecond=0) == expected


@pytest.mark.parametrize(
    ("dt", "expected"),
    [
        (datetime.datetime(2015, 1, 1, tzinfo=timezone.utc), 0),
        (datetime.datetime(2021, 8, 29, 13, 50, 0, tzinfo=timezone.utc), 881536165478400000),
    ],
)
def test_time_snowflake(dt, expected) -> None:
    low = utils.time_snowflake(dt)
    assert low == expected

    high = utils.time_snowflake(dt, high=True)
    assert low < high
    assert high + 1 == utils.time_snowflake(dt + timedelta(milliseconds=1))


def test_find() -> None:
    pred = lambda i: i == 42  # type: ignore
    assert utils.find(pred, []) is None
    assert utils.find(pred, [42]) == 42
    assert utils.find(pred, [1, 2, 42, 3, 4]) == 42

    pred = lambda i: i.id == 42  # type: ignore
    lst = list(map(disnake.Object, [1, 42, 42, 2]))
    assert utils.find(pred, lst) is lst[1]


def test_get() -> None:
    @dataclass
    class A:
        value: int

    @dataclass
    class B:
        value: int
        a: A

    lst = [B(123, A(42))]
    with pytest.raises(AttributeError):
        utils.get(lst, something=None)

    # test special case for len(lst) == 1
    assert utils.get(lst, value=123) == lst[0]
    assert utils.get(lst, a__value=42) == lst[0]
    assert utils.get(lst, value=111111) is None

    # general case
    lst += [B(456, A(42)), B(789, A(99999))]
    assert utils.get(lst, value=789) == lst[2]
    assert utils.get(lst, a__value=42) == lst[0]

    assert utils.get(lst, value=456, a__value=42) is lst[1]
    assert utils.get(lst, value=789, a__value=42) is None


@pytest.mark.parametrize(
    ("it", "expected"),
    [
        ([1, 1, 1], [1]),
        ([3, 2, 1, 2], [3, 2, 1]),
        ([1, 2], [1, 2]),
        ([2, 1], [2, 1]),
    ],
)
def test_unique(it, expected) -> None:
    assert utils._unique(it) == expected


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, None),
        ({"a": 42}, None),
        ({"key": None}, None),
        ({"key": 42}, 42),
        ({"key": "42"}, 42),
    ],
)
def test_get_as_snowflake(data, expected) -> None:
    assert utils._get_as_snowflake(data, "key") == expected


def test_maybe_cast() -> None:
    convert = lambda v: v + 1  # type: ignore
    default = object()

    assert utils._maybe_cast(utils.MISSING, convert) is None
    assert utils._maybe_cast(utils.MISSING, convert, default) is default

    assert utils._maybe_cast(42, convert) == 43
    assert utils._maybe_cast(42, convert, default) == 43


@pytest.mark.parametrize(
    ("data", "expected_mime", "expected_ext"),
    [
        (b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a", "image/png", ".png"),
        (b"\xff\xd8\xffxxxJFIF", "image/jpeg", ".jpg"),
        (b"\xff\xd8\xffxxxExif", "image/jpeg", ".jpg"),
        (b"\xff\xd8\xffxxxxxxxxxxxx", "image/jpeg", ".jpg"),
        (b"xxxxxxJFIF", "image/jpeg", ".jpg"),
        (b"\x47\x49\x46\x38\x37\x61", "image/gif", ".gif"),
        (b"\x47\x49\x46\x38\x39\x61", "image/gif", ".gif"),
        (b"RIFFxxxxWEBP", "image/webp", ".webp"),
        (b"ID3", "audio/mpeg", ".mp3"),
        (b"\xff\xf3", "audio/mpeg", ".mp3"),
        (b"OggS", "audio/ogg", ".ogg"),
    ],
)
def test_mime_type_valid(data, expected_mime, expected_ext) -> None:
    for d in (data, data + b"\xff"):
        assert utils._get_mime_type_for_data(d) == expected_mime
        assert utils._get_extension_for_data(d) == expected_ext

    prefixed = b"\xff" + data
    with pytest.raises(ValueError, match=r"Unsupported file type provided"):
        utils._get_mime_type_for_data(prefixed)
    assert utils._get_extension_for_data(prefixed) is None


@pytest.mark.parametrize(
    "data",
    [
        b"\x89\x50\x4e\x47\x0d\x0a\x1a\xff",  # invalid png end
        b"\x47\x49\x46\x38\x38\x61",  # invalid gif version
        b"RIFFxxxxAAAA",
        b"AAAAxxxxWEBP",
        b"",
    ],
)
def test_mime_type_invalid(data) -> None:
    with pytest.raises(ValueError, match=r"Unsupported file type provided"):
        utils._get_mime_type_for_data(data)
    assert utils._get_extension_for_data(data) is None


@pytest.mark.asyncio
async def test_assetbytes_base64() -> None:
    assert await utils._assetbytes_to_base64_data(None) is None

    # test bytes
    data = b"RIFFabcdWEBPwxyz"
    expected = "data:image/webp;base64,UklGRmFiY2RXRUJQd3h5eg=="
    for conv in (bytes, bytearray, memoryview):
        assert await utils._assetbytes_to_base64_data(conv(data)) == expected

    # test assets
    mock_asset = mock.Mock(disnake.Asset)
    mock_asset.read = mock.AsyncMock(return_value=data)

    assert await utils._assetbytes_to_base64_data(mock_asset) == expected


@pytest.mark.parametrize(
    ("after", "use_clock", "expected"),
    [
        # use reset_after
        (42, False, 42),
        # use timestamp
        (42, True, 7),
        (utils.MISSING, False, 7),
        (utils.MISSING, True, 7),
    ],
)
@helpers.freeze_time()
def test_parse_ratelimit_header(after, use_clock, expected) -> None:
    reset_time = utils.utcnow() + timedelta(seconds=7)

    request = mock.Mock()
    request.headers = {"X-Ratelimit-Reset": reset_time.timestamp()}
    if after is not utils.MISSING:
        request.headers["X-Ratelimit-Reset-After"] = after

    assert utils._parse_ratelimit_header(request, use_clock=use_clock) == expected


@pytest.mark.parametrize(
    "func",
    [
        mock.Mock(),
        mock.AsyncMock(),
    ],
)
@pytest.mark.asyncio
async def test_maybe_coroutine(func: mock.Mock) -> None:
    assert await utils.maybe_coroutine(func, 42, arg="uwu") is func.return_value
    func.assert_called_once_with(42, arg="uwu")


@pytest.mark.parametrize("mock_type", [mock.Mock, mock.AsyncMock])
@pytest.mark.parametrize(
    ("gen", "expected"),
    [
        ([], True),
        ([True], True),
        ([False], False),
        ([False, True], False),
        ([True, False, True], False),
    ],
)
@pytest.mark.asyncio
async def test_async_all(mock_type, gen, expected) -> None:
    assert await utils.async_all(mock_type(return_value=x)() for x in gen) is expected


@pytest.mark.looptime
@pytest.mark.asyncio
async def test_sane_wait_for(looptime) -> None:
    times = [10, 50, 25]

    def create():
        return [asyncio.sleep(n) for n in times]

    # no timeout
    await utils.sane_wait_for(create(), timeout=100)
    assert looptime == 50

    # timeout
    tasks = [asyncio.create_task(c) for c in create()]
    with pytest.raises(asyncio.TimeoutError):
        await utils.sane_wait_for(tasks, timeout=40)
    assert looptime == 90

    assert [t.done() for t in tasks] == [True, False, True]

    # tasks should continue running even if timeout occurred
    await asyncio.sleep(1000)
    assert all(t.done() for t in tasks)


def test_get_slots() -> None:
    class A:
        __slots__ = ("a", "a2")

    class B:
        __slots__ = ()

    class C(A):
        __slots__ = {"c": "uwu"}

    class D(B, C):
        __slots__ = "xyz"  # noqa: PLC0205  # this is intentional

    assert list(utils.get_slots(D)) == ["a", "a2", "c", "xyz"]


@pytest.mark.parametrize(
    "tz",
    [
        # naive datetime
        utils.MISSING,
        # aware datetime
        None,
        timezone.utc,
        timezone(timedelta(hours=-9)),
    ],
)
@pytest.mark.parametrize(("delta", "expected"), [(7, 7), (-100, 0)])
@helpers.freeze_time()
def test_compute_timedelta(tz, delta, expected) -> None:
    dt = datetime.datetime.now()  # noqa: DTZ005
    if tz is not utils.MISSING:
        dt = dt.astimezone(tz)
    assert utils.compute_timedelta(dt + timedelta(seconds=delta)) == expected


@pytest.mark.parametrize(("delta", "expected"), [(0, 0), (42, 42), (-100, 0)])
@pytest.mark.looptime
@pytest.mark.asyncio
@helpers.freeze_time()
async def test_sleep_until(looptime, delta, expected) -> None:
    o = object()
    assert await utils.sleep_until(utils.utcnow() + timedelta(seconds=delta), o) is o
    assert looptime == expected


def test_utcnow() -> None:
    assert utils.utcnow().tzinfo == timezone.utc


def test_valid_icon_size() -> None:
    for s in (2**x for x in range(4, 13)):
        assert utils.valid_icon_size(s)

    for s in [0, 1, 2, 8, 24, 100, 2**20]:
        assert not utils.valid_icon_size(s)


@pytest.mark.parametrize(("s", "expected"), [("a一b", 4), ("abc", 3)])
def test_string_width(s, expected) -> None:
    assert utils._string_width(s) == expected


@pytest.mark.parametrize(
    ("url", "params", "expected"),
    [
        (mock.Mock(disnake.Invite, code="uwu"), {}, "uwu"),
        ("uwu", {}, "uwu"),
        ("https://discord.com/disnake", {}, "https://discord.com/disnake"),
        ("https://discord.com/invite/disnake", {}, "disnake"),
        ("http://discord.gg/disnake?param=123%20456", {"param": "123 456"}, "disnake"),
        ("https://discordapp.com/invite/disnake?a=1&a=2", {"a": "1"}, "disnake"),
    ],
)
@pytest.mark.parametrize("with_params", [False, True])
def test_resolve_invite(url, params, expected, with_params) -> None:
    res = utils.resolve_invite(url, with_params=with_params)
    if with_params:
        assert res == (expected, params)
    else:
        assert res == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (mock.Mock(disnake.Template, code="uwu"), "uwu"),
        ("uwu", "uwu"),
        ("http://discord.com/disnake", "http://discord.com/disnake"),
        ("http://discord.new/disnake", "disnake"),
        ("https://discord.com/template/disnake", "disnake"),
        ("https://discordapp.com/template/disnake", "disnake"),
    ],
)
def test_resolve_template(url, expected) -> None:
    assert utils.resolve_template(url) == expected


@pytest.mark.parametrize(
    ("text", "exp_remove", "exp_escape"),
    [
        (
            # this is obviously not valid markdown for the most part,
            # it's just meant to test several combinations
            "*hi* ~~a~ |aaa~*\\``\n`py x``` __uwu__ y",
            "hi a aaa\npy x uwu y",
            r"\*hi\* \~\~a\~ \|aaa\~\*\\\`\`" "\n" r"\`py x\`\`\` \_\_uwu\_\_ y",
        ),
        (
            r"## disnake",
            "disnake",
            r"\#\# disnake",
        ),
        (
            r"""Inside is a long list of why markdown is an amazing tool
- markdown supports lists
 - honestly its a great tool that markdown supports said lists
   - this is wrong but uh we'll get to that
""",
            r"""Inside is a long list of why markdown is an amazing tool
markdown supports lists
 honestly its a great tool that markdown supports said lists
   this is wrong but uh we'll get to that
""",
            r"""Inside is a long list of why markdown is an amazing tool
\- markdown supports lists
 \- honestly its a great tool that markdown supports said lists
   \- this is wrong but uh we'll get to that
""",
        ),
        (
            "aaaaa\n> h\n>> abc \n>>> te*st_",
            "aaaaa\nh\n>> abc \ntest",
            "aaaaa\n\\> h\n>> abc \n\\>\\>\\> te\\*st\\_",
        ),
        (
            "*h*\n> [li|nk](~~url~~) xyz **https://google.com/stuff?uwu=owo",
            "h\n xyz https://google.com/stuff?uwu=owo",
            # NOTE: currently doesn't escape inside `[x](y)`, should that be changed?
            r"\*h\*" "\n" r"\> \[li|nk](~~url~~) xyz \*\*https://google.com/stuff?uwu=owo",
        ),
    ],
)
def test_markdown(text: str, exp_remove, exp_escape) -> None:
    assert utils.remove_markdown(text, ignore_links=False) == exp_remove
    assert utils.remove_markdown(text, ignore_links=True) == exp_remove

    assert utils.escape_markdown(text, ignore_links=False) == exp_escape
    assert utils.escape_markdown(text, ignore_links=True) == exp_escape


@pytest.mark.parametrize(
    ("text", "expected", "expected_ignore"),
    [
        (
            "http://google.com/~test/hi_test ~~a~~",
            "http://google.com/test/hitest a",
            "http://google.com/~test/hi_test a",
        ),
        (
            "abc [link](http://test~test.com)\n>>> <http://endless.horse/_*>",
            "abc \n<http://endless.horse/>",
            "abc \n<http://endless.horse/_*>",
        ),
    ],
)
def test_markdown_links(text: str, expected, expected_ignore) -> None:
    assert utils.remove_markdown(text, ignore_links=False) == expected
    assert utils.remove_markdown(text, ignore_links=True) == expected_ignore


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("@everyone hey look at this cat", "@\u200beveryone hey look at this cat"),
        ("test @here", "test @\u200bhere"),
        ("<@12341234123412341> hi", "<@\u200b12341234123412341> hi"),
        ("<@!12341234123412341>", "<@\u200b!12341234123412341>"),
        ("<@&12341234123412341>", "<@\u200b&12341234123412341>"),
    ],
)
def test_escape_mentions(text: str, expected) -> None:
    assert utils.escape_mentions(text) == expected


@pytest.mark.parametrize(
    ("docstring", "expected"),
    [
        (None, ""),
        ("", ""),
        ("test abc", "test abc"),
        (
            """
            test
            hi


            aaaaaaa
            xyz: abc

            stuff
            -----
            something
            """,
            "test\nhi\n\n\naaaaaaa\nxyz: abc",
        ),
        # other chars
        (
            """
            stuff
            -----+
            abc
            """,
            "stuff\n-----+\nabc",
        ),
        # additional spaces in front of line
        (
            """
             stuff
            -----
            abc
            """,
            "stuff\n-----\nabc",
        ),
        # invalid underline length
        (
            """
            stuff
            ----
            abc
            """,
            "stuff\n----\nabc",
        ),
    ],
)
def test_parse_docstring_desc(docstring: Optional[str], expected) -> None:
    def f() -> None: ...

    f.__doc__ = docstring
    assert utils.parse_docstring(f) == {
        "description": expected,
        "params": {},
        "localization_key_name": None,
        "localization_key_desc": None,
    }


@pytest.mark.parametrize(
    ("docstring", "expected"),
    [
        (
            """
            This does stuff.

            Parameters
            ----------
            something: a value
            other_something: :class:`int`
                another value,
                wow
            thingy: a very cool thingy

            Returns
            -------
            Nothing.
            """,
            {
                "something": {"name": "something", "description": "a value"},
                "other_something": {
                    "name": "other_something",
                    "description": "another value,\nwow",
                },
                "thingy": {"name": "thingy", "description": "a very cool thingy"},
            },
        ),
        # invalid underline length
        (
            """
            Parameters
            ---------
            something: abc
            """,
            {},
        ),
        # missing next line
        (
            """
            Parameters
            ----------
            """,
            {},
        ),
    ],
)
def test_parse_docstring_param(docstring: str, expected) -> None:
    def f() -> None: ...

    f.__doc__ = docstring
    expected = {
        k: {**v, "type": None, "localization_key_name": None, "localization_key_desc": None}
        for k, v in expected.items()
    }
    assert utils.parse_docstring(f)["params"] == expected  # ignore description


def test_parse_docstring_localizations() -> None:
    def f() -> None:
        """Does stuff. {{cool_key}}

        Parameters
        ----------
        p1: {{ PARAM_1 }} Probably a number.
        p2: str
            Definitely a string {{   PARAM_X }}
        """

    assert utils.parse_docstring(f) == {
        "description": "Does stuff.",
        "localization_key_name": "cool_key_NAME",
        "localization_key_desc": "cool_key_DESCRIPTION",
        "params": {
            "p1": {
                "name": "p1",
                "description": "Probably a number.",
                "localization_key_name": "PARAM_1_NAME",
                "localization_key_desc": "PARAM_1_DESCRIPTION",
                "type": None,
            },
            "p2": {
                "name": "p2",
                "description": "Definitely a string",
                "localization_key_name": "PARAM_X_NAME",
                "localization_key_desc": "PARAM_X_DESCRIPTION",
                "type": None,
            },
        },
    }


@pytest.mark.parametrize(
    ("it", "max_size", "expected"),
    [
        ([], 3, []),
        ([0], 3, [[0]]),
        ([0, 1, 2], 2, [[0, 1], [2]]),
        ([0, 1, 2, 3, 4, 5], 3, [[0, 1, 2], [3, 4, 5]]),
    ],
)
@pytest.mark.parametrize("sync", [False, True])
@pytest.mark.asyncio
async def test_as_chunks(sync, it, max_size: int, expected) -> None:
    if sync:
        assert list(utils.as_chunks(it, max_size)) == expected
    else:

        async def _it():
            for x in it:
                yield x

        assert [x async for x in utils.as_chunks(_it(), max_size)] == expected


@pytest.mark.parametrize("max_size", [-1, 0])
def test_as_chunks_size(max_size: int) -> None:
    with pytest.raises(ValueError, match=r"Chunk sizes must be greater than 0."):
        utils.as_chunks(iter([]), max_size)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ([], ()),
        ([disnake.CommandInter, int, Optional[str]], (disnake.CommandInter, int, Optional[str])),
        # check flattening + deduplication (both of these are done automatically in 3.9.1+)
        ([float, Literal[1, 2, Literal[3, 4]], Literal["a", "bc"]], (float, 1, 2, 3, 4, "a", "bc")),
        ([Literal[1, 1, 2, 3, 3]], (1, 2, 3)),
    ],
)
def test_flatten_literal_params(params, expected) -> None:
    assert utils.flatten_literal_params(params) == expected


NoneType = type(None)


@pytest.mark.parametrize(
    ("params", "expected"),
    [([NoneType], (NoneType,)), ([NoneType, int, NoneType, float], (int, float, NoneType))],
)
def test_normalise_optional_params(params, expected) -> None:
    assert utils.normalise_optional_params(params) == expected


@pytest.mark.parametrize(
    ("tp", "expected", "expected_cache"),
    [
        # simple types
        (None, NoneType, False),
        (int, int, False),
        # complex types
        (List[int], List[int], False),
        (Dict[float, "List[yarl.URL]"], Dict[float, List[yarl.URL]], True),
        (Literal[1, Literal[False], "hi"], Literal[1, False, "hi"], False),
        # unions
        (Union[timezone, float], Union[timezone, float], False),
        (Optional[int], Optional[int], False),
        (Union["tuple", None, int], Union[tuple, int, None], True),
        # forward refs
        ("bool", bool, True),
        ("Tuple[dict, List[Literal[42, 99]]]", Tuple[dict, List[Literal[42, 99]]], True),
        # 3.10 union syntax
        pytest.param(
            "int | float",
            Union[int, float],
            True,
            marks=pytest.mark.skipif(sys.version_info < (3, 10), reason="syntax requires py3.10"),
        ),
    ],
)
def test_resolve_annotation(tp, expected, expected_cache) -> None:
    cache = {}
    result = utils.resolve_annotation(tp, globals(), locals(), cache)
    assert result == expected

    # check if state is what we expect
    assert bool(cache) == expected_cache
    # if it's a forward ref, resolve again and ensure cache is used
    if isinstance(tp, str):
        assert utils.resolve_annotation(tp, globals(), locals(), cache) is result


def test_resolve_annotation_literal() -> None:
    with pytest.raises(
        TypeError, match=r"Literal arguments must be of type str, int, bool, or NoneType."
    ):
        utils.resolve_annotation(Literal[timezone.utc, 3], globals(), locals(), {})  # type: ignore


@pytest.mark.skipif(sys.version_info < (3, 12), reason="syntax requires py3.12")
class TestResolveAnnotationTypeAliasType:
    def test_simple(self) -> None:
        # this is equivalent to `type CoolList = List[int]`
        CoolList = TypeAliasType("CoolList", List[int])
        assert utils.resolve_annotation(CoolList, globals(), locals(), {}) == List[int]

    def test_generic(self) -> None:
        # this is equivalent to `type CoolList[T] = List[T]; CoolList[int]`
        T = TypeVar("T")
        CoolList = TypeAliasType("CoolList", List[T], type_params=(T,))

        annotation = CoolList[int]
        assert utils.resolve_annotation(annotation, globals(), locals(), {}) == List[int]

    # alias and arg in local scope
    def test_forwardref_local(self) -> None:
        T = TypeVar("T")
        IntOrStr = Union[int, str]
        CoolList = TypeAliasType("CoolList", List[T], type_params=(T,))

        annotation = CoolList["IntOrStr"]
        assert utils.resolve_annotation(annotation, globals(), locals(), {}) == List[IntOrStr]

    # alias and arg in other module scope
    def test_forwardref_module(self) -> None:
        resolved = utils.resolve_annotation(
            utils_helper_module.ListWithForwardRefAlias, globals(), locals(), {}
        )
        assert resolved == List[Union[int, str]]

    # combination of the previous two, alias in other module scope and arg in local scope
    def test_forwardref_mixed(self) -> None:
        LocalIntOrStr = Union[int, str]

        annotation = utils_helper_module.GenericListAlias["LocalIntOrStr"]
        assert utils.resolve_annotation(annotation, globals(), locals(), {}) == List[LocalIntOrStr]

    # two different forwardrefs with same name
    def test_forwardref_duplicate(self) -> None:
        DuplicateAlias = int

        # first, resolve an annotation where `DuplicateAlias` resolves to the local int
        cache = {}
        assert (
            utils.resolve_annotation(List["DuplicateAlias"], globals(), locals(), cache)
            == List[int]
        )

        # then, resolve an annotation where the globalns changes and `DuplicateAlias` resolves to something else
        # (i.e. this should not resolve to `List[int]` despite {"DuplicateAlias": int} in the cache)
        assert (
            utils.resolve_annotation(
                utils_helper_module.ListWithDuplicateAlias, globals(), locals(), cache
            )
            == List[str]
        )


@pytest.mark.parametrize(
    ("dt", "style", "expected"),
    [
        (0, "F", "<t:0:F>"),
        (1630245000.1234, "T", "<t:1630245000:T>"),
        (datetime.datetime(2021, 8, 29, 13, 50, 0, tzinfo=timezone.utc), "f", "<t:1630245000:f>"),
    ],
)
def test_format_dt(dt, style, expected) -> None:
    assert utils.format_dt(dt, style) == expected


@pytest.fixture(scope="session")
def tmp_module_root(tmp_path_factory):
    # this obviously isn't great code, but it'll do just fine for tests
    tmpdir = tmp_path_factory.mktemp("module_root")
    for d in ["empty", "not_a_module", "mod/sub1/sub2"]:
        (tmpdir / d).mkdir(parents=True)
    for f in [
        "test.py",
        "not_a_module/abc.py",
        "mod/__init__.py",
        "mod/ext.py",
        "mod/sub1/sub2/__init__.py",
        "mod/sub1/sub2/abc.py",
    ]:
        (tmpdir / f).touch()
    return tmpdir


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (".", ["test", "mod.ext"]),
        ("./", ["test", "mod.ext"]),
        ("empty/", []),
    ],
)
def test_search_directory(tmp_module_root, path, expected) -> None:
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_module_root)

        # test relative and absolute paths
        for p in [path, os.path.abspath(path)]:
            assert sorted(utils.search_directory(p)) == sorted(expected)
    finally:
        os.chdir(orig_cwd)


@pytest.mark.parametrize(
    ("path", "exc"),
    [
        ("../../", r"Modules outside the cwd require a package to be specified"),
        ("nonexistent", r"Provided path '.*?nonexistent' does not exist"),
        ("test.py", r"Provided path '.*?test.py' is not a directory"),
    ],
)
def test_search_directory_exc(tmp_module_root, path, exc) -> None:
    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_module_root)

        with pytest.raises(ValueError, match=exc):
            list(utils.search_directory(tmp_module_root / path))
    finally:
        os.chdir(orig_cwd)


@pytest.mark.parametrize(
    ("locale", "expected"),
    [
        ("abc", None),
        ("en-US", "en-US"),
        ("en_US", "en-US"),
        ("de", "de"),
        ("de-DE", "de"),
        ("de_DE", "de"),
    ],
)
def test_as_valid_locale(locale, expected) -> None:
    assert utils.as_valid_locale(locale) == expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([], "<none>"),
        (["one"], "one"),
        (["one", "two"], "one plus two"),
        (["one", "two", "three"], "one, two, plus three"),
        (["one", "two", "three", "four"], "one, two, three, plus four"),
    ],
)
def test_humanize_list(values, expected) -> None:
    assert utils.humanize_list(values, "plus") == expected


# used for `test_signature_has_self_param`
def _toplevel():
    def inner() -> None: ...

    return inner


def decorator(f):
    @functools.wraps(f)
    def wrap(self, *args, **kwargs):
        return f(self, *args, **kwargs)

    return wrap


# used for `test_signature_has_self_param`
class _Clazz:
    def func(self):
        def inner() -> None: ...

        return inner

    @classmethod
    def cmethod(cls) -> None: ...

    @staticmethod
    def smethod() -> None: ...

    class Nested:
        def func(self):
            def inner() -> None: ...

            return inner

    rebind = _toplevel

    @decorator
    def decorated(self) -> None: ...

    _lambda = lambda: None


@pytest.mark.parametrize(
    ("function", "expected"),
    [
        # top-level function
        (_toplevel, False),
        # methods in class
        (_Clazz.func, True),
        (_Clazz().func, False),
        # unfortunately doesn't work
        (_Clazz.rebind, False),
        (_Clazz().rebind, False),
        # classmethod/staticmethod isn't supported, but checked to ensure consistency
        (_Clazz.cmethod, False),
        (_Clazz.smethod, True),
        # nested class methods
        (_Clazz.Nested.func, True),
        (_Clazz.Nested().func, False),
        # inner methods
        (_toplevel(), False),
        (_Clazz().func(), False),
        (_Clazz.Nested().func(), False),
        # decorated method
        (_Clazz.decorated, True),
        (_Clazz().decorated, False),
        # lambda (class-level)
        (_Clazz._lambda, False),
        (_Clazz()._lambda, False),
    ],
)
def test_signature_has_self_param(function, expected) -> None:
    assert utils.signature_has_self_param(function) == expected

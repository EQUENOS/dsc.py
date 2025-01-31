# SPDX-License-Identifier: MIT

from __future__ import annotations

import functools
import operator
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    Iterator,
    List,
    NoReturn,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from .enums import UserFlags
from .utils import MISSING, _generated

if TYPE_CHECKING:
    from typing_extensions import Self


__all__ = (
    "SystemChannelFlags",
    "MessageFlags",
    "PublicUserFlags",
    "Intents",
    "MemberCacheFlags",
    "ApplicationFlags",
    "ChannelFlags",
    "AutoModKeywordPresets",
    "MemberFlags",
    "RoleFlags",
    "AttachmentFlags",
    "SKUFlags",
    "ApplicationInstallTypes",
    "InteractionContextTypes",
    "EmbedFlags",
    "EmbedMediaFlags",
)

BF = TypeVar("BF", bound="BaseFlags")
T = TypeVar("T", bound="BaseFlags")


class flag_value(Generic[T]):
    def __init__(self, func: Callable[[Any], int]) -> None:
        self.flag = func(None)
        self.__doc__ = func.__doc__
        self._parent: Type[T] = MISSING

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, flag_value):
            return self.flag == other.flag
        if isinstance(other, BaseFlags):
            return self._parent is other.__class__ and self.flag == other.value
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __or__(self, other: Union[flag_value[T], T]) -> T:
        if isinstance(other, BaseFlags):
            if self._parent is not other.__class__:
                raise TypeError(
                    f"unsupported operand type(s) for |: flags of '{self._parent.__name__}' and flags of '{other.__class__.__name__}'"
                )
            return other._from_value(self.flag | other.value)
        if not isinstance(other, flag_value):
            raise TypeError(
                f"unsupported operand type(s) for |: flags of '{self._parent.__name__}' and {other.__class__}"
            )
        if self._parent is not other._parent:
            raise TypeError(
                f"unsupported operand type(s) for |: flags of '{self._parent.__name__}' and flags of '{other._parent.__name__}'"
            )
        return self._parent._from_value(self.flag | other.flag)

    def __invert__(self: flag_value[T]) -> T:
        return ~self._parent._from_value(self.flag)

    @overload
    def __get__(self, instance: None, owner: Type[BF]) -> flag_value[BF]: ...

    @overload
    def __get__(self, instance: BF, owner: Type[BF]) -> bool: ...

    def __get__(self, instance: Optional[BF], owner: Type[BF]) -> Any:
        if instance is None:
            return self
        return instance._has_flag(self.flag)

    def __set__(self, instance: BaseFlags, value: bool) -> None:
        instance._set_flag(self.flag, value)

    def __repr__(self) -> str:
        return f"<flag_value flag={self.flag!r}>"


class alias_flag_value(flag_value):
    pass


def all_flags_value(flags: Dict[str, int]) -> int:
    return functools.reduce(operator.or_, flags.values())


class BaseFlags:
    VALID_FLAGS: ClassVar[Dict[str, int]]
    DEFAULT_VALUE: ClassVar[int]

    value: int

    __slots__ = ("value",)

    def __init__(self, **kwargs: bool) -> None:
        self.value = self.DEFAULT_VALUE
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f"{key!r} is not a valid flag name.")
            setattr(self, key, value)

    @classmethod
    def __init_subclass__(cls, inverted: bool = False, no_fill_flags: bool = False):
        # add a way to bypass filling flags, eg for ListBaseFlags.
        if no_fill_flags:
            return cls

        # use the parent's current flags as a base if they exist
        cls.VALID_FLAGS = getattr(cls, "VALID_FLAGS", {}).copy()

        for name, value in cls.__dict__.items():
            if isinstance(value, flag_value):
                value._parent = cls
                cls.VALID_FLAGS[name] = value.flag

        if not cls.VALID_FLAGS:
            raise RuntimeError(
                "At least one flag must be defined in a BaseFlags subclass, or 'no_fill_flags' must be set to True"
            )

        cls.DEFAULT_VALUE = all_flags_value(cls.VALID_FLAGS) if inverted else 0

        return cls

    @classmethod
    def _from_value(cls, value: int) -> Self:
        self = cls.__new__(cls)
        self.value = value
        return self

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, self.__class__):
            return self.value == other.value
        if isinstance(other, flag_value):
            return self.__class__ is other._parent and self.value == other.flag
        return False

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __and__(self, other: Self) -> Self:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for &: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return self._from_value(self.value & other.value)

    def __iand__(self, other: Self) -> Self:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for &=: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        self.value &= other.value
        return self

    def __or__(self, other: Union[Self, flag_value[Self]]) -> Self:
        if isinstance(other, flag_value):
            if self.__class__ is not other._parent:
                raise TypeError(
                    f"unsupported operand type(s) for |: flags of '{self.__class__.__name__}' and flags of '{other._parent.__name__}'"
                )
            return self._from_value(self.value | other.flag)
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for |: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return self._from_value(self.value | other.value)

    def __ior__(self, other: Union[Self, flag_value[Self]]) -> Self:
        if isinstance(other, flag_value):
            if self.__class__ is not other._parent:
                raise TypeError(
                    f"unsupported operand type(s) for |=: flags of '{self.__class__.__name__}' and flags of '{other._parent.__name__}'"
                )
            self.value |= other.flag
            return self
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for |=: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        self.value |= other.value
        return self

    def __xor__(self, other: Union[Self, flag_value[Self]]) -> Self:
        if isinstance(other, flag_value):
            if self.__class__ is not other._parent:
                raise TypeError(
                    f"unsupported operand type(s) for ^: flags of '{self.__class__.__name__}' and flags of '{other._parent.__name__}'"
                )
            return self._from_value(self.value ^ other.flag)
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for ^: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return self._from_value(self.value ^ other.value)

    def __ixor__(self, other: Union[Self, flag_value[Self]]) -> Self:
        if isinstance(other, flag_value):
            if self.__class__ is not other._parent:
                raise TypeError(
                    f"unsupported operand type(s) for ^=: flags of '{self.__class__.__name__}' and flags of '{other._parent.__name__}'"
                )
            self.value ^= other.flag
            return self
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"unsupported operand type(s) for ^=: '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        self.value ^= other.value
        return self

    def __le__(self, other: Self) -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"'<=' not supported between instances of '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return (self.value & other.value) == self.value

    def __ge__(self, other: Self) -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"'>=' not supported between instances of '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return (self.value | other.value) == self.value

    def __lt__(self, other: Self) -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"'<' not supported between instances of '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return (self.value & other.value) == self.value and self.value != other.value

    def __gt__(self, other: Self) -> bool:
        if not isinstance(other, self.__class__):
            raise TypeError(
                f"'>' not supported between instances of '{self.__class__.__name__}' and '{other.__class__.__name__}'"
            )
        return (self.value | other.value) == self.value and self.value != other.value

    def __invert__(self) -> Self:
        # invert the bit but make sure all truthy values are valid flags
        # this code means that if a flag class doesn't define 1 << 2 that
        # value won't suddenly be set to True
        bitmask = all_flags_value(self.VALID_FLAGS)
        return self._from_value((self.value ^ bitmask) & bitmask)

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} value={self.value}>"

    def __iter__(self) -> Iterator[Tuple[str, bool]]:
        for name, value in self.__class__.__dict__.items():
            if isinstance(value, alias_flag_value):
                continue

            if isinstance(value, flag_value):
                yield (name, self._has_flag(value.flag))

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) == o

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value |= o
        elif toggle is False:
            self.value &= ~o
        else:
            raise TypeError(f"Value to set for {self.__class__.__name__} must be a bool.")


class ListBaseFlags(BaseFlags, no_fill_flags=True):
    """A base class for flags that aren't powers of 2.
    Instead, values are used as exponents to map to powers of 2 to avoid collisions,
    and only the combined value is stored, which allows all bitwise operations to work as expected.
    """

    __slots__ = ()

    @classmethod
    def _from_values(cls, values: Sequence[int]):
        self = cls.__new__(cls)
        value = 0
        for n in values:
            # protect against DoS with large shift values
            # n.b. performance overhead of this is negligible
            if not (0 <= n < 64):
                raise ValueError("Flag values must be within [0, 64)")
            value += 1 << n
        self.value = value
        return self

    @property
    def values(self) -> List[int]:
        # This essentially converts an int like `0b100110` into `[1, 2, 5]`,
        # i.e. the exponents of set bits in `self.value`.
        # This may look weird but interestingly it's by far the
        # fastest out of all benchmarked snippets, see https://stackoverflow.com/a/49592515/5080607
        # (this code is a derivative of one of them)
        return [i for i, c in enumerate(bin(self.value)[:1:-1]) if c == "1"]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} values={self.values}>"


class SystemChannelFlags(BaseFlags, inverted=True):
    """Wraps up a Discord system channel flag value.

    Similar to :class:`Permissions`\\, the properties provided are two way.
    You can set and retrieve individual bits using the properties as if they
    were regular bools. This allows you to edit the system flags easily.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.
    Arguments are applied in order, similar to :class:`Permissions`.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two SystemChannelFlags instances are equal.
        .. describe:: x != y

            Checks if two SystemChannelFlags instances are not equal.
        .. describe:: x <= y

            Checks if a SystemChannelFlags instance is a subset of another SystemChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if a SystemChannelFlags instance is a superset of another SystemChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if a SystemChannelFlags instance is a strict subset of another SystemChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if a SystemChannelFlags instance is a strict superset of another SystemChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new SystemChannelFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new SystemChannelFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new SystemChannelFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new SystemChannelFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.


        Additionally supported are a few operations on class attributes.

        .. describe:: SystemChannelFlags.y | SystemChannelFlags.z, SystemChannelFlags(y=True) | SystemChannelFlags.z

            Returns a SystemChannelFlags instance with all provided flags enabled.

        .. describe:: ~SystemChannelFlags.y

            Returns a SystemChannelFlags instance with all flags except ``y`` inverted from their default value.

    Attributes
    ----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            guild_reminder_notifications: bool = ...,
            join_notification_replies: bool = ...,
            join_notifications: bool = ...,
            premium_subscriptions: bool = ...,
            role_subscription_purchase_notification_replies: bool = ...,
            role_subscription_purchase_notifications: bool = ...,
        ) -> None: ...

    # For some reason the flags for system channels are "inverted"
    # ergo, if they're set then it means "suppress" (off in the GUI toggle)
    # Since this is counter-intuitive from an API perspective and annoying
    # these will be inverted automatically

    def _has_flag(self, o: int) -> bool:
        return (self.value & o) != o

    def _set_flag(self, o: int, toggle: bool) -> None:
        if toggle is True:
            self.value &= ~o
        elif toggle is False:
            self.value |= o
        else:
            raise TypeError("Value to set for SystemChannelFlags must be a bool.")

    @flag_value
    def join_notifications(self) -> int:
        """:class:`bool`: Returns ``True`` if the system channel is used for member join notifications."""
        return 1 << 0

    @flag_value
    def premium_subscriptions(self) -> int:
        """:class:`bool`: Returns ``True`` if the system channel is used for "Nitro boosting" notifications."""
        return 1 << 1

    @flag_value
    def guild_reminder_notifications(self) -> int:
        """:class:`bool`: Returns ``True`` if the system channel is used for server setup helpful tips notifications.

        .. versionadded:: 2.0
        """
        return 1 << 2

    @flag_value
    def join_notification_replies(self) -> int:
        """:class:`bool`: Returns ``True`` if the system channel shows sticker reply
        buttons for member join notifications.

        .. versionadded:: 2.3
        """
        return 1 << 3

    @flag_value
    def role_subscription_purchase_notifications(self):
        """:class:`bool`: Returns ``True`` if the system channel shows role
        subscription purchase/renewal notifications.

        .. versionadded:: 2.9
        """
        return 1 << 4

    @flag_value
    def role_subscription_purchase_notification_replies(self):
        """:class:`bool`: Returns ``True`` if the system channel shows sticker reply
        buttons for role subscription purchase/renewal notifications.

        .. versionadded:: 2.9
        """
        return 1 << 5


class MessageFlags(BaseFlags):
    """Wraps up a Discord Message flag value.

    See :class:`SystemChannelFlags`.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two MessageFlags instances are equal.
        .. describe:: x != y

            Checks if two MessageFlags instances are not equal.
        .. describe:: x <= y

            Checks if a MessageFlags instance is a subset of another MessageFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if a MessageFlags instance is a superset of another MessageFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if a MessageFlags instance is a strict subset of another MessageFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if a MessageFlags instance is a strict superset of another MessageFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new MessageFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new MessageFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new MessageFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new MessageFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.


        Additionally supported are a few operations on class attributes.

        .. describe:: MessageFlags.y | MessageFlags.z, MessageFlags(y=True) | MessageFlags.z

            Returns a MessageFlags instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~MessageFlags.y

            Returns a MessageFlags instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    .. versionadded:: 1.3

    Attributes
    ----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            crossposted: bool = ...,
            ephemeral: bool = ...,
            failed_to_mention_roles_in_thread: bool = ...,
            has_snapshot: bool = ...,
            has_thread: bool = ...,
            is_crossposted: bool = ...,
            is_voice_message: bool = ...,
            loading: bool = ...,
            source_message_deleted: bool = ...,
            suppress_embeds: bool = ...,
            suppress_notifications: bool = ...,
            urgent: bool = ...,
        ) -> None: ...

    @flag_value
    def crossposted(self):
        """:class:`bool`: Returns ``True`` if the message is the original crossposted message."""
        return 1 << 0

    @flag_value
    def is_crossposted(self):
        """:class:`bool`: Returns ``True`` if the message was crossposted from another channel."""
        return 1 << 1

    @flag_value
    def suppress_embeds(self):
        """:class:`bool`: Returns ``True`` if the message's embeds have been suppressed."""
        return 1 << 2

    @flag_value
    def source_message_deleted(self):
        """:class:`bool`: Returns ``True`` if the source message for this crosspost has been deleted."""
        return 1 << 3

    @flag_value
    def urgent(self):
        """:class:`bool`: Returns ``True`` if the message is an urgent message.

        An urgent message is one sent by Discord Trust and Safety.
        """
        return 1 << 4

    @flag_value
    def has_thread(self):
        """:class:`bool`: Returns ``True`` if the message is associated with a thread.

        .. versionadded:: 2.0
        """
        return 1 << 5

    @flag_value
    def ephemeral(self):
        """:class:`bool`: Returns ``True`` if the message is ephemeral.

        .. versionadded:: 2.0
        """
        return 1 << 6

    @flag_value
    def loading(self):
        """:class:`bool`: Returns ``True`` if the message is a deferred
        interaction response and shows a "thinking" state.

        .. versionadded:: 2.3
        """
        return 1 << 7

    @flag_value
    def failed_to_mention_roles_in_thread(self):
        """:class:`bool`: Returns ``True`` if the message failed to
        mention some roles and add their members to the thread.

        .. versionadded:: 2.4
        """
        return 1 << 8

    @flag_value
    def suppress_notifications(self):
        """:class:`bool`: Returns ``True`` if the message does not
        trigger push and desktop notifications.

        .. versionadded:: 2.9
        """
        return 1 << 12

    @flag_value
    def is_voice_message(self):
        """:class:`bool`: Returns ``True`` if the message is a voice message.

        Messages with this flag will have a single audio attachment, and no other content.

        .. versionadded:: 2.9
        """
        return 1 << 13

    @flag_value
    def has_snapshot(self):
        """:class:`bool`: Returns ``True`` if the message is a forward message.

        Messages with this flag will have only the forward data, and no other content.

        .. versionadded:: 2.10
        """
        return 1 << 14


class PublicUserFlags(BaseFlags):
    """Wraps up the Discord User Public flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two PublicUserFlags instances are equal.
        .. describe:: x != y

            Checks if two PublicUserFlags instances are not equal.
        .. describe:: x <= y

            Checks if a PublicUserFlags instance is a subset of another PublicUserFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if a PublicUserFlags instance is a superset of another PublicUserFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if a PublicUserFlags instance is a strict subset of another PublicUserFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if a PublicUserFlags instance is a strict superset of another PublicUserFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new PublicUserFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new PublicUserFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new PublicUserFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new PublicUserFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.


        Additionally supported are a few operations on class attributes.

        .. describe:: PublicUserFlags.y | PublicUserFlags.z, PublicUserFlags(y=True) | PublicUserFlags.z

            Returns a PublicUserFlags instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~PublicUserFlags.y

            Returns a PublicUserFlags instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    .. versionadded:: 1.4

    Attributes
    ----------
    value: :class:`int`
        The raw value. This value is a bit array field of a 53-bit integer
        representing the currently available flags. You should query
        flags via the properties rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            active_developer: bool = ...,
            bug_hunter: bool = ...,
            bug_hunter_level_2: bool = ...,
            discord_certified_moderator: bool = ...,
            early_supporter: bool = ...,
            early_verified_bot_developer: bool = ...,
            http_interactions_bot: bool = ...,
            hypesquad: bool = ...,
            hypesquad_balance: bool = ...,
            hypesquad_bravery: bool = ...,
            hypesquad_brilliance: bool = ...,
            moderator_programs_alumni: bool = ...,
            partner: bool = ...,
            spammer: bool = ...,
            staff: bool = ...,
            system: bool = ...,
            team_user: bool = ...,
            verified_bot: bool = ...,
            verified_bot_developer: bool = ...,
        ) -> None: ...

    @flag_value
    def staff(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Employee."""
        return UserFlags.staff.value

    @flag_value
    def partner(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Partner."""
        return UserFlags.partner.value

    @flag_value
    def hypesquad(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Events member."""
        return UserFlags.hypesquad.value

    @flag_value
    def bug_hunter(self):
        """:class:`bool`: Returns ``True`` if the user is a Bug Hunter"""
        return UserFlags.bug_hunter.value

    @flag_value
    def hypesquad_bravery(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Bravery member."""
        return UserFlags.hypesquad_bravery.value

    @flag_value
    def hypesquad_brilliance(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Brilliance member."""
        return UserFlags.hypesquad_brilliance.value

    @flag_value
    def hypesquad_balance(self):
        """:class:`bool`: Returns ``True`` if the user is a HypeSquad Balance member."""
        return UserFlags.hypesquad_balance.value

    @flag_value
    def early_supporter(self):
        """:class:`bool`: Returns ``True`` if the user is an Early Supporter."""
        return UserFlags.early_supporter.value

    @flag_value
    def team_user(self):
        """:class:`bool`: Returns ``True`` if the user is a Team User."""
        return UserFlags.team_user.value

    @flag_value
    def system(self):
        """:class:`bool`: Returns ``True`` if the user is a system user (i.e. represents Discord officially)."""
        return UserFlags.system.value

    @flag_value
    def bug_hunter_level_2(self):
        """:class:`bool`: Returns ``True`` if the user is a Bug Hunter Level 2"""
        return UserFlags.bug_hunter_level_2.value

    @flag_value
    def verified_bot(self):
        """:class:`bool`: Returns ``True`` if the user is a Verified Bot."""
        return UserFlags.verified_bot.value

    @flag_value
    def verified_bot_developer(self):
        """:class:`bool`: Returns ``True`` if the user is an Early Verified Bot Developer."""
        return UserFlags.verified_bot_developer.value

    @alias_flag_value
    def early_verified_bot_developer(self):
        """:class:`bool`: An alias for :attr:`verified_bot_developer`.

        .. versionadded:: 1.5
        """
        return UserFlags.verified_bot_developer.value

    @flag_value
    def moderator_programs_alumni(self):
        """:class:`bool`: Returns ``True`` if the user is a Discord Moderator Programs Alumni.

        .. versionadded:: 2.8
        """
        return UserFlags.discord_certified_moderator.value

    @alias_flag_value
    def discord_certified_moderator(self):
        """:class:`bool`: An alias for :attr:`moderator_programs_alumni`.

        .. versionadded:: 2.0
        """
        return UserFlags.discord_certified_moderator.value

    @flag_value
    def http_interactions_bot(self):
        """:class:`bool`: Returns ``True`` if the user is a bot that only uses HTTP interactions.

        .. versionadded:: 2.3
        """
        return UserFlags.http_interactions_bot.value

    @flag_value
    def spammer(self):
        """:class:`bool`: Returns ``True`` if the user is marked as a spammer.

        .. versionadded:: 2.3
        """
        return UserFlags.spammer.value

    @flag_value
    def active_developer(self):
        """:class:`bool`: Returns ``True`` if the user is an Active Developer.

        .. versionadded:: 2.8
        """
        return UserFlags.active_developer.value

    def all(self) -> List[UserFlags]:
        """List[:class:`UserFlags`]: Returns all public flags the user has."""
        return [public_flag for public_flag in UserFlags if self._has_flag(public_flag.value)]


class Intents(BaseFlags):
    """Wraps up a Discord gateway intent flag.

    Similar to :class:`Permissions`\\, the properties provided are two way.
    You can set and retrieve individual bits using the properties as if they
    were regular bools.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.
    Arguments are applied in order, similar to :class:`Permissions`.

    This is used to disable certain gateway features that are unnecessary to
    run your bot. To make use of this, it is passed to the ``intents`` keyword
    argument of :class:`Client`.

    .. versionadded:: 1.5

    .. collapse:: operations

        .. describe:: x == y

            Checks if two Intents instances are equal.
        .. describe:: x != y

            Checks if two Intents instances are not equal.
        .. describe:: x <= y

            Checks if an Intents instance is a subset of another Intents instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if an Intents instance is a superset of another Intents instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if an Intents instance is a strict subset of another Intents instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if an Intents instance is a strict superset of another Intents instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new Intents instance with all enabled intents from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new Intents instance with only intents enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new Intents instance with only intents enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new Intents instance with all intents inverted from x.

            .. versionadded:: 2.6
        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.


        Additionally supported are a few operations on class attributes.

        .. describe:: Intents.y | Intents.z, Intents(y=True) | Intents.z

            Returns an Intents instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~Intents.y

            Returns an Intents instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.

        .. versionchanged:: 2.6

            This can be now be provided on initialisation.
    """

    __slots__ = ()

    @overload
    @_generated
    def __init__(
        self,
        value: Optional[int] = None,
        *,
        automod: bool = ...,
        automod_configuration: bool = ...,
        automod_execution: bool = ...,
        bans: bool = ...,
        dm_messages: bool = ...,
        dm_polls: bool = ...,
        dm_reactions: bool = ...,
        dm_typing: bool = ...,
        emojis: bool = ...,
        emojis_and_stickers: bool = ...,
        expressions: bool = ...,
        guild_messages: bool = ...,
        guild_polls: bool = ...,
        guild_reactions: bool = ...,
        guild_scheduled_events: bool = ...,
        guild_typing: bool = ...,
        guilds: bool = ...,
        integrations: bool = ...,
        invites: bool = ...,
        members: bool = ...,
        message_content: bool = ...,
        messages: bool = ...,
        moderation: bool = ...,
        polls: bool = ...,
        presences: bool = ...,
        reactions: bool = ...,
        typing: bool = ...,
        voice_states: bool = ...,
        webhooks: bool = ...,
    ) -> None: ...

    @overload
    @_generated
    def __init__(self: NoReturn) -> None: ...

    def __init__(self, value: Optional[int] = None, **kwargs: bool) -> None:
        if value is not None:
            if not isinstance(value, int):
                raise TypeError(
                    f"Expected int, received {type(value).__name__} for argument 'value'."
                )
            if value < 0:
                raise ValueError("Expected a non-negative value.")
            self.value = value
        else:
            self.value = self.DEFAULT_VALUE
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f"{key!r} is not a valid flag name.")
            setattr(self, key, value)

    @classmethod
    def all(cls) -> Self:
        """A factory method that creates an :class:`Intents` instance with everything enabled."""
        self = cls.__new__(cls)
        self.value = all_flags_value(cls.VALID_FLAGS)
        return self

    @classmethod
    def none(cls) -> Self:
        """A factory method that creates an :class:`Intents` instance with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @classmethod
    def default(cls) -> Self:
        """A factory method that creates an :class:`Intents` instance with everything enabled
        except :attr:`presences`, :attr:`members`, and :attr:`message_content`.
        """
        self = cls.all()
        self.presences = False
        self.members = False
        self.message_content = False
        return self

    @flag_value
    def guilds(self):
        """:class:`bool`: Whether guild related events are enabled.

        This corresponds to the following events:

        - :func:`on_guild_join`
        - :func:`on_guild_remove`
        - :func:`on_guild_available`
        - :func:`on_guild_unavailable`
        - :func:`on_guild_channel_update`
        - :func:`on_guild_channel_create`
        - :func:`on_guild_channel_delete`
        - :func:`on_guild_channel_pins_update`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Client.guilds`
        - :class:`Guild` and all its attributes.
        - :meth:`Client.get_channel`
        - :meth:`Client.get_all_channels`

        It is highly advisable to leave this intent enabled for your bot to function.
        """
        return 1 << 0

    @flag_value
    def members(self):
        """:class:`bool`: Whether guild member related events are enabled.

        This corresponds to the following events:

        - :func:`on_member_join`
        - :func:`on_member_remove`
        - :func:`on_member_update`
        - :func:`on_user_update`
        - :func:`on_guild_scheduled_event_subscribe`
        - :func:`on_guild_scheduled_event_unsubscribe`

        This also corresponds to the following attributes and classes in terms of cache:

        - :meth:`Client.get_all_members`
        - :meth:`Client.get_user`
        - :meth:`Guild.chunk`
        - :meth:`Guild.fetch_members`
        - :meth:`Guild.get_member`
        - :attr:`Guild.members`
        - :attr:`Member.roles`
        - :attr:`Member.nick`
        - :attr:`Member.premium_since`
        - :attr:`User.name`
        - :attr:`User.avatar`
        - :attr:`User.discriminator`
        - :attr:`User.global_name`

        For more information go to the :ref:`member intent documentation <need_members_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.
        """
        return 1 << 1

    @flag_value
    def moderation(self):
        """:class:`bool`: Whether guild moderation related events are enabled.

        This corresponds to the following events:

        - :func:`on_member_ban`
        - :func:`on_member_unban`
        - :func:`on_audit_log_entry_create`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 2

    @alias_flag_value
    def bans(self):
        """:class:`bool`: Alias of :attr:`.moderation`.

        .. versionchanged:: 2.8
            Changed to an alias.
        """
        return 1 << 2

    @flag_value
    def expressions(self):
        """:class:`bool`: Whether events related to guild emojis, stickers, and
        soundboard sounds are enabled.

        .. versionadded:: 2.10

        This corresponds to the following events:

        - :func:`on_guild_emojis_update`
        - :func:`on_guild_stickers_update`
        - :func:`on_guild_soundboard_sounds_update`

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Emoji`
        - :class:`GuildSticker`
        - :class:`GuildSoundboardSound`
        - :meth:`Client.get_emoji`
        - :meth:`Client.get_sticker`
        - :meth:`Client.get_soundboard_sound`
        - :meth:`Client.emojis`
        - :meth:`Client.stickers`
        - :meth:`Client.soundboard_sounds`
        - :attr:`Guild.emojis`
        - :attr:`Guild.stickers`
        - :attr:`Guild.soundboard_sounds`
        """
        return 1 << 3

    @alias_flag_value
    def emojis_and_stickers(self):
        """:class:`bool`: Alias of :attr:`.expressions`.

        .. versionadded:: 2.0

        .. versionchanged:: 2.10
            Changed to an alias.
        """
        return 1 << 3

    @alias_flag_value
    def emojis(self):
        """:class:`bool`: Alias of :attr:`.expressions`.

        .. versionchanged:: 2.0
            Changed to an alias.
        """
        return 1 << 3

    @flag_value
    def integrations(self):
        """:class:`bool`: Whether guild integration related events are enabled.

        This corresponds to the following events:

        - :func:`on_guild_integrations_update`
        - :func:`on_integration_create`
        - :func:`on_integration_update`
        - :func:`on_raw_integration_delete`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 4

    @flag_value
    def webhooks(self):
        """:class:`bool`: Whether guild webhook related events are enabled.

        This corresponds to the following events:

        - :func:`on_webhooks_update`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 5

    @flag_value
    def invites(self):
        """:class:`bool`: Whether guild invite related events are enabled.

        This corresponds to the following events:

        - :func:`on_invite_create`
        - :func:`on_invite_delete`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 6

    @flag_value
    def voice_states(self):
        """:class:`bool`: Whether guild voice state related events are enabled.

        This corresponds to the following events:

        - :func:`on_voice_state_update`
        - :func:`on_voice_channel_effect`
        - :func:`on_raw_voice_channel_effect`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`VoiceChannel.members`
        - :attr:`VoiceChannel.voice_states`
        - :attr:`Member.voice`

        .. note::

            This intent is required to connect to voice.
        """
        return 1 << 7

    @flag_value
    def presences(self):
        """:class:`bool`: Whether guild presence related events are enabled.

        This corresponds to the following events:

        - :func:`on_presence_update`
        - :func:`on_raw_presence_update`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Member.activities`
        - :attr:`Member.status`
        - :attr:`Member.raw_status`

        For more information go to the :ref:`presence intent documentation <need_presence_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.
        """
        return 1 << 8

    @alias_flag_value
    def messages(self):
        """:class:`bool`: Whether guild and direct message related events are enabled.

        This is a shortcut to set or get both :attr:`guild_messages` and :attr:`dm_messages`.

        This corresponds to the following events:

        - :func:`on_message` (both guilds and DMs)
        - :func:`on_message_edit` (both guilds and DMs)
        - :func:`on_message_delete` (both guilds and DMs)
        - :func:`on_raw_message_delete` (both guilds and DMs)
        - :func:`on_raw_message_edit` (both guilds and DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages`

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (both guilds and DMs)
        - :func:`on_reaction_remove` (both guilds and DMs)
        - :func:`on_reaction_clear` (both guilds and DMs)

        .. note::

            :attr:`.Intents.message_content` is required to receive the content of messages.
        """
        return (1 << 9) | (1 << 12)

    @flag_value
    def guild_messages(self):
        """:class:`bool`: Whether guild message related events are enabled.

        See also :attr:`dm_messages` for DMs or :attr:`messages` for both.

        This corresponds to the following events:

        - :func:`on_message` (only for guilds)
        - :func:`on_message_edit` (only for guilds)
        - :func:`on_message_delete` (only for guilds)
        - :func:`on_raw_message_delete` (only for guilds)
        - :func:`on_raw_message_edit` (only for guilds)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages` (only for guilds)

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (only for guilds)
        - :func:`on_reaction_remove` (only for guilds)
        - :func:`on_reaction_clear` (only for guilds)
        """
        return 1 << 9

    @flag_value
    def dm_messages(self):
        """:class:`bool`: Whether direct message related events are enabled.

        See also :attr:`guild_messages` for guilds or :attr:`messages` for both.

        This corresponds to the following events:

        - :func:`on_message` (only for DMs)
        - :func:`on_message_edit` (only for DMs)
        - :func:`on_message_delete` (only for DMs)
        - :func:`on_raw_message_delete` (only for DMs)
        - :func:`on_raw_message_edit` (only for DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :class:`Message`
        - :attr:`Client.cached_messages` (only for DMs)

        Note that due to an implicit relationship this also corresponds to the following events:

        - :func:`on_reaction_add` (only for DMs)
        - :func:`on_reaction_remove` (only for DMs)
        - :func:`on_reaction_clear` (only for DMs)
        """
        return 1 << 12

    @flag_value
    def message_content(self):
        """:class:`bool`: Whether messages will have access to message content.

        .. versionadded:: 2.5

        This applies to the following fields on :class:`~disnake.Message` instances:

        - :attr:`~disnake.Message.content`
        - :attr:`~disnake.Message.embeds`
        - :attr:`~disnake.Message.attachments`
        - :attr:`~disnake.Message.components`

        The following cases will always have the above fields:

        - Messages the bot sends
        - Messages the bot receives as a direct message
        - Messages in which the bot is mentioned
        - Messages received from an interaction payload, these will typically be attributes on :class:`~disnake.MessageInteraction` instances.

        In addition, this also corresponds to the following fields:

        - :attr:`AutoModActionExecution.content`
        - :attr:`AutoModActionExecution.matched_content`

        For more information go to the :ref:`message content intent documentation <need_message_content_intent>`.

        .. note::

            Currently, this requires opting in explicitly via the developer portal as well.
            Bots in over 100 guilds will need to apply to Discord for verification.
        """
        return 1 << 15

    @alias_flag_value
    def reactions(self):
        """:class:`bool`: Whether guild and direct message reaction related events are enabled.

        This is a shortcut to set or get both :attr:`guild_reactions` and :attr:`dm_reactions`.

        This corresponds to the following events:

        - :func:`on_reaction_add` (both guilds and DMs)
        - :func:`on_reaction_remove` (both guilds and DMs)
        - :func:`on_reaction_clear` (both guilds and DMs)
        - :func:`on_raw_reaction_add` (both guilds and DMs)
        - :func:`on_raw_reaction_remove` (both guilds and DMs)
        - :func:`on_raw_reaction_clear` (both guilds and DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (both guild and DM messages)
        """
        return (1 << 10) | (1 << 13)

    @flag_value
    def guild_reactions(self):
        """:class:`bool`: Whether guild reaction related events are enabled.

        See also :attr:`dm_reactions` for DMs or :attr:`reactions` for both.

        This corresponds to the following events:

        - :func:`on_reaction_add` (only for guilds)
        - :func:`on_reaction_remove` (only for guilds)
        - :func:`on_reaction_clear` (only for guilds)
        - :func:`on_raw_reaction_add` (only for guilds)
        - :func:`on_raw_reaction_remove` (only for guilds)
        - :func:`on_raw_reaction_clear` (only for guilds)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (only for guild messages)
        """
        return 1 << 10

    @flag_value
    def dm_reactions(self):
        """:class:`bool`: Whether direct message reaction related events are enabled.

        See also :attr:`guild_reactions` for guilds or :attr:`reactions` for both.

        This corresponds to the following events:

        - :func:`on_reaction_add` (only for DMs)
        - :func:`on_reaction_remove` (only for DMs)
        - :func:`on_reaction_clear` (only for DMs)
        - :func:`on_raw_reaction_add` (only for DMs)
        - :func:`on_raw_reaction_remove` (only for DMs)
        - :func:`on_raw_reaction_clear` (only for DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.reactions` (only for DM messages)
        """
        return 1 << 13

    @alias_flag_value
    def typing(self):
        """:class:`bool`: Whether guild and direct message typing related events are enabled.

        This is a shortcut to set or get both :attr:`guild_typing` and :attr:`dm_typing`.

        This corresponds to the following events:

        - :func:`on_typing` (both guilds and DMs)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return (1 << 11) | (1 << 14)

    @flag_value
    def guild_typing(self):
        """:class:`bool`: Whether guild typing related events are enabled.

        See also :attr:`dm_typing` for DMs or :attr:`typing` for both.

        This corresponds to the following events:

        - :func:`on_typing` (only for guilds)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 11

    @flag_value
    def dm_typing(self):
        """:class:`bool`: Whether direct message typing related events are enabled.

        See also :attr:`guild_typing` for guilds or :attr:`typing` for both.

        This corresponds to the following events:

        - :func:`on_typing` (only for DMs)

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 14

    @flag_value
    def guild_scheduled_events(self):
        """:class:`bool`: Whether guild scheduled event related events are enabled.

        .. versionadded:: 2.3

        This corresponds to the following events:

        - :func:`on_guild_scheduled_event_create`
        - :func:`on_guild_scheduled_event_delete`
        - :func:`on_guild_scheduled_event_update`
        - :func:`on_guild_scheduled_event_subscribe`
        - :func:`on_guild_scheduled_event_unsubscribe`
        - :func:`on_raw_guild_scheduled_event_subscribe`
        - :func:`on_raw_guild_scheduled_event_unsubscribe`

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Guild.scheduled_events`
        - :meth:`Guild.get_scheduled_event`
        - :attr:`StageInstance.guild_scheduled_event`
        """
        return 1 << 16

    @flag_value
    def automod_configuration(self):
        """:class:`bool`: Whether auto moderation configuration related events are enabled.

        .. versionadded:: 2.6

        This corresponds to the following events:

        - :func:`on_automod_rule_create`
        - :func:`on_automod_rule_delete`
        - :func:`on_automod_rule_update`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 20

    @flag_value
    def automod_execution(self):
        """:class:`bool`: Whether auto moderation execution related events are enabled.

        .. versionadded:: 2.6

        This corresponds to the following events:

        - :func:`on_automod_action_execution`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return 1 << 21

    @alias_flag_value
    def automod(self):
        """:class:`bool`: Whether auto moderation related events are enabled.

        .. versionadded:: 2.6

        This is a shortcut to set or get both :attr:`automod_configuration` and :attr:`automod_execution`.

        This corresponds to the following events:

        - :func:`on_automod_rule_create`
        - :func:`on_automod_rule_delete`
        - :func:`on_automod_rule_update`
        - :func:`on_automod_action_execution`

        This does not correspond to any attributes or classes in the library in terms of cache.
        """
        return (1 << 20) | (1 << 21)

    @alias_flag_value
    def polls(self):
        """:class:`bool`: Whether guild and direct message polls related events are enabled.

        This is a shortcut to set or get both :attr:`guild_polls` and :attr:`dm_polls`.

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (both guilds and DMs)
        - :func:`on_poll_vote_remove` (both guilds and DMs)
        - :func:`on_raw_poll_vote_add` (both guilds and DMs)
        - :func:`on_raw_poll_vote_remove` (both guilds and DMs)
        """
        return (1 << 24) | (1 << 25)

    @flag_value
    def guild_polls(self):
        """:class:`bool`: Whether guild polls related events are enabled.

        .. versionadded:: 2.10

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (only for guilds)
        - :func:`on_poll_vote_remove` (only for guilds)
        - :func:`on_raw_poll_vote_add` (only for guilds)
        - :func:`on_raw_poll_vote_remove` (only for guilds)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.poll` (only for guild messages)
        - :class:`Poll` and all its attributes.
        """
        return 1 << 24

    @flag_value
    def dm_polls(self):
        """:class:`bool`: Whether direct message polls related events are enabled.

        .. versionadded:: 2.10

        This corresponds to the following events:

        - :func:`on_poll_vote_add` (only for DMs)
        - :func:`on_poll_vote_remove` (only for DMs)
        - :func:`on_raw_poll_vote_add` (only for DMs)
        - :func:`on_raw_poll_vote_remove` (only for DMs)

        This also corresponds to the following attributes and classes in terms of cache:

        - :attr:`Message.poll` (only for DM messages)
        - :class:`Poll` and all its attributes.
        """
        return 1 << 25


class MemberCacheFlags(BaseFlags):
    """Controls the library's cache policy when it comes to members.

    This allows for finer grained control over what members are cached.
    Note that the bot's own member is always cached. This class is passed
    to the ``member_cache_flags`` parameter in :class:`Client`.

    Due to a quirk in how Discord works, in order to ensure proper cleanup
    of cache resources it is recommended to have :attr:`Intents.members`
    enabled. Otherwise the library cannot know when a member leaves a guild and
    is thus unable to cleanup after itself.

    To construct an object you can pass keyword arguments denoting the flags
    to enable or disable.
    Arguments are applied in order, similar to :class:`Permissions`.

    The default value is all flags enabled.

    .. versionadded:: 1.5

    .. collapse:: operations

        .. describe:: x == y

            Checks if two MemberCacheFlags instances are equal.
        .. describe:: x != y

            Checks if two MemberCacheFlags instances are not equal.
        .. describe:: x <= y

            Checks if a MemberCacheFlags instance is a subset of another MemberCacheFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if a MemberCacheFlags instance is a superset of another MemberCacheFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if a MemberCacheFlags instance is a strict subset of another MemberCacheFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if a MemberCacheFlags instance is a strict superset of another MemberCacheFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new MemberCacheFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new MemberCacheFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new MemberCacheFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new MemberCacheFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

               Return the flag's hash.
        .. describe:: iter(x)

               Returns an iterator of ``(name, value)`` pairs. This allows it
               to be, for example, constructed as a dict or a list of pairs.


        Additionally supported are a few operations on class attributes.

        .. describe:: MemberCacheFlags.y | MemberCacheFlags.z, MemberCacheFlags(y=True) | MemberCacheFlags.z

            Returns a MemberCacheFlags instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~MemberCacheFlags.y

            Returns a MemberCacheFlags instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    @overload
    @_generated
    def __init__(self, *, joined: bool = ..., voice: bool = ...) -> None: ...

    @overload
    @_generated
    def __init__(self: NoReturn) -> None: ...

    def __init__(self, **kwargs: bool) -> None:
        self.value = all_flags_value(self.VALID_FLAGS)
        for key, value in kwargs.items():
            if key not in self.VALID_FLAGS:
                raise TypeError(f"{key!r} is not a valid flag name.")
            setattr(self, key, value)

    @classmethod
    def all(cls) -> Self:
        """A factory method that creates a :class:`MemberCacheFlags` instance with everything enabled."""
        self = cls.__new__(cls)
        self.value = all_flags_value(cls.VALID_FLAGS)
        return self

    @classmethod
    def none(cls) -> Self:
        """A factory method that creates a :class:`MemberCacheFlags` instance with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @property
    def _empty(self):
        return self.value == self.DEFAULT_VALUE

    @flag_value
    def voice(self) -> int:
        """:class:`bool`: Whether to cache members that are in voice.

        This requires :attr:`Intents.voice_states`.

        Members that leave voice are no longer cached.
        """
        return 1

    @flag_value
    def joined(self) -> int:
        """:class:`bool`: Whether to cache members that joined the guild
        or are chunked as part of the initial log in flow.

        This requires :attr:`Intents.members`.

        Members that leave the guild are no longer cached.
        """
        return 2

    @classmethod
    def from_intents(cls, intents: Intents) -> Self:
        """A factory method that creates a :class:`MemberCacheFlags` instance based on
        the currently selected :class:`Intents`.

        Parameters
        ----------
        intents: :class:`Intents`
            The intents to select from.

        Returns
        -------
        :class:`MemberCacheFlags`
            The resulting member cache flags.
        """
        self = cls.none()
        if intents.members:
            self.joined = True
        if intents.voice_states:
            self.voice = True

        return self

    def _verify_intents(self, intents: Intents) -> None:
        if self.voice and not intents.voice_states:
            raise ValueError("MemberCacheFlags.voice requires Intents.voice_states")

        if self.joined and not intents.members:
            raise ValueError("MemberCacheFlags.joined requires Intents.members")

    @property
    def _voice_only(self):
        return self.value == 1


class ApplicationFlags(BaseFlags):
    """Wraps up the Discord Application flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two ApplicationFlags instances are equal.
        .. describe:: x != y

            Checks if two ApplicationFlags instances are not equal.
        .. describe:: x <= y

            Checks if an ApplicationFlags instance is a subset of another ApplicationFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if an ApplicationFlags instance is a superset of another ApplicationFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if an ApplicationFlags instance is a strict subset of another ApplicationFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if an ApplicationFlags instance is a strict superset of another ApplicationFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new ApplicationFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new ApplicationFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new ApplicationFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new ApplicationFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.


        Additionally supported are a few operations on class attributes.

        .. describe:: ApplicationFlags.y | ApplicationFlags.z, ApplicationFlags(y=True) | ApplicationFlags.z

            Returns an ApplicationFlags instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~ApplicationFlags.y

            Returns an ApplicationFlags instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    .. versionadded:: 2.0

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            application_auto_moderation_rule_create_badge: bool = ...,
            application_command_badge: bool = ...,
            embedded: bool = ...,
            gateway_guild_members: bool = ...,
            gateway_guild_members_limited: bool = ...,
            gateway_message_content: bool = ...,
            gateway_message_content_limited: bool = ...,
            gateway_presence: bool = ...,
            gateway_presence_limited: bool = ...,
            verification_pending_guild_limit: bool = ...,
        ) -> None: ...

    @flag_value
    def application_auto_moderation_rule_create_badge(self):
        """:class:`bool`: Returns ``True`` if the application uses the Auto Moderation API."""
        return 1 << 6

    @flag_value
    def gateway_presence(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive presence information over the gateway.
        """
        return 1 << 12

    @flag_value
    def gateway_presence_limited(self):
        """:class:`bool`: Returns ``True`` if the application is allowed to receive limited
        presence information over the gateway.
        """
        return 1 << 13

    @flag_value
    def gateway_guild_members(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive guild members information over the gateway.
        """
        return 1 << 14

    @flag_value
    def gateway_guild_members_limited(self):
        """:class:`bool`: Returns ``True`` if the application is allowed to receive limited
        guild members information over the gateway.
        """
        return 1 << 15

    @flag_value
    def verification_pending_guild_limit(self):
        """:class:`bool`: Returns ``True`` if the application is currently pending verification
        and has hit the guild limit.
        """
        return 1 << 16

    @flag_value
    def embedded(self):
        """:class:`bool`: Returns ``True`` if the application is embedded within the Discord client."""
        return 1 << 17

    @flag_value
    def gateway_message_content(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive message content over the gateway.
        """
        return 1 << 18

    @flag_value
    def gateway_message_content_limited(self):
        """:class:`bool`: Returns ``True`` if the application is verified and is allowed to
        receive limited message content over the gateway.
        """
        return 1 << 19

    @flag_value
    def application_command_badge(self):
        """:class:`bool`: Returns ``True`` if the application has registered global application commands.

        .. versionadded:: 2.6
        """
        return 1 << 23


class ChannelFlags(BaseFlags):
    """Wraps up the Discord Channel flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two ChannelFlags instances are equal.
        .. describe:: x != y

            Checks if two ChannelFlags instances are not equal.
        .. describe:: x <= y

            Checks if a ChannelFlags instance is a subset of another ChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x >= y

            Checks if a ChannelFlags instance is a superset of another ChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x < y

            Checks if a ChannelFlags instance is a strict subset of another ChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x > y

            Checks if a ChannelFlags instance is a strict superset of another ChannelFlags instance.

            .. versionadded:: 2.6
        .. describe:: x | y, x |= y

            Returns a new ChannelFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x & y, x &= y

            Returns a new ChannelFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: x ^ y, x ^= y

            Returns a new ChannelFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).

            .. versionadded:: 2.6
        .. describe:: ~x

            Returns a new ChannelFlags instance with all flags from x inverted.

            .. versionadded:: 2.6
        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.


        Additionally supported are a few operations on class attributes.

        .. describe:: ChannelFlags.y | ChannelFlags.z, ChannelFlags(y=True) | ChannelFlags.z

            Returns a ChannelFlags instance with all provided flags enabled.

            .. versionadded:: 2.6
        .. describe:: ~ChannelFlags.y

            Returns a ChannelFlags instance with all flags except ``y`` inverted from their default value.

            .. versionadded:: 2.6

    .. versionadded:: 2.5

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            hide_media_download_options: bool = ...,
            pinned: bool = ...,
            require_tag: bool = ...,
        ) -> None: ...

    @flag_value
    def pinned(self):
        """:class:`bool`: Returns ``True`` if the thread is pinned.

        This only applies to threads that are part of a :class:`ForumChannel` or :class:`MediaChannel`.
        """
        return 1 << 1

    @flag_value
    def require_tag(self):
        """:class:`bool`: Returns ``True`` if the channel requires all newly created threads to have a tag.

        This only applies to channels of types :class:`ForumChannel` or :class:`MediaChannel`.

        .. versionadded:: 2.6
        """
        return 1 << 4

    @flag_value
    def hide_media_download_options(self):
        """:class:`bool`: Returns ``True`` if the channel hides the embedded media download options.

        This only applies to channels of type :class:`MediaChannel`.

        .. versionadded:: 2.10
        """
        return 1 << 15


class AutoModKeywordPresets(ListBaseFlags):
    """Wraps up the pre-defined auto moderation keyword lists, provided by Discord.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two AutoModKeywordPresets instances are equal.
        .. describe:: x != y

            Checks if two AutoModKeywordPresets instances are not equal.
        .. describe:: x <= y

            Checks if an AutoModKeywordPresets instance is a subset of another AutoModKeywordPresets instance.
        .. describe:: x >= y

            Checks if an AutoModKeywordPresets instance is a superset of another AutoModKeywordPresets instance.
        .. describe:: x < y

            Checks if an AutoModKeywordPresets instance is a strict subset of another AutoModKeywordPresets instance.
        .. describe:: x > y

            Checks if an AutoModKeywordPresets instance is a strict superset of another AutoModKeywordPresets instance.
        .. describe:: x | y, x |= y

            Returns a new AutoModKeywordPresets instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new AutoModKeywordPresets instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new AutoModKeywordPresets instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new AutoModKeywordPresets instance with all flags from x inverted.
        .. describe:: hash(x)

            Return the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.


        Additionally supported are a few operations on class attributes.

        .. describe:: AutoModKeywordPresets.y | AutoModKeywordPresets.z, AutoModKeywordPresets(y=True) | AutoModKeywordPresets.z

            Returns an AutoModKeywordPresets instance with all provided flags enabled.

        .. describe:: ~AutoModKeywordPresets.y

            Returns an AutoModKeywordPresets instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.6

    Attributes
    ----------
    values: :class:`int`
        The raw values. You should query flags via the properties
        rather than using these raw values.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self, *, profanity: bool = ..., sexual_content: bool = ..., slurs: bool = ...
        ) -> None: ...

    @classmethod
    def all(cls) -> Self:
        """A factory method that creates an :class:`AutoModKeywordPresets` instance with everything enabled."""
        self = cls.__new__(cls)
        self.value = all_flags_value(cls.VALID_FLAGS)
        return self

    @classmethod
    def none(cls) -> Self:
        """A factory method that creates an :class:`AutoModKeywordPresets` instance with everything disabled."""
        self = cls.__new__(cls)
        self.value = self.DEFAULT_VALUE
        return self

    @flag_value
    def profanity(self):
        """:class:`bool`: Returns ``True`` if the profanity preset is enabled
        (contains words that may be considered swearing or cursing).
        """
        return 1 << 1

    @flag_value
    def sexual_content(self):
        """:class:`bool`: Returns ``True`` if the sexual content preset is enabled
        (contains sexually explicit words).
        """
        return 1 << 2

    @flag_value
    def slurs(self):
        """:class:`bool`: Returns ``True`` if the slurs preset is enabled
        (contains insults or words that may be considered hate speech).
        """
        return 1 << 3


class MemberFlags(BaseFlags):
    """Wraps up Discord Member flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two MemberFlags instances are equal.
        .. describe:: x != y

            Checks if two MemberFlags instances are not equal.
        .. describe:: x <= y

            Checks if a MemberFlags instance is a subset of another MemberFlags instance.
        .. describe:: x >= y

            Checks if a MemberFlags instance is a superset of another MemberFlags instance.
        .. describe:: x < y

            Checks if a MemberFlags instance is a strict subset of another MemberFlags instance.
        .. describe:: x > y

            Checks if a MemberFlags instance is a strict superset of another MemberFlags instance.
        .. describe:: x | y, x |= y

            Returns a new MemberFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new MemberFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new MemberFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new MemberFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: MemberFlags.y | MemberFlags.z, MemberFlags(y=True) | MemberFlags.z

            Returns a MemberFlags instance with all provided flags enabled.

        .. describe:: ~MemberFlags.y

            Returns a MemberFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.8

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            automod_quarantined_username: bool = ...,
            bypasses_verification: bool = ...,
            completed_home_actions: bool = ...,
            completed_onboarding: bool = ...,
            did_rejoin: bool = ...,
            dm_settings_upsell_acknowledged: bool = ...,
            is_guest: bool = ...,
            started_home_actions: bool = ...,
            started_onboarding: bool = ...,
        ) -> None: ...

    @flag_value
    def did_rejoin(self):
        """:class:`bool`: Returns ``True`` if the member has left and rejoined the guild."""
        return 1 << 0

    @flag_value
    def completed_onboarding(self):
        """:class:`bool`: Returns ``True`` if the member has completed onboarding."""
        return 1 << 1

    @flag_value
    def bypasses_verification(self):
        """:class:`bool`: Returns ``True`` if the member is able to bypass guild verification requirements."""
        return 1 << 2

    @flag_value
    def started_onboarding(self):
        """:class:`bool`: Returns ``True`` if the member has started onboarding."""
        return 1 << 3

    @flag_value
    def is_guest(self):
        """:class:`bool`: Returns ``True`` if the member is a guest and can only access the voice channel they were invited to.

        .. versionadded:: 2.10
        """
        return 1 << 4

    @flag_value
    def started_home_actions(self):
        """:class:`bool`: Returns ``True`` if the member has started the Server Guide actions.

        .. versionadded:: 2.10
        """
        return 1 << 5

    @flag_value
    def completed_home_actions(self):
        """:class:`bool`: Returns ``True`` if the member has completed the Server Guide actions.

        .. versionadded:: 2.10
        """
        return 1 << 6

    @flag_value
    def automod_quarantined_username(self):
        """:class:`bool`: Returns ``True`` if the member's username, display name, or nickname is blocked by AutoMod.

        .. versionadded:: 2.10
        """
        return 1 << 7

    @flag_value
    def dm_settings_upsell_acknowledged(self):
        """:class:`bool`: Returns ``True`` if the member has dismissed the DM settings upsell.

        .. versionadded:: 2.10
        """
        return 1 << 9


class RoleFlags(BaseFlags):
    """Wraps up Discord Role flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two RoleFlags instances are equal.
        .. describe:: x != y

            Checks if two RoleFlags instances are not equal.
        .. describe:: x <= y

            Checks if a RoleFlags instance is a subset of another RoleFlags instance.
        .. describe:: x >= y

            Checks if a RoleFlags instance is a superset of another RoleFlags instance.
        .. describe:: x < y

            Checks if a RoleFlags instance is a strict subset of another RoleFlags instance.
        .. describe:: x > y

            Checks if a RoleFlags instance is a strict superset of another RoleFlags instance.
        .. describe:: x | y, x |= y

            Returns a new RoleFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new RoleFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new RoleFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new RoleFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: RoleFlags.y | RoleFlags.z, RoleFlags(y=True) | RoleFlags.z

            Returns a RoleFlags instance with all provided flags enabled.

        .. describe:: ~RoleFlags.y

            Returns a RoleFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.10

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(self, *, in_prompt: bool = ...) -> None: ...

    @flag_value
    def in_prompt(self):
        """:class:`bool`: Returns ``True`` if the role can be selected by members in an onboarding prompt."""
        return 1 << 0


class AttachmentFlags(BaseFlags):
    """Wraps up Discord Attachment flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two AttachmentFlags instances are equal.
        .. describe:: x != y

            Checks if two AttachmentFlags instances are not equal.
        .. describe:: x <= y

            Checks if an AttachmentFlags instance is a subset of another AttachmentFlags instance.
        .. describe:: x >= y

            Checks if an AttachmentFlags instance is a superset of another AttachmentFlags instance.
        .. describe:: x < y

            Checks if an AttachmentFlags instance is a strict subset of another AttachmentFlags instance.
        .. describe:: x > y

            Checks if an AttachmentFlags instance is a strict superset of another AttachmentFlags instance.
        .. describe:: x | y, x |= y

            Returns a new AttachmentFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new AttachmentFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new AttachmentFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new AttachmentFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: AttachmentFlags.y | AttachmentFlags.z, AttachmentFlags(y=True) | AttachmentFlags.z

            Returns an AttachmentFlags instance with all provided flags enabled.

        .. describe:: ~AttachmentFlags.y

            Returns an AttachmentFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.10

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            contains_explicit_media: bool = ...,
            is_animated: bool = ...,
            is_clip: bool = ...,
            is_remix: bool = ...,
            is_spoiler: bool = ...,
            is_thumbnail: bool = ...,
        ) -> None: ...

    @flag_value
    def is_clip(self):
        """:class:`bool`: Returns ``True`` if the attachment is a clip.

        .. versionadded:: 2.11
        """
        return 1 << 0

    @flag_value
    def is_thumbnail(self):
        """:class:`bool`: Returns ``True`` if the attachment is the thumbnail of a thread in a media channel.

        .. versionadded:: 2.11
        """
        return 1 << 1

    @flag_value
    def is_remix(self):
        """:class:`bool`: Returns ``True`` if the attachment has been edited using the Remix feature."""
        return 1 << 2

    @flag_value
    def is_spoiler(self):
        """:class:`bool`: Returns ``True`` if the attachment was marked as a spoiler.

        .. versionadded:: 2.11
        """
        return 1 << 3

    @flag_value
    def contains_explicit_media(self):
        """:class:`bool`: Returns ``True`` if the attachment was flagged as sensitive content.

        .. versionadded:: 2.11
        """
        return 1 << 4

    @flag_value
    def is_animated(self):
        """:class:`bool`: Returns ``True`` if the attachment is an animated image.

        .. versionadded:: 2.11
        """
        return 1 << 5


class SKUFlags(BaseFlags):
    """Wraps up Discord SKU flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two SKUFlags instances are equal.
        .. describe:: x != y

            Checks if two SKUFlags instances are not equal.
        .. describe:: x <= y

            Checks if an SKUFlags instance is a subset of another SKUFlags instance.
        .. describe:: x >= y

            Checks if an SKUFlags instance is a superset of another SKUFlags instance.
        .. describe:: x < y

            Checks if an SKUFlags instance is a strict subset of another SKUFlags instance.
        .. describe:: x > y

            Checks if an SKUFlags instance is a strict superset of another SKUFlags instance.
        .. describe:: x | y, x |= y

            Returns a new SKUFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new SKUFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new SKUFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new SKUFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: SKUFlags.y | SKUFlags.z, SKUFlags(y=True) | SKUFlags.z

            Returns an SKUFlags instance with all provided flags enabled.

        .. describe:: ~SKUFlags.y

            Returns an SKUFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.10

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self,
            *,
            available: bool = ...,
            guild_subscription: bool = ...,
            user_subscription: bool = ...,
        ) -> None: ...

    @flag_value
    def available(self):
        """:class:`bool`: Returns ``True`` if the SKU can be purchased."""
        return 1 << 2

    @flag_value
    def guild_subscription(self):
        """:class:`bool`: Returns ``True`` if the SKU is an application subscription applied to a guild."""
        return 1 << 7

    @flag_value
    def user_subscription(self):
        """:class:`bool`: Returns ``True`` if the SKU is an application subscription applied to a user."""
        return 1 << 8


class ApplicationInstallTypes(ListBaseFlags):
    """Represents the location(s) in which an application or application command can be installed.

    See the :ddocs:`official documentation <resources/application#installation-context>` for more info.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two ApplicationInstallTypes instances are equal.
        .. describe:: x != y

            Checks if two ApplicationInstallTypes instances are not equal.
        .. describe:: x <= y

            Checks if an ApplicationInstallTypes instance is a subset of another ApplicationInstallTypes instance.
        .. describe:: x >= y

            Checks if an ApplicationInstallTypes instance is a superset of another ApplicationInstallTypes instance.
        .. describe:: x < y

            Checks if an ApplicationInstallTypes instance is a strict subset of another ApplicationInstallTypes instance.
        .. describe:: x > y

            Checks if an ApplicationInstallTypes instance is a strict superset of another ApplicationInstallTypes instance.
        .. describe:: x | y, x |= y

            Returns a new ApplicationInstallTypes instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new ApplicationInstallTypes instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new ApplicationInstallTypes instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new ApplicationInstallTypes instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: ApplicationInstallTypes.y | ApplicationInstallTypes.z, ApplicationInstallTypes(y=True) | ApplicationInstallTypes.z

            Returns an ApplicationInstallTypes instance with all provided flags enabled.

        .. describe:: ~ApplicationInstallTypes.y

            Returns an ApplicationInstallTypes instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.10

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(self, *, guild: bool = ..., user: bool = ...) -> None: ...

    @classmethod
    def all(cls) -> Self:
        """A factory method that creates an :class:`ApplicationInstallTypes` instance with everything enabled."""
        self = cls.__new__(cls)
        self.value = all_flags_value(cls.VALID_FLAGS)
        return self

    @flag_value
    def guild(self):
        """:class:`bool`: Returns ``True`` if installable to guilds."""
        return 1 << 0

    @flag_value
    def user(self):
        """:class:`bool`: Returns ``True`` if installable to users."""
        return 1 << 1


class InteractionContextTypes(ListBaseFlags):
    """Represents the context(s) in which an application command can be used.

    See the :ddocs:`official documentation <interactions/application-commands#interaction-contexts>` for more info.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two InteractionContextTypes instances are equal.
        .. describe:: x != y

            Checks if two InteractionContextTypes instances are not equal.
        .. describe:: x <= y

            Checks if an InteractionContextTypes instance is a subset of another InteractionContextTypes instance.
        .. describe:: x >= y

            Checks if an InteractionContextTypes instance is a superset of another InteractionContextTypes instance.
        .. describe:: x < y

            Checks if an InteractionContextTypes instance is a strict subset of another InteractionContextTypes instance.
        .. describe:: x > y

            Checks if an InteractionContextTypes instance is a strict superset of another InteractionContextTypes instance.
        .. describe:: x | y, x |= y

            Returns a new InteractionContextTypes instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new InteractionContextTypes instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new InteractionContextTypes instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new InteractionContextTypes instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: InteractionContextTypes.y | InteractionContextTypes.z, InteractionContextTypes(y=True) | InteractionContextTypes.z

            Returns an InteractionContextTypes instance with all provided flags enabled.

        .. describe:: ~InteractionContextTypes.y

            Returns an InteractionContextTypes instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.10

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    __slots__ = ()

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self, *, bot_dm: bool = ..., guild: bool = ..., private_channel: bool = ...
        ) -> None: ...

    @classmethod
    def all(cls) -> Self:
        """A factory method that creates an :class:`InteractionContextTypes` instance with everything enabled."""
        self = cls.__new__(cls)
        self.value = all_flags_value(cls.VALID_FLAGS)
        return self

    @flag_value
    def guild(self):
        """:class:`bool`: Returns ``True`` if the command is usable in guilds."""
        return 1 << 0

    @flag_value
    def bot_dm(self):
        """:class:`bool`: Returns ``True`` if the command is usable in DMs with the bot."""
        return 1 << 1

    @flag_value
    def private_channel(self):
        """:class:`bool`: Returns ``True`` if the command is usable in DMs and group DMs with other users."""
        return 1 << 2


class EmbedFlags(BaseFlags):
    """Wraps up Discord Embed flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two EmbedFlags instances are equal.
        .. describe:: x != y

            Checks if two EmbedFlags instances are not equal.
        .. describe:: x <= y

            Checks if an EmbedFlags instance is a subset of another EmbedFlags instance.
        .. describe:: x >= y

            Checks if an EmbedFlags instance is a superset of another EmbedFlags instance.
        .. describe:: x < y

            Checks if an EmbedFlags instance is a strict subset of another EmbedFlags instance.
        .. describe:: x > y

            Checks if an EmbedFlags instance is a strict superset of another EmbedFlags instance.
        .. describe:: x | y, x |= y

            Returns a new EmbedFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new EmbedFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new EmbedFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new EmbedFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: EmbedFlags.y | EmbedFlags.z, EmbedFlags(y=True) | EmbedFlags.z

            Returns an EmbedFlags instance with all provided flags enabled.

        .. describe:: ~EmbedFlags.y

            Returns an EmbedFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.11

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    if TYPE_CHECKING:

        @_generated
        def __init__(
            self, *, contains_explicit_media: bool = ..., is_content_inventory_entry: bool = ...
        ) -> None: ...

    @flag_value
    def contains_explicit_media(self):
        """:class:`bool`: Returns ``True`` if the embed was flagged as sensitive content."""
        return 1 << 4

    @flag_value
    def is_content_inventory_entry(self):
        """:class:`bool`: Returns ``True`` if the embed is a reply to an activity card."""
        return 1 << 5


class EmbedMediaFlags(BaseFlags):
    """Wraps up Discord Embed media flags.

    .. collapse:: operations

        .. describe:: x == y

            Checks if two EmbedMediaFlags instances are equal.
        .. describe:: x != y

            Checks if two EmbedMediaFlags instances are not equal.
        .. describe:: x <= y

            Checks if an EmbedMediaFlags instance is a subset of another EmbedMediaFlags instance.
        .. describe:: x >= y

            Checks if an EmbedMediaFlags instance is a superset of another EmbedMediaFlags instance.
        .. describe:: x < y

            Checks if an EmbedMediaFlags instance is a strict subset of another EmbedMediaFlags instance.
        .. describe:: x > y

            Checks if an EmbedMediaFlags instance is a strict superset of another EmbedMediaFlags instance.
        .. describe:: x | y, x |= y

            Returns a new EmbedMediaFlags instance with all enabled flags from both x and y.
            (Using ``|=`` will update in place).
        .. describe:: x & y, x &= y

            Returns a new EmbedMediaFlags instance with only flags enabled on both x and y.
            (Using ``&=`` will update in place).
        .. describe:: x ^ y, x ^= y

            Returns a new EmbedMediaFlags instance with only flags enabled on one of x or y, but not both.
            (Using ``^=`` will update in place).
        .. describe:: ~x

            Returns a new EmbedMediaFlags instance with all flags from x inverted.
        .. describe:: hash(x)

            Returns the flag's hash.
        .. describe:: iter(x)

            Returns an iterator of ``(name, value)`` pairs. This allows it
            to be, for example, constructed as a dict or a list of pairs.
            Note that aliases are not shown.

        Additionally supported are a few operations on class attributes.

        .. describe:: EmbedMediaFlags.y | EmbedMediaFlags.z, EmbedMediaFlags(y=True) | EmbedMediaFlags.z

            Returns an EmbedMediaFlags instance with all provided flags enabled.

        .. describe:: ~EmbedMediaFlags.y

            Returns an EmbedMediaFlags instance with all flags except ``y`` inverted from their default value.

    .. versionadded:: 2.11

    Attributes
    ----------
    value: :class:`int`
        The raw value. You should query flags via the properties
        rather than using this raw value.
    """

    if TYPE_CHECKING:

        @_generated
        def __init__(self, *, is_animated: bool = ...) -> None: ...

    @flag_value
    def is_animated(self):
        """:class:`bool`: Returns ``True`` if the embed media is animated."""
        return 1 << 5

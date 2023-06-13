# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Dict, List, Tuple

from .enums import Event


class EventData:
    def __init__(
        self,
        *,
        arg_types: List[str],
        bot: bool = False,
        event_only: bool = False,
    ) -> None:
        self.arg_types: Tuple[str, ...] = tuple(arg_types)
        """Type names of event arguments, e.g. `("Guild", "User")`"""

        self.bot: bool = bot
        """Whether the event is specific to ext.commands"""

        self.event_only: bool = event_only
        """Whether the event can only be used through `@event` and not other listeners"""


EVENT_DATA: Dict[Event, EventData] = {
    Event.connect: EventData(
        arg_types=[],
    ),
    Event.disconnect: EventData(
        arg_types=[],
    ),
    # FIXME: figure out how to specify varargs for these two if we ever add overloads for @event
    Event.error: EventData(
        arg_types=[],
        event_only=True,
    ),
    Event.gateway_error: EventData(
        arg_types=[],
        event_only=True,
    ),
    Event.ready: EventData(
        arg_types=[],
    ),
    Event.resumed: EventData(
        arg_types=[],
    ),
    Event.shard_connect: EventData(
        arg_types=["int"],
    ),
    Event.shard_disconnect: EventData(
        arg_types=["int"],
    ),
    Event.shard_ready: EventData(
        arg_types=["int"],
    ),
    Event.shard_resumed: EventData(
        arg_types=["int"],
    ),
    Event.socket_event_type: EventData(
        arg_types=["str"],
    ),
    Event.socket_raw_receive: EventData(
        arg_types=["str"],
    ),
    Event.socket_raw_send: EventData(
        arg_types=["Union[str, bytes]"],
    ),
    Event.guild_channel_create: EventData(
        arg_types=["GuildChannel"],
    ),
    Event.guild_channel_update: EventData(
        arg_types=["GuildChannel", "GuildChannel"],
    ),
    Event.guild_channel_delete: EventData(
        arg_types=["GuildChannel"],
    ),
    Event.guild_channel_pins_update: EventData(
        arg_types=["Union[GuildChannel, Thread]", "Optional[datetime]"],
    ),
    Event.invite_create: EventData(
        arg_types=["Invite"],
    ),
    Event.invite_delete: EventData(
        arg_types=["Invite"],
    ),
    Event.private_channel_update: EventData(
        arg_types=["GroupChannel", "GroupChannel"],
    ),
    Event.private_channel_pins_update: EventData(
        arg_types=["PrivateChannel", "Optional[datetime]"],
    ),
    Event.webhooks_update: EventData(
        arg_types=["GuildChannel"],
    ),
    Event.thread_create: EventData(
        arg_types=["Thread"],
    ),
    Event.thread_update: EventData(
        arg_types=["Thread", "Thread"],
    ),
    Event.thread_delete: EventData(
        arg_types=["Thread"],
    ),
    Event.thread_join: EventData(
        arg_types=["Thread"],
    ),
    Event.thread_remove: EventData(
        arg_types=["Thread"],
    ),
    Event.thread_member_join: EventData(
        arg_types=["ThreadMember"],
    ),
    Event.thread_member_remove: EventData(
        arg_types=["ThreadMember"],
    ),
    Event.raw_thread_member_remove: EventData(
        arg_types=["RawThreadMemberRemoveEvent"],
    ),
    Event.raw_thread_update: EventData(
        arg_types=["Thread"],
    ),
    Event.raw_thread_delete: EventData(
        arg_types=["RawThreadDeleteEvent"],
    ),
    Event.guild_join: EventData(
        arg_types=["Guild"],
    ),
    Event.guild_remove: EventData(
        arg_types=["Guild"],
    ),
    Event.guild_update: EventData(
        arg_types=["Guild", "Guild"],
    ),
    Event.guild_available: EventData(
        arg_types=["Guild"],
    ),
    Event.guild_unavailable: EventData(
        arg_types=["Guild"],
    ),
    Event.guild_role_create: EventData(
        arg_types=["Role"],
    ),
    Event.guild_role_delete: EventData(
        arg_types=["Role"],
    ),
    Event.guild_role_update: EventData(
        arg_types=["Role", "Role"],
    ),
    Event.guild_emojis_update: EventData(
        arg_types=["Guild", "Sequence[Emoji]", "Sequence[Emoji]"],
    ),
    Event.guild_stickers_update: EventData(
        arg_types=["Guild", "Sequence[GuildSticker]", "Sequence[GuildSticker]"],
    ),
    Event.guild_integrations_update: EventData(
        arg_types=["Guild"],
    ),
    Event.guild_scheduled_event_create: EventData(
        arg_types=["GuildScheduledEvent"],
    ),
    Event.guild_scheduled_event_update: EventData(
        arg_types=["GuildScheduledEvent", "GuildScheduledEvent"],
    ),
    Event.guild_scheduled_event_delete: EventData(
        arg_types=["GuildScheduledEvent"],
    ),
    Event.guild_scheduled_event_subscribe: EventData(
        arg_types=["GuildScheduledEvent", "Union[Member, User]"],
    ),
    Event.guild_scheduled_event_unsubscribe: EventData(
        arg_types=["GuildScheduledEvent", "Union[Member, User]"],
    ),
    Event.raw_guild_scheduled_event_subscribe: EventData(
        arg_types=["RawGuildScheduledEventUserActionEvent"],
    ),
    Event.raw_guild_scheduled_event_unsubscribe: EventData(
        arg_types=["RawGuildScheduledEventUserActionEvent"],
    ),
    Event.application_command_permissions_update: EventData(
        arg_types=["GuildApplicationCommandPermissions"],
    ),
    Event.automod_action_execution: EventData(
        arg_types=["AutoModActionExecution"],
    ),
    Event.automod_rule_create: EventData(
        arg_types=["AutoModRule"],
    ),
    Event.automod_rule_update: EventData(
        arg_types=["AutoModRule"],
    ),
    Event.automod_rule_delete: EventData(
        arg_types=["AutoModRule"],
    ),
    Event.audit_log_entry_create: EventData(
        arg_types=["AuditLogEntry"],
    ),
    Event.integration_create: EventData(
        arg_types=["Integration"],
    ),
    Event.integration_update: EventData(
        arg_types=["Integration"],
    ),
    Event.raw_integration_delete: EventData(
        arg_types=["RawIntegrationDeleteEvent"],
    ),
    Event.member_join: EventData(
        arg_types=["Member"],
    ),
    Event.member_remove: EventData(
        arg_types=["Member"],
    ),
    Event.member_update: EventData(
        arg_types=["Member", "Member"],
    ),
    Event.raw_member_remove: EventData(
        arg_types=["RawGuildMemberRemoveEvent"],
    ),
    Event.raw_member_update: EventData(
        arg_types=["Member"],
    ),
    Event.member_ban: EventData(
        arg_types=["Guild", "Union[User, Member]"],
    ),
    Event.member_unban: EventData(
        arg_types=["Guild", "User"],
    ),
    Event.presence_update: EventData(
        arg_types=["Member", "Member"],
    ),
    Event.user_update: EventData(
        arg_types=["User", "User"],
    ),
    Event.voice_state_update: EventData(
        arg_types=["Member", "VoiceState", "VoiceState"],
    ),
    Event.stage_instance_create: EventData(
        arg_types=["StageInstance"],
    ),
    Event.stage_instance_delete: EventData(
        arg_types=["StageInstance", "StageInstance"],
    ),
    Event.stage_instance_update: EventData(
        arg_types=["StageInstance"],
    ),
    Event.application_command: EventData(
        arg_types=["ApplicationCommandInteraction"],
    ),
    Event.application_command_autocomplete: EventData(
        arg_types=["ApplicationCommandInteraction"],
    ),
    Event.button_click: EventData(
        arg_types=["MessageInteraction"],
    ),
    Event.dropdown: EventData(
        arg_types=["MessageInteraction"],
    ),
    Event.interaction: EventData(
        arg_types=["Interaction"],
    ),
    Event.message_interaction: EventData(
        arg_types=["MessageInteraction"],
    ),
    Event.modal_submit: EventData(
        arg_types=["ModalInteraction"],
    ),
    Event.message: EventData(
        arg_types=["Message"],
    ),
    Event.message_edit: EventData(
        arg_types=["Message", "Message"],
    ),
    Event.message_delete: EventData(
        arg_types=["Message"],
    ),
    Event.bulk_message_delete: EventData(
        arg_types=["List[Message]"],
    ),
    Event.raw_message_edit: EventData(
        arg_types=["RawMessageUpdateEvent"],
    ),
    Event.raw_message_delete: EventData(
        arg_types=["RawMessageDeleteEvent"],
    ),
    Event.raw_bulk_message_delete: EventData(
        arg_types=["RawBulkMessageDeleteEvent"],
    ),
    Event.reaction_add: EventData(
        arg_types=["Reaction", "Union[Member, User]"],
    ),
    Event.reaction_remove: EventData(
        arg_types=["Reaction", "Union[Member, User]"],
    ),
    Event.reaction_clear: EventData(
        arg_types=["Message", "List[Reaction]"],
    ),
    Event.reaction_clear_emoji: EventData(
        arg_types=["Reaction"],
    ),
    Event.raw_reaction_add: EventData(
        arg_types=["RawReactionActionEvent"],
    ),
    Event.raw_reaction_remove: EventData(
        arg_types=["RawReactionActionEvent"],
    ),
    Event.raw_reaction_clear: EventData(
        arg_types=["RawReactionClearEvent"],
    ),
    Event.raw_reaction_clear_emoji: EventData(
        arg_types=["RawReactionClearEmojiEvent"],
    ),
    Event.typing: EventData(
        arg_types=["Union[Messageable, ForumChannel]", "Union[User, Member]", "datetime"],
    ),
    Event.raw_typing: EventData(
        arg_types=["RawTypingEvent"],
    ),
    Event.command: EventData(
        arg_types=["commands.Context"],
        bot=True,
    ),
    Event.command_completion: EventData(
        arg_types=["commands.Context"],
        bot=True,
    ),
    Event.command_error: EventData(
        arg_types=["commands.Context", "commands.CommandError"],
        bot=True,
    ),
    Event.slash_command: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.slash_command_completion: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.slash_command_error: EventData(
        arg_types=["ApplicationCommandInteraction", "commands.CommandError"],
        bot=True,
    ),
    Event.user_command: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.user_command_completion: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.user_command_error: EventData(
        arg_types=["ApplicationCommandInteraction", "commands.CommandError"],
        bot=True,
    ),
    Event.message_command: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.message_command_completion: EventData(
        arg_types=["ApplicationCommandInteraction"],
        bot=True,
    ),
    Event.message_command_error: EventData(
        arg_types=["ApplicationCommandInteraction", "commands.CommandError"],
        bot=True,
    ),
}

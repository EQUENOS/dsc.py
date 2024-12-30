# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from ..utils import MISSING
from .async_ import Webhook

if TYPE_CHECKING:
    from typing import List, Optional

    from ..abc import Snowflake
    from ..embeds import Embed
    from ..file import File
    from ..flags import MessageFlags
    from ..mentions import AllowedMentions
    from ..ui.action_row import Components, MessageUIComponent
    from ..ui.view import View
    from ..webhook.async_ import WebhookMessage

__all__ = ("InteractionFollowupWebhook",)


class InteractionFollowupWebhook(Webhook):
    """A 1:1 copy of :class:`Webhook` meant for :attr:`Interaction.followup`\\'s annotations."""

    if TYPE_CHECKING:

        async def send(
            self,
            content: Optional[str] = MISSING,
            *,
            tts: bool = MISSING,
            ephemeral: bool = MISSING,
            suppress_embeds: bool = MISSING,
            flags: MessageFlags = MISSING,
            file: File = MISSING,
            files: List[File] = MISSING,
            embed: Embed = MISSING,
            embeds: List[Embed] = MISSING,
            allowed_mentions: AllowedMentions = MISSING,
            view: View = MISSING,
            components: Components[MessageUIComponent] = MISSING,
            thread: Snowflake = MISSING,
            thread_name: str = MISSING,
            applied_tags: Sequence[Snowflake] = MISSING,
            delete_after: float = MISSING,
        ) -> WebhookMessage:
            """|coro|

            Sends a message using the webhook.

            This is the same as :meth:`Webhook.send` but with type hints changed. Namely,
            this method always returns a :class:`WebhookMessage` because ``wait=True`` for
            interaction webhooks, and ``username`` and ``avatar_url`` are not supported.

            Returns
            -------
            :class:`WebhookMessage`
                The message that was sent.
            """
            return await super().send(
                content=content,
                tts=tts,
                ephemeral=ephemeral,
                embeds=embeds,
                embed=embed,
                file=file,
                files=files,
                view=view,
                components=components,
                allowed_mentions=allowed_mentions,
                thread=thread,
                thread_name=thread_name,
                applied_tags=applied_tags,
                delete_after=delete_after,
                suppress_embeds=suppress_embeds,
                flags=flags,
                wait=True,
            )

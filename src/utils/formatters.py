from __future__ import annotations

from collections.abc import Sequence

from src.database.models import Subscription
from src.utils.i18n import translate


def format_subscription_list(
    subscriptions: Sequence[Subscription],
    *,
    chat_title: str | None,
    chat_type: str,
    locale: str,
    request_id: str | None = None,
) -> str:
    """Produce a formatted subscription list for the current chat context."""
    header_key = "formatters.subscription.header.private"
    resolved_title = chat_title
    if chat_type == "group":
        header_key = "formatters.subscription.header.group"
        if not resolved_title:
            resolved_title = translate(
                "formatters.subscription.unnamed.group",
                locale=locale,
                request_id=request_id,
            )
    elif chat_type == "supergroup":
        header_key = "formatters.subscription.header.supergroup"
        if not resolved_title:
            resolved_title = translate(
                "formatters.subscription.unnamed.supergroup",
                locale=locale,
                request_id=request_id,
            )
    elif chat_type == "channel":
        header_key = "formatters.subscription.header.channel"
        if not resolved_title:
            resolved_title = translate(
                "formatters.subscription.unnamed.channel",
                locale=locale,
                request_id=request_id,
            )

    lines: list[str] = [
        translate(
            header_key,
            locale=locale,
            request_id=request_id,
            chat_title=escape_markdown_v2(resolved_title or ""),
        ),
        "",
    ]

    for subscription in subscriptions:
        channel = subscription.channel
        lines.append(
            translate(
                "formatters.subscription.item_line",
                locale=locale,
                request_id=request_id,
                channel_name=escape_markdown_v2(channel.channel_name),
            )
        )
        lines.append(
            translate(
                "formatters.subscription.item_link",
                locale=locale,
                request_id=request_id,
                channel_url=escape_markdown_v2(channel.channel_url),
            )
        )
        lines.append("")

    lines.append(
        translate(
            "formatters.subscription.footer",
            locale=locale,
            request_id=request_id,
            command="/unsubscribe",
        )
    )
    return "\n".join(lines)


def format_group_discussion_prompt(
    *,
    chat_type: str,
    chat_title: str | None,
    locale: str,
    request_id: str | None = None,
) -> str | None:
    """Return an additional prompt encouraging interaction for shared contexts."""
    if chat_type == "private":
        return None

    audience = chat_title
    if chat_type == "channel" and not audience:
        audience = translate(
            "formatters.group_prompt.channel_fallback",
            locale=locale,
            request_id=request_id,
        )
    elif not audience:
        audience = translate(
            "formatters.group_prompt.shared_fallback",
            locale=locale,
            request_id=request_id,
        )

    if chat_type == "channel":
        return translate(
            "formatters.group_prompt.channel",
            locale=locale,
            request_id=request_id,
            chat_title=escape_markdown_v2(audience or ""),
        )

    return translate(
        "formatters.group_prompt.shared",
        locale=locale,
        request_id=request_id,
        chat_title=escape_markdown_v2(audience or ""),
    )


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram's MarkdownV2.

    The following characters are escaped: `_`, `*`, `[`, `]`, `(`, `)`, `~`,
    `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`
    """
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in escape_chars else char for char in text)

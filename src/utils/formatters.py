from __future__ import annotations

from collections.abc import Sequence

from src.database.models import Subscription


def format_subscription_list(
    subscriptions: Sequence[Subscription],
    *,
    chat_title: str | None,
    chat_type: str,
) -> str:
    """Produce a formatted subscription list for the current chat context."""
    header = "📋 Your subscriptions:"
    if chat_type == "group":
        header = f"📋 Subscriptions shared with {chat_title or 'this group'}:"
    elif chat_type == "supergroup":
        header = f"📋 Subscriptions for {chat_title or 'this supergroup'}:"
    elif chat_type == "channel":
        header = f"📋 Channels tracked for {chat_title or 'this channel'}:"

    lines: list[str] = [header, ""]

    for subscription in subscriptions:
        channel = subscription.channel
        lines.append(f"• {channel.channel_name}")
        lines.append(f"  {channel.channel_url}")
        lines.append("")

    lines.append("Use /unsubscribe to remove a channel.")
    return "\n".join(lines)


def format_group_discussion_prompt(*, chat_type: str, chat_title: str | None) -> str | None:
    """Return an additional prompt encouraging interaction for shared contexts."""
    if chat_type == "private":
        return None

    audience = chat_title or "everyone here"

    if chat_type == "channel":
        return (
            f"📣 Share this update with {audience} and pin it if it's important.\n"
            "💡 Add your own summary so followers know why it matters."
        )

    return (
        f"💬 Keep the conversation going with {audience}.\n"
        "Ask for thoughts, share highlights, or schedule a watch party!"
    )

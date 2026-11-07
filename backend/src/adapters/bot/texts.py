"""English copy for the public bot."""

BRAND = "UNKRE"
BUTTON_LABEL = "Open UNKRE Studio"
TAGLINE = "Uncensored AI image studio."


def start_message(free_credits: int) -> str:
    perks = [
        f"• <b>{free_credits} free credits</b> for new accounts"
        if free_credits > 0
        else "• Create an account in seconds",
        "• Sign in with Google or Telegram",
    ]
    return "\n".join(
        [
            f"<b>{BRAND}</b> — {TAGLINE[0].lower()}{TAGLINE[1:]}",
            "",
            "Create ultra-realistic SFW and NSFW images with Krea 2 and "
            "Qwen Image 2.1. Use reference photos, build recurring characters "
            "and explore LoRAs.",
            "",
            *perks,
            "",
            "Tap the button below to open the MiniApp and start creating.",
        ]
    )

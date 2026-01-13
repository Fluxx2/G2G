import discord
import asyncio
import os
import re
from datetime import datetime, timezone
from itertools import product

# ================================
# CONFIG
# ================================
CHANNEL_ID = 1442370325831487608
MAX_AGE_SECONDS = 240
TOGGLE_INTERVAL = 27
EDIT_THROTTLE = 1.6

NO_TOGGLE_USER_IDS = {
    1252645184777359391,
    906546198754775082
}

VARIANT_ROLE_ID = 1460446818407022785

MAX_VARIANTS = 16  # safety cap (VERY IMPORTANT)

# ================================
# BOT SETUP
# ================================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

mirrored_messages = {}
code_data = {}

# ================================
# HELPERS
# ================================
def is_fresh(msg: discord.Message) -> bool:
    age = (datetime.now(timezone.utc) - msg.created_at).total_seconds()
    return age <= MAX_AGE_SECONDS

def discord_relative_timestamp(seconds_from_now: int) -> str:
    unix = int(datetime.now(timezone.utc).timestamp()) + seconds_from_now
    return f"<t:{unix}:R>"

def has_variant_role(member: discord.Member) -> bool:
    return any(role.id == VARIANT_ROLE_ID for role in member.roles)

AMBIGUOUS_SETS = {
    "l": ["l", "I"],
    "I": ["I", "l"],
}

def generate_all_variants(code: str) -> list[str]:
    pools = [AMBIGUOUS_SETS.get(c, [c]) for c in code]
    variants = ["".join(p) for p in product(*pools)]

    seen = set()
    unique = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique.append(v)

    if code in unique:
        unique.remove(code)
    unique.insert(0, code)

    return unique[:MAX_VARIANTS]

def build_content(source_id: int) -> str:
    data = code_data[source_id]
    codes = data["codes"]

    if len(codes) == 1:
        header = f"# `     {codes[0]}     `"
    else:
        header = "\n".join(
            f"# {i}) `   {code}   `"
            for i, code in enumerate(codes, start=1)
        )

    if not data["show_timer"]:
        return header

    return f"{header}\n{data['emoji']} {data['timer']}"

async def expire_message(source_id: int):
    await asyncio.sleep(MAX_AGE_SECONDS)

    msg = mirrored_messages.pop(source_id, None)
    code_data.pop(source_id, None)

    if msg:
        try:
            await msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

# ================================
# EMOJI TOGGLE LOOP
# ================================
async def emoji_toggle_loop():
    await client.wait_until_ready()

    while not client.is_closed():
        for source_id, msg in list(mirrored_messages.items()):
            data = code_data.get(source_id)

            if not data or not data["show_timer"]:
                continue

            data["emoji"] = "🔚" if data["emoji"] == "⏳" else "⏳"

            try:
                await msg.edit(content=build_content(source_id))
                await asyncio.sleep(EDIT_THROTTLE)
            except (discord.NotFound, discord.HTTPException):
                pass

        await asyncio.sleep(TOGGLE_INTERVAL)

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Code Bot logged in as {client.user}")
    client.loop.create_task(emoji_toggle_loop())

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != CHANNEL_ID:
        return

    if not is_fresh(message):
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
    if not match:
        return

    code = match.group(0)

    # ROLE → variants
    use_variants = has_variant_role(message.author)

    # USER ID → timer + emoji
    show_timer = message.author.id not in NO_TOGGLE_USER_IDS

    codes = generate_all_variants(code) if use_variants else [code]
    timer = discord_relative_timestamp(MAX_AGE_SECONDS) if show_timer else ""

    code_data[message.id] = {
        "codes": codes,
        "timer": timer,
        "emoji": "⏳",
        "show_timer": show_timer
    }

    mirrored_messages[message.id] = await message.channel.send(
        build_content(message.id)
    )

    client.loop.create_task(expire_message(message.id))

@client.event
async def on_message_edit(before, after):
    if not is_fresh(after):
        return

    data = code_data.get(after.id)
    msg = mirrored_messages.get(after.id)

    if not data or not msg:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    new_code = match.group(0)

    data["codes"] = (
        generate_all_variants(new_code)
        if has_variant_role(after.author)
        else [new_code]
    )

    try:
        await msg.edit(content=build_content(after.id))
    except (discord.NotFound, discord.HTTPException):
        pass

@client.event
async def on_message_delete(message):
    msg = mirrored_messages.pop(message.id, None)
    code_data.pop(message.id, None)

    if msg:
        try:
            await msg.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

# ================================
# RUN
# ================================
client.run(TOKEN)

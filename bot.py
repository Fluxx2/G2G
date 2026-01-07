import discord
import asyncio
import os
import re
from datetime import datetime, timezone

# ================================
# CONFIG
# ================================
toggle_tasks = {}

MIRROR_SOURCE_CHANNEL_ID = 1442370325831487608
MIRROR_TARGET_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

DELETE_AFTER = 225

ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

TARGET_BOT_IDS = {
    1457091181224661004,
    628400349979344919,
}

CODE_COUNTDOWN_SECONDS = 240

# ================================
# BOT SETUP
# ================================
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# message_id -> { channel_id: discord.Message }
mirrored_messages = {}

# message_id -> code/timer/emoji (SOURCE OF TRUTH)
code_data = {}

# ================================
# HELPERS
# ================================
def discord_relative_timestamp(seconds_from_now: int) -> str:
    unix = int(datetime.now(timezone.utc).timestamp()) + seconds_from_now
    return f"<t:{unix}:R>"

def build_content(source_id: int) -> str:
    data = code_data[source_id]
    return (
        f"# `     {data['code']}     `\n"
        f"{data['emoji']} {data['timer']}"
    )

async def toggle_code_emoji(source_message_id: int):
    while True:
        data = code_data.get(source_message_id)
        mirrored = mirrored_messages.get(source_message_id)

        if not data or not mirrored:
            return

        # toggle emoji
        data["emoji"] = "🔚" if data["emoji"] == "⏳" else "⏳"
        content = build_content(source_message_id)

        for msg in mirrored.values():
            try:
                await msg.edit(content=content)
            except:
                pass

        await asyncio.sleep(15)

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Code Bot logged in as {client.user}")

@client.event
async def on_message(message):

    # Auto-delete target bots
    if (
        message.author.bot
        and message.channel.id in ALLOWED_CHANNEL_IDS
        and message.author.id in TARGET_BOT_IDS
    ):
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except:
            pass
        return

    if message.author.bot:
        return

    # Code mirroring
    if message.channel.id == MIRROR_SOURCE_CHANNEL_ID:
        match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
        if not match:
            return

        code = match.group(0)
        timer = discord_relative_timestamp(CODE_COUNTDOWN_SECONDS)

        # ✅ store canonical data
        code_data[message.id] = {
            "code": code,
            "timer": timer,
            "emoji": "⏳"
        }

        mirrored_messages[message.id] = {}
        content = build_content(message.id)

        for cid in MIRROR_TARGET_CHANNEL_IDS:
            ch = client.get_channel(cid)
            if ch:
                mirrored_messages[message.id][cid] = await ch.send(content)

        toggle_tasks[message.id] = client.loop.create_task(
            toggle_code_emoji(message.id)
        )

@client.event
async def on_message_edit(before, after):
    data = code_data.get(after.id)
    mirrored = mirrored_messages.get(after.id)

    if not data or not mirrored:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    # ✅ update ONLY the code
    data["code"] = match.group(0)
    content = build_content(after.id)

    for msg in mirrored.values():
        try:
            await msg.edit(content=content)
        except:
            pass

@client.event
async def on_message_delete(message):
    mirrored = mirrored_messages.pop(message.id, None)
    code_data.pop(message.id, None)

    task = toggle_tasks.pop(message.id, None)
    if task:
        task.cancel()

    if not mirrored:
        return

    for msg in mirrored.values():
        try:
            await msg.delete()
        except:
            pass

# ================================
# RUN
# ================================
client.run(TOKEN)

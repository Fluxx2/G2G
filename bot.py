import discord
import asyncio
import os
import re
from datetime import datetime, timezone

# ================================
# CONFIG
# ================================
CHANNEL_ID = 1442370325831487608
CODE_COUNTDOWN_SECONDS = 240

NO_TOGGLE_USER_IDS = {
    1252645184777359391,
    906546198754775082
}

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
toggle_tasks = {}

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
        msg = mirrored_messages.get(source_message_id)

        if not data or not msg:
            return

        data["emoji"] = "🔚" if data["emoji"] == "⏳" else "⏳"
        try:
            await msg.edit(content=build_content(source_message_id))
        except:
            pass

        await asyncio.sleep(27)

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Code Bot logged in as {client.user}")

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != CHANNEL_ID:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
    if not match:
        return

    code = match.group(0)

    is_no_toggle_user = message.author.id in NO_TOGGLE_USER_IDS

    timer = (
        discord_relative_timestamp(CODE_COUNTDOWN_SECONDS)
        if not is_no_toggle_user
        else ""
    )

    code_data[message.id] = {
        "code": code,
        "timer": timer,
        "emoji": "⏳"
    }

    content = build_content(message.id)
    mirrored_messages[message.id] = await message.channel.send(content)

    # 🚫 DO NOT START TOGGLE FOR SPECIFIC USERS
    if not is_no_toggle_user:
        toggle_tasks[message.id] = client.loop.create_task(
            toggle_code_emoji(message.id)
        )

@client.event
async def on_message_edit(before, after):
    data = code_data.get(after.id)
    msg = mirrored_messages.get(after.id)

    if not data or not msg:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    data["code"] = match.group(0)
    try:
        await msg.edit(content=build_content(after.id))
    except:
        pass

@client.event
async def on_message_delete(message):
    msg = mirrored_messages.pop(message.id, None)
    code_data.pop(message.id, None)

    task = toggle_tasks.pop(message.id, None)
    if task:
        task.cancel()

    if msg:
        try:
            await msg.delete()
        except:
            pass

# ================================
# RUN
# ================================
client.run(TOKEN)

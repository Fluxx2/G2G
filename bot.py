import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone
import pytz
import re

# ================================
# CONFIG
# ================================

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

GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370325831487608
LOG_CHANNEL_ID = 1443852961502466090

# Reaction countdown
REACTION_CHANNEL_ID = 1442370325831487608
REACTION_INTERVAL = 10
REACTION_DURATION = 240
REACTIONS = [
    "⚪","⚪","⚪","⚪","⚪",
    "🟢","🟢","🟢","🟢","🟢","🟢",
    "🟡","🟡","🟡","🟡","🟡",
    "🔴","🔴","🔴",
    "⚠️","‼️","🚨",
    "🚫","🚫"
]

# Custom emoji mass delete
TARGET_USER_ID = 906546198754775082
TARGET_EMOJI_ID = 1444022259789467709
REACTION_THRESHOLD = 4

# Wins system
WINS_SOURCE_CHANNEL_ID = 1442370325831487608
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

IST = pytz.timezone("Asia/Kolkata")

# ================================
# BOT SETUP
# ================================

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_win_message: dict[int, discord.Message] = {}

# ✅ FIX: store mirrored bot messages correctly
# { source_message_id: { channel_id: bot_message } }
mirrored_messages: dict[int, dict[int, discord.Message]] = {}

# ================================
# HELPERS
# ================================

async def reaction_countdown(message: discord.Message):
    steps = REACTION_DURATION // REACTION_INTERVAL
    last = None

    for i in range(steps):
        try:
            if last:
                await message.remove_reaction(last, client.user)

            emoji = REACTIONS[i % len(REACTIONS)]
            await message.add_reaction(emoji)
            last = emoji

            await asyncio.sleep(REACTION_INTERVAL)
        except (discord.NotFound, discord.Forbidden):
            break


async def cleanup_channel(channel):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24, minutes=30)
    deleted = 0

    async for msg in channel.history(limit=None):
        if msg.author.bot or msg.created_at < cutoff:
            continue
        try:
            await msg.delete()
            deleted += 1
            await asyncio.sleep(0.4)
        except (discord.NotFound, discord.Forbidden):
            pass

    return deleted


async def seconds_until_ist_midnight():
    now = datetime.now(IST)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


async def count_live_messages(channel, user):
    count = 0
    async for msg in channel.history(limit=None):
        if msg.author.id == user.id and not msg.author.bot:
            count += 1
    return count

# ================================
# BACKGROUND TASK
# ================================

async def daily_cleanup_task():
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)

    while not client.is_closed():
        await asyncio.sleep(await seconds_until_ist_midnight())
        deleted = await cleanup_channel(channel)

        log = client.get_channel(LOG_CHANNEL_ID)
        if log:
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win `{deleted}`** in <#{channel.id}>"
            )

        await asyncio.sleep(60)

# ================================
# EVENTS
# ================================

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    client.loop.create_task(daily_cleanup_task())


@client.event
async def on_message(message: discord.Message):

    # ✅ FIX: targeted bot deletion works in BOTH channels
    if (
        message.author.bot
        and message.channel.id in ALLOWED_CHANNEL_IDS
        and message.author.id in TARGET_BOT_IDS
    ):
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass
        return

    if message.author.bot:
        return

    # ========================
    # CODE DETECTION & MIRROR
    # ========================
    if message.channel.id == MIRROR_SOURCE_CHANNEL_ID:
        match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
        if match:
            code = match.group(0)
            formatted = f"# `     {code}     `"

            mirrored_messages[message.id] = {}

            for channel_id in MIRROR_TARGET_CHANNEL_IDS:
                channel = client.get_channel(channel_id)
                if channel:
                    bot_msg = await channel.send(formatted)
                    mirrored_messages[message.id][channel_id] = bot_msg

    # ========================
    # REACTION COUNTDOWN
    # ========================
    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

    # ========================
    # WINS SYSTEM
    # ========================
    if message.channel.id == WINS_SOURCE_CHANNEL_ID:
        total = await count_live_messages(message.channel, message.author)

        if total > 0 and total % 10 == 0:
            announce = client.get_channel(WINS_ANNOUNCE_CHANNEL_ID)
            if not announce:
                return

            old = last_win_message.get(message.author.id)
            if old:
                try:
                    await old.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass

            new_msg = await announce.send(
                f"{message.author.mention} **wins done today so far ({total})**"
            )
            last_win_message[message.author.id] = new_msg


@client.event
async def on_message_edit(before, after):
    mirrored = mirrored_messages.get(after.id)
    if not mirrored:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    formatted = f"# `     {match.group(0)}     `"

    for msg in mirrored.values():
        try:
            await msg.edit(content=formatted)
        except (discord.NotFound, discord.Forbidden):
            pass


@client.event
async def on_message_delete(message):
    mirrored = mirrored_messages.pop(message.id, None)
    if not mirrored:
        return

    for msg in mirrored.values():
        try:
            await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            pass


@client.event
async def on_reaction_add(reaction, user):
    try:
        msg = reaction.message

        if user.bot:
            return
        if msg.channel.id != REACTION_CHANNEL_ID:
            return
        if msg.author.id != TARGET_USER_ID:
            return
        if not isinstance(reaction.emoji, discord.Emoji):
            return
        if reaction.emoji.id != TARGET_EMOJI_ID:
            return

        if reaction.count >= REACTION_THRESHOLD:
            await msg.delete()

    except (discord.NotFound, discord.Forbidden):
        pass

# ================================
# SLASH COMMAND
# ================================

@tree.command(
    name="daily_count",
    description="Delete human messages under 24h30m",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction):
    await interaction.response.defer(ephemeral=True)

    deleted = await cleanup_channel(interaction.channel)

    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(
            f"🧹 **Manual Daily Cleanup**\n"
            f"📍 <#{interaction.channel.id}>\n"
            f"🏆 todays win **{deleted}**"
        )

    await interaction.followup.send(
        f"🏆 todays win **{deleted}**",
        ephemeral=True
    )

# ================================
# RUN
# ================================

client.run(TOKEN)

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

# Code countdown
CODE_COUNTDOWN_SECONDS = 240
CODE_COUNTDOWN_INTERVAL = 5

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

# mirrored messages
mirrored_messages: dict[int, dict[int, discord.Message]] = {}

# ================================
# LIVE DAILY WINS
# ================================

daily_wins = 0
live_wins_message: discord.Message | None = None

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
        except:
            break


async def cleanup_channel(channel):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24, minutes=30)
    deleted = 0

    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot or msg.created_at < cutoff:
            continue
        try:
            await msg.delete()
            deleted += 1
            await asyncio.sleep(0.4)
        except:
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


async def update_live_wins():
    global live_wins_message

    channel = client.get_channel(LOG_CHANNEL_ID)
    if not channel:
        return

    content = f"🏆 **Live Wins Today:** `{daily_wins}`"

    if live_wins_message:
        try:
            await live_wins_message.edit(content=content)
            return
        except:
            live_wins_message = None

    live_wins_message = await channel.send(content)


async def run_code_countdown(source_id: int):
    remaining = CODE_COUNTDOWN_SECONDS

    while remaining >= 0:
        mirrored = mirrored_messages.get(source_id)
        if not mirrored:
            return

        mins = remaining // 60
        secs = remaining % 60
        timer = f"{mins:02d}:{secs:02d}"

        for msg in mirrored.values():
            try:
                base = msg.content.split("⏳")[0].rstrip()
                await msg.edit(content=f"{base} ⏳ {timer}")
            except:
                pass

        await asyncio.sleep(CODE_COUNTDOWN_INTERVAL)
        remaining -= CODE_COUNTDOWN_INTERVAL

# ================================
# BACKGROUND TASK
# ================================

async def daily_cleanup_task():
    global daily_wins, live_wins_message

    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while not client.is_closed():
        await asyncio.sleep(await seconds_until_ist_midnight())

        if live_wins_message:
            try:
                await live_wins_message.delete()
            except:
                pass
            live_wins_message = None

        deleted = await cleanup_channel(channel)

        if log:
            await log.send(
                f"🌙 **Daily Cleanup Complete (IST Midnight)**\n"
                f"**🏆 todays win `404` in** <#CHANNEL_ID>"
            )

        daily_wins = 0
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

    if message.channel.id == MIRROR_SOURCE_CHANNEL_ID:
        match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
        if match:
            code = match.group(0)
            formatted = f"# `     {code}     ` ⏳ 04:00"

            mirrored_messages[message.id] = {}

            for cid in MIRROR_TARGET_CHANNEL_IDS:
                ch = client.get_channel(cid)
                if ch:
                    bot_msg = await ch.send(formatted)
                    mirrored_messages[message.id][cid] = bot_msg

            client.loop.create_task(run_code_countdown(message.id))

    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

    if message.channel.id == WINS_SOURCE_CHANNEL_ID:
        global daily_wins
        daily_wins += 1
        await update_live_wins()

        total = await count_live_messages(message.channel, message.author)
        if total > 0 and total % 10 == 0:
            announce = client.get_channel(WINS_ANNOUNCE_CHANNEL_ID)
            old = last_win_message.get(message.author.id)
            if old:
                try:
                    await old.delete()
                except:
                    pass
            last_win_message[message.author.id] = await announce.send(
                f"{message.author.mention} **wins done today so far ({total})**"
            )


@client.event
async def on_message_edit(before, after):
    mirrored = mirrored_messages.get(after.id)
    if not mirrored:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    formatted = f"# `     {match.group(0)}     ` ⏳ 04:00"

    for msg in mirrored.values():
        try:
            await msg.edit(content=formatted)
        except:
            pass

    client.loop.create_task(run_code_countdown(after.id))


@client.event
async def on_message_delete(message):
    mirrored = mirrored_messages.pop(message.id, None)
    if not mirrored:
        return

    for msg in mirrored.values():
        try:
            await msg.delete()
        except:
            pass


@client.event
async def on_reaction_add(reaction, user):
    try:
        msg = reaction.message
        if (
            not user.bot
            and msg.channel.id == REACTION_CHANNEL_ID
            and msg.author.id == TARGET_USER_ID
            and isinstance(reaction.emoji, discord.Emoji)
            and reaction.emoji.id == TARGET_EMOJI_ID
            and reaction.count >= REACTION_THRESHOLD
        ):
            await msg.delete()
    except:
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

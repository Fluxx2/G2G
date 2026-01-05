import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone
import pytz

# ================================
# CONFIG
# ================================

DELETE_AFTER = 225

ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

TARGET_BOT_IDS = {
    1449623475588436039,
    628400349979344919
}

GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370325831487608

# Reaction countdown
REACTION_CHANNEL_ID = 1442370325831487608
REACTION_INTERVAL = 10
REACTION_DURATION = 240
REACTIONS = [
    "⚪","⚪","⚪","⚪","⚪",
    "🟢","🟢","🟢","🟢","🟢","🟢",
    "🟡","🟡","🟡","🟡","🟡",
    "🔴","🔴","🔴",
    "🚨","🚨","🚨",
    "🚫","🚫"
]

# 🔥 Custom emoji mass delete
TARGET_USER_ID = 906546198754775082
TARGET_EMOJI_ID = 1444022259789467709  # LL emoji ID
REACTION_THRESHOLD = 4  # delete when count >= 4

# 🏆 Wins system
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

    async for msg in channel.history(limit=None):
        if msg.author.bot or msg.created_at < cutoff:
            continue
        try:
            await msg.delete()
            await asyncio.sleep(0.4)
        except (discord.NotFound, discord.Forbidden):
            pass


async def seconds_until_ist_midnight():
    now = datetime.now(IST)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


async def count_user_messages_today(channel, user):
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start.astimezone(timezone.utc)

    count = 0
    async for msg in channel.history(after=start_utc):
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
        await cleanup_channel(channel)
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
async def on_message(message):
    if message.author.id == client.user.id:
        return

    # Delete specific bot messages
    if (
        message.channel.id in ALLOWED_CHANNEL_IDS
        and message.author.bot
        and message.author.id in TARGET_BOT_IDS
    ):
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden):
            pass

    # Reaction countdown
    if message.channel.id == REACTION_CHANNEL_ID and not message.author.bot:
        client.loop.create_task(reaction_countdown(message))

    # 🏆 Wins counter
    if (
        message.channel.id == WINS_SOURCE_CHANNEL_ID
        and not message.author.bot
    ):
        total = await count_user_messages_today(message.channel, message.author)

        if total > 0 and total % 10 == 0:
            announce = client.get_channel(WINS_ANNOUNCE_CHANNEL_ID)
            if announce:
                await announce.send(
                    f"{message.author.mention} wins done today so far ({total})"
                )


@client.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
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
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await cleanup_channel(interaction.channel)
    await interaction.followup.send(
        "✅ Daily cleanup complete.", ephemeral=True
    )

# ================================
# RUN
# ================================

client.run(TOKEN)

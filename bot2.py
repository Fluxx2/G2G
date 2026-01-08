"""
Wins Bot Features:

1. Live Wins Counter
2. Daily Cleanup (IST Midnight) — counts deleted messages correctly
3. User Milestone Announcements
4. Reaction-Based Deletion
5. Timezone Handling (IST)
6. Slash Command
7. Stability and Safety
"""

import discord
import asyncio
import os
from datetime import datetime, timedelta, timezone
import pytz
from discord import app_commands

# ================================
# CONFIG
# ================================
GUILD_ID = 1442370324858667041

AUTO_CHANNEL_ID = 1442370325831487608
SECOND_AUTO_CHANNEL_ID = 1449692284596523068
LOG_CHANNEL_ID = 1443852961502466090
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

TARGET_USER_ID = 906546198754775082
TARGET_EMOJI_ID = 1444022259789467709
REACTION_THRESHOLD = 4

IST = pytz.timezone("Asia/Kolkata")

# ================================
# BOT SETUP
# ================================
TOKEN = os.getenv("DISCORD_TOKEN_2")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN_2 not set")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_win_message = {}
live_total_message = None

# stores deleted count for daily reset
daily_deleted_count = 0

# ================================
# HELPERS
# ================================
async def count_user_messages_today(channel, user):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot and msg.author.id == user.id:
            count += 1
    return count

async def count_total_messages_today(channel):
    start = datetime.now(IST).replace(hour=1, minute=31, second=50, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot:
            count += 1
    return count

async def cleanup_channel_last_24h(channel):
    """
    Deletes HUMAN messages from the last 24 hours
    Counts deletions from oldest → newest
    """
    global daily_deleted_count

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot:
            continue

        if msg.created_at < cutoff:
            continue

        try:
            await msg.delete()
            daily_deleted_count += 1
            await asyncio.sleep(0.6)
        except:
            pass

async def update_live_total():
    global live_total_message

    log = client.get_channel(LOG_CHANNEL_ID)
    channel = client.get_channel(AUTO_CHANNEL_ID)
    if not log or not channel:
        return

    total = await count_total_messages_today(channel)
    content = f"🏆 **Live Wins Today:** `{total}`"

    if live_total_message:
        try:
            await live_total_message.edit(content=content)
            return
        except:
            live_total_message = None

    live_total_message = await log.send(content)

# ================================
# BACKGROUND TASKS
# ================================
async def live_wins_loop():
    await client.wait_until_ready()
    while not client.is_closed():
        await update_live_total()
        await asyncio.sleep(60)

async def daily_cleanup_task():
    global daily_deleted_count, live_total_message

    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while True:
        now = datetime.now(IST)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_midnight - now).total_seconds())

        # delete live counter message
        if live_total_message:
            try:
                await live_total_message.delete()
            except:
                pass
            live_total_message = None

        # reset count before cleanup
        daily_deleted_count = 0

        # cleanup last 24h messages
        await cleanup_channel_last_24h(channel)

        # log correct deleted count
        if log:
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n" 
                f"**🏆 todays win {total} in** <#{AUTO_CHANNEL_ID}>"
            )

        daily_deleted_count = 0

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Wins Bot logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    client.loop.create_task(live_wins_loop())
    client.loop.create_task(daily_cleanup_task())

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id == AUTO_CHANNEL_ID:
        user_total = await count_user_messages_today(message.channel, message.author)
        if user_total > 0 and user_total % 10 == 0:
            announce = client.get_channel(WINS_ANNOUNCE_CHANNEL_ID)
            old = last_win_message.get(message.author.id)
            if old:
                try:
                    await old.delete()
                except:
                    pass
            last_win_message[message.author.id] = await announce.send(
                f"{message.author.mention} **wins done today so far ({user_total})**"
            )

@client.event
async def on_reaction_add(reaction, user):
    try:
        if (
            not user.bot
            and reaction.message.channel.id == AUTO_CHANNEL_ID
            and reaction.message.author.id == TARGET_USER_ID
            and isinstance(reaction.emoji, discord.Emoji)
            and reaction.emoji.id == TARGET_EMOJI_ID
            and reaction.count >= REACTION_THRESHOLD
        ):
            await reaction.message.delete()
    except:
        pass

# ================================
# SLASH COMMAND
# ================================
@tree.command(
    name="daily_count",
    description="Delete messages from last 24 hours",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    global daily_deleted_count

    await interaction.response.defer(ephemeral=True)
    daily_deleted_count = 0

    await cleanup_channel_last_24h(interaction.channel)

    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(
            f"🧹 **Manual Cleanup**\n"
            f"📍 <#{interaction.channel.id}>\n"
            f"🗑️ **Deleted `{daily_deleted_count}` messages**"
        )

    await interaction.followup.send(
        f"🗑️ **Deleted `{daily_deleted_count}` messages**",
        ephemeral=True
    )

    daily_deleted_count = 0

# ================================
# RUN
# ================================
client.run(TOKEN)


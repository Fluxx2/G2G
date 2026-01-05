import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone
import pytz

# ================================
# CONFIG
# ================================

DELETE_AFTER = 225  # seconds

ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

TARGET_BOT_IDS = {
    1449623475588436039,
    628400349979344919
}

COUNTDOWN_CHANNEL_ID = 1442370325831487608

LOG_CHANNEL_ID = 1443852961502466090
GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370326460895246

INDIA_TZ = pytz.timezone("Asia/Kolkata")

# ================================
# BOT SETUP
# ================================

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ================================
# COUNTDOWN REACTIONS
# ================================

async def countdown_reactions(message):
    try:
        reactions = [
            "⏳",
            "🕒","🕒","🕒","🕒",
            "🟡","🟡","🟡","🟡",
            "🔴","🔴","🔴","🔴",
            "3️⃣","2️⃣","1️⃣","🗑️"
        ]

        for emoji in reactions:
            await message.add_reaction(emoji)
            await asyncio.sleep(15)

    except:
        pass

# ================================
# DAILY CLEANUP FUNCTION
# ================================

async def cleanup_channel(channel):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24, minutes=30)
    deleted_count = 0

    async for message in channel.history(limit=None):
        if message.author.bot:
            continue
        if message.created_at < cutoff:
            continue
        try:
            await message.delete()
            deleted_count += 1
            await asyncio.sleep(0.4)
        except (discord.NotFound, discord.Forbidden):
            continue

    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(
            f"🧹 **Daily Cleanup Complete**\n"
            f"🏆 todays win **{deleted_count}** in <#{channel.id}>"
        )

# ================================
# MIDNIGHT INDIA TASK
# ================================

async def daily_cleanup_task():
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)

    while not client.is_closed():
        now = datetime.now(INDIA_TZ)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        sleep_seconds = (next_midnight - now).total_seconds()

        await asyncio.sleep(sleep_seconds)

        try:
            await cleanup_channel(channel)
        except Exception as e:
            print(f"Auto cleanup error: {e}")

# ================================
# EVENTS
# ================================

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Slash commands synced")
    client.loop.create_task(daily_cleanup_task())

@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return

    # Countdown reactions for human messages
    if (
        message.channel.id == COUNTDOWN_CHANNEL_ID
        and not message.author.bot
    ):
        asyncio.create_task(countdown_reactions(message))

    # Bot message deletion logic (UNCHANGED)
    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    if message.author.bot and message.author.id in TARGET_BOT_IDS:
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print("Missing permissions to delete message")

# ================================
# SLASH COMMAND
# ================================

@tree.command(
    name="daily_count",
    description="Delete human messages under 24h30m and log count",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await cleanup_channel(interaction.channel)
    await interaction.followup.send(
        "✅ Daily cleanup done. Count posted in log channel.",
        ephemeral=True
    )

# ================================
# RUN BOT
# ================================

client.run(TOKEN)

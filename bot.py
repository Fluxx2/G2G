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

LOG_CHANNEL_ID = 1443852961502466090
GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370326460895246

# Reaction countdown config
REACTION_CHANNEL_ID = 1442370325831487608
REACTION_INTERVAL = 15
REACTION_DURATION = 240
REACTIONS = ["🟢", "🟡", "🔴", "1️⃣5️⃣","⛔"]

IST = pytz.timezone("Asia/Kolkata")

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
# REACTION COUNTDOWN
# ================================

async def reaction_countdown(message: discord.Message):
    if message.author.bot:
        return

    steps = REACTION_DURATION // REACTION_INTERVAL
    last_reaction = None

    for i in range(steps):
        try:
            if last_reaction:
                await message.remove_reaction(last_reaction, client.user)

            reaction = REACTIONS[i % len(REACTIONS)]
            await message.add_reaction(reaction)
            last_reaction = reaction

            await asyncio.sleep(REACTION_INTERVAL)

        except (discord.NotFound, discord.Forbidden):
            break

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
            f"🏆 **{deleted_count} messages deleted** in <#{channel.id}>"
        )

# ================================
# MIDNIGHT (IST) AUTO TASK
# ================================

async def seconds_until_ist_midnight():
    now = datetime.now(IST)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()

async def daily_cleanup_task():
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)

    while not client.is_closed():
        wait_seconds = await seconds_until_ist_midnight()
        await asyncio.sleep(wait_seconds)

        try:
            await cleanup_channel(channel)
        except Exception as e:
            print(f"Auto cleanup error: {e}")

        await asyncio.sleep(60)  # safety buffer

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

    # Bot message deletion
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

    # Reaction countdown for human messages
    if message.channel.id == REACTION_CHANNEL_ID and not message.author.bot:
        client.loop.create_task(reaction_countdown(message))

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
        "✅ Daily cleanup complete. Result posted in log channel.",
        ephemeral=True
    )

# ================================
# RUN BOT
# ================================

client.run(TOKEN)


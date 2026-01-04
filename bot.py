import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone

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
# TIME HELPERS (IST MIDNIGHT)
# ================================

def seconds_until_ist_midnight():
    now_utc = datetime.now(timezone.utc)
    ist = timezone(timedelta(hours=5, minutes=30))
    now_ist = now_utc.astimezone(ist)

    next_midnight_ist = (now_ist + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    return (next_midnight_ist - now_ist).total_seconds()

# ================================
# CLEANUP LOGIC
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
            f"🏆 **todays win `{deleted_count}`** in <#{channel.id}>"
        )

# ================================
# BACKGROUND TASK (IST MIDNIGHT)
# ================================

async def daily_cleanup_task():
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)

    while not client.is_closed():
        try:
            seconds = seconds_until_ist_midnight()
            print(f"Next cleanup in {seconds/3600:.2f} hours (IST midnight)")
            await asyncio.sleep(seconds)

            await cleanup_channel(channel)

            # prevent double run
            await asyncio.sleep(60)

        except Exception as e:
            print(f"Auto cleanup error: {e}")
            await asyncio.sleep(60)

# ================================
# EVENTS
# ================================

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print(f"Slash commands synced to guild {GUILD_ID}")
    client.loop.create_task(daily_cleanup_task())

@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return

    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    if message.author.bot and message.author.id in TARGET_BOT_IDS:
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print(f"Missing permissions in {message.channel.id}")

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
        "✅ Daily cleanup done. Total posted in log channel.",
        ephemeral=True
    )

# ================================
# RUN BOT
# ================================

client.run(TOKEN)

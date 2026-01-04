import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone

# ================================
# CONFIG
# ================================

DELETE_AFTER = 225  # seconds (for bot messages)

# Channels where bot auto-deletes other bot messages
ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

# Bots whose messages should be deleted automatically
TARGET_BOT_IDS = {
    1449623475588436039,
    628400349979344919
}

# Channel where /daily_count report will be posted
LOG_CHANNEL_ID =  1443852961502466090 # <-- Replace with your log channel ID

# ================================
# BOT SETUP
# ================================

TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.message_content = True

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MyClient()

# ================================
# EVENTS
# ================================

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

@client.event
async def on_message(message):
    # Ignore messages from THIS bot
    if message.author.id == client.user.id:
        return

    # Ignore messages NOT in allowed channels
    if message.channel.id not in ALLOWED_CHANNEL_IDS:
        return

    # Only delete messages from selected bots
    if message.author.bot and message.author.id in TARGET_BOT_IDS:
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            print("Missing permissions to delete messages.")

# ================================
# SLASH COMMAND: /daily_count
# ================================

@client.tree.command(
    name="daily_count",
    description="Delete human messages under 24h 30m and log total"
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    channel = interaction.channel
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24, minutes=30)

    deleted_count = 0

    async for message in channel.history(limit=None):
        # ONLY human messages
        if message.author.bot:
            continue

        # ONLY messages within 24h 30m
        if message.created_at < cutoff:
            continue

        try:
            await message.delete()
            deleted_count += 1
            await asyncio.sleep(0.4)  # rate-limit safety
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Missing permission to delete messages.",
                ephemeral=True
            )
            return

    # Send count to log channel
    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(
            f"🧹 **Daily Cleanup Complete**\n"
            f"🗑️ Deleted **{deleted_count} human messages** from <#{channel.id}>\n"
            f"⏱️ Time window: last **24h 30m**"
        )
    else:
        await interaction.followup.send(
            "❌ Log channel not found. Please check LOG_CHANNEL_ID.",
            ephemeral=True
        )

    # Optional

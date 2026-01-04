import discord
import asyncio
import os

# ================================
# CONFIG
# ================================

DELETE_AFTER = 10  # seconds

# ONLY delete messages in these channels
# Enable Developer Mode → Right-click channel → Copy ID
ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

# ONLY delete messages from these bots
# Right-click bot → Copy ID
TARGET_BOT_IDS = {
    1449623475588436039,
    628400349979344919
}

# ================================
# BOT SETUP
# ================================

TOKEN = "MTQ1NzA5MTE4MTIyNDY2MTAwNA.GYfaAQ.4P9lO280AU14SXK3wZpXm0DNq2FNoES1iYnDfw"

# 🔒 SAFETY CHECK (VERY IMPORTANT)
if TOKEN is None:
    raise RuntimeError("DISCORD_TOKEN environment variable is not set")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

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

client.run(TOKEN)


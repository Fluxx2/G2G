import discord
import asyncio
import os

# ================================
# CONFIG
# ================================
DELETE_AFTER = 225

ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

TARGET_BOT_IDS = {
    1457091181224661004,
    628400349979344919,
}

REACTION_CHANNEL_ID = 1442370325831487608
REACTION_INTERVAL = 19
REACTION_DURATION = 250

REACTIONS = [
    "⚪","⚪","⚪",
    "🟢","🟢","🟢",
    "🟡","🟡","🟡",
    "⚠️","‼️","🚨",
    "🚫"
]

# ================================
# BOT SETUP
# ================================
TOKEN = os.getenv("DISCORD_TOKEN_3")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN_3 not set")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)

# ================================
# HELPERS
# ================================
async def reaction_countdown(message):
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

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Cleanup + Reaction Bot logged in as {client.user}")

@client.event
async def on_message(message):

    # Auto-delete specific bots
    if (
        message.author.bot
        and message.author.id in TARGET_BOT_IDS
        and message.channel.id in ALLOWED_CHANNEL_IDS
    ):
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except:
            pass
        return

    if message.author.bot:
        return

    # Reaction countdown
    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

# ================================
# RUN
# ================================
client.run(TOKEN)

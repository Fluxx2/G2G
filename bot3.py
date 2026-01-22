import discord
import asyncio
import os

# ================================
# CONFIG
# ================================
REACTION_CHANNEL_ID = 1442370325831487608
REACTION_INTERVAL = 19
REACTION_DURATION = 250

REACTIONS = [
    "⚪","⚪","⚪",
    "🟢","🟢","🟢",
    "🟡","🟡","🟡",
    "⚠️","‼️","🚨",
    "🔚"
]

# Webhook IDs to react to
TARGET_WEBHOOK_IDS = {
    1463699794286346315,  # Example webhook ID
    222222222222222222,  # Example webhook ID
}

# ================================
# BOT SETUP
# ================================
TOKEN = os.getenv("DISCORD_TOKEN_3")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# ================================
# HELPERS
# ================================
async def reaction_countdown(message):
    steps = REACTION_DURATION // REACTION_INTERVAL
    last = None

    for i in range(steps):
        try:
            # 🛑 stop if message was deleted
            await message.channel.fetch_message(message.id)

            if last:
                await message.remove_reaction(last, client.user)

            emoji = REACTIONS[i % len(REACTIONS)]
            await message.add_reaction(emoji)
            last = emoji

            await asyncio.sleep(REACTION_INTERVAL)

        except discord.NotFound:
            break
        except:
            break

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Reaction Bot logged in as {client.user}")

@client.event
async def on_message(message):
    if message.channel.id != REACTION_CHANNEL_ID:
        return

    # React to target webhooks
    if message.webhook_id and message.webhook_id in TARGET_WEBHOOK_IDS:
        client.loop.create_task(reaction_countdown(message))
        return

    # React to human messages
    if not message.author.bot and not message.webhook_id:
        client.loop.create_task(reaction_countdown(message))

# ================================
# RUN
# ================================
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN_3 not set")

    client.run(TOKEN)

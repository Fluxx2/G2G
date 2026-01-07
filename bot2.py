import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone
import pytz

# ================================
# CONFIG
# ================================
GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370325831487608
LOG_CHANNEL_ID = 1443852961502466090
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

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

# ================================
# HELPERS
# ================================

async def count_today_messages(channel):
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(after=start):
        if not msg.author.bot:
            count += 1
    return count

async def cleanup_channel(channel):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    deleted = 0

    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot:
            continue
        if msg.created_at >= cutoff:
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(1.5)
            except:
                pass

    return deleted

async def seconds_until_ist_midnight():
    now = datetime.now(IST)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()

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
# BACKGROUND TASK
# ================================

async def daily_cleanup_task():
    await client.wait_until_ready()

    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while True:
        await asyncio.sleep(await seconds_until_ist_midnight())

        wins = await count_today_messages(channel)
        await cleanup_channel(channel)

        if log:
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win `{wins}` in** <#{AUTO_CHANNEL_ID}>"
            )

# ================================
# EVENTS
# ================================

@client.event
async def on_ready():
    print(f"✅ Wins Bot logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    client.loop.create_task(daily_cleanup_task())

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # 🔹 Start reaction countdown
    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

    # 🔹 Wins counter
    if message.channel.id == AUTO_CHANNEL_ID:
        total = await count_today_messages(message.channel)

        if total > 0 and total % 10 == 0:
            old = last_win_message.get(message.author.id)
            if old:
                try:
                    await old.delete()
                except:
                    pass

            last_win_message[message.author.id] = await message.channel.send(
                f"{message.author.mention} **wins done today so far ({total})**"
            )

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
    description="Delete human messages 24h+",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    deleted = await cleanup_channel(interaction.channel)

    await interaction.followup.send(
        f"🏆 todays win **{deleted}**",
        ephemeral=True
    )

# ================================
# RUN
# ================================
client.run(TOKEN)

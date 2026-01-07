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
LOG_CHANNEL_ID = 1443852961502466090
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

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
live_total_message = None  # Discord message showing live total

# ================================
# HELPERS
# ================================
async def count_user_messages_today(channel, user):
    """Count human messages by user in channel since IST midnight."""
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if msg.author.id == user.id and not msg.author.bot:
            count += 1
    return count

async def count_total_messages_today(channel):
    """Count all human messages in channel since IST midnight."""
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot:
            count += 1
    return count

async def cleanup_channel(channel):
    """Delete human messages sent BEFORE today's IST midnight (oldest → newest)."""
    ist_midnight = datetime.now(IST).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    deleted = 0
    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot:
            continue

        # Convert message time to IST
        msg_time_ist = msg.created_at.astimezone(IST)

        if msg_time_ist < ist_midnight:
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.7)
            except:
                pass
        else:
            # Stop once we hit messages from today
            break

    return deleted


async def reaction_countdown(message):
    """Cycle reactions on a message."""
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

async def update_live_total():
    """Recount all human messages today and update the live total message."""
    global live_total_message
    log = client.get_channel(LOG_CHANNEL_ID)
    channel = client.get_channel(AUTO_CHANNEL_ID)
    if not log or not channel:
        return

    # Recount all messages every update
    count = await count_total_messages_today(channel)
    content = f"🏆 **Live Wins Today:** `{count}`"

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
    """Update live wins every 60 seconds."""
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            await update_live_total()
        except:
            pass
        await asyncio.sleep(60)  # 1 minute

async def daily_cleanup_task():
    """Runs at IST midnight: deletes old messages, resets counters."""
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while True:
        now = datetime.now(IST)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_midnight - now).total_seconds())

        # Delete live total message
        if live_total_message:
            try:
                await live_total_message.delete()
            except:
                pass

        await cleanup_channel(channel)
        await update_live_total()  # recount after cleanup

        if log:
            total = await count_total_messages_today(channel)
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win `{total}` in** <#{AUTO_CHANNEL_ID}>"
            )

# Initialize live total at startup
async def initialize_live_wins():
    await client.wait_until_ready()
    await update_live_total()

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Wins Bot logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    client.loop.create_task(daily_cleanup_task())
    client.loop.create_task(live_wins_loop())  # 1-min live updates
    client.loop.create_task(initialize_live_wins())

@client.event
async def on_message(message):
    if message.author.bot:
        return

    # Reaction countdown
    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

    # Per-user win messages (every 10 wins)
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
    description="Delete human messages from last 24 hours",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    channel = interaction.channel
    deleted = await cleanup_channel(channel)
    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(
            f"🧹 **Manual Daily Cleanup**\n"
            f"📍 <#{channel.id}>\n"
            f"**🏆 todays win {deleted}**"
        )
    await interaction.followup.send(
        f"**🏆 todays win {deleted}**",
        ephemeral=True
    )

# ================================
# RUN
# ================================
client.run(TOKEN)

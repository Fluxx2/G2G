import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta
import pytz

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

last_win_message = {}  # track last achievement announcement per user
live_total_message = None
daily_deleted_count = 0
last_reset_date = datetime.now(IST).date()

# ================================
# HELPERS
# ================================

def ensure_daily_bucket():
    global daily_deleted_count, last_reset_date
    today = datetime.now(IST).date()
    if today != last_reset_date:
        daily_deleted_count = 0
        last_reset_date = today

async def count_user_messages_today(channel, user):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot and msg.author.id == user.id:
            count += 1
    return count

async def count_total_messages_today(channel):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot:
            count += 1
    return count

async def cleanup_channel(channel):
    """Delete messages sent in the last 24 hours (IST)."""
    global daily_deleted_count
    ensure_daily_bucket()

    now = datetime.now(IST)
    cutoff = now - timedelta(hours=24)  # 24 hours ago

    deleted = 0
    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot:
            continue

        msg_time = msg.created_at.astimezone(IST)
        if cutoff <= msg_time <= now:
            try:
                await msg.delete()
                deleted += 1
                daily_deleted_count += 1
                await asyncio.sleep(0.7)
            except:
                pass
        elif msg_time > now:
            break  # future messages → skip
        else:
            continue  # older than 24h → skip

    return deleted

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
    global live_total_message
    await client.wait_until_ready()

    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while True:
        now = datetime.now(IST)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_midnight - now).total_seconds())

        ensure_daily_bucket()

        if live_total_message:
            try:
                await live_total_message.delete()
            except:
                pass
            live_total_message = None

        # Delete only messages sent in past 24h
        await cleanup_channel(channel)

        if log:
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win {daily_deleted_count} in** <#{AUTO_CHANNEL_ID}>"
            )

        await update_live_total()

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

    # 🔹 User achievement tracking (every 10 messages)
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
            and reaction.message.author.id == TARGET_USER_ID
            and isinstance(reaction.emoji, discord.Emoji)
            and reaction.emoji.id == TARGET_EMOJI_ID
            and reaction.count >= REACTION_THRESHOLD
        ):
            await reaction.message.delete()
    except:
        pass

# ================================
# SLASH COMMANDS
# ================================

@tree.command(
    name="daily_count",
    description="Delete messages sent in the past 24h",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    deleted = await cleanup_channel(interaction.channel)
    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(
            f"🧹 **Manual Daily Cleanup**\n"
            f"📍 <#{interaction.channel.id}>\n"
            f"**🏆 todays win {deleted}**"
        )
    await interaction.followup.send(f"**🏆 todays win {deleted}**", ephemeral=True)

# 🔹 /reset_now — forces daily IST reset for messages in past 24h
@tree.command(
    name="reset_now",
    description="Force delete messages sent in the past 24h and update daily win counts",
    guild=discord.Object(id=GUILD_ID)
)
async def reset_now(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    ensure_daily_bucket()

    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    deleted_count = await cleanup_channel(channel)

    # Update live total after reset
    await update_live_total()

    # Log
    if log:
        await log.send(
            f"⚡ **Manual Reset Executed**\n"
            f"**🏆 todays win {deleted_count} in** <#{AUTO_CHANNEL_ID}>"
        )

    await interaction.followup.send(
        f"✅ Reset complete — `{deleted_count}` messages deleted (past 24h)",
        ephemeral=True
    )

# ================================
# RUN
# ================================
client.run(TOKEN)

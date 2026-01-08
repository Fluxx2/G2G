"""
Wins Bot Features:

1. Live Wins Counter:
   - Tracks all non-bot messages in AUTO_CHANNEL_ID.
   - Updates a live message in LOG_CHANNEL_ID every 60 seconds showing total wins today.

2. Daily Cleanup:
   - Deletes all user messages in AUTO_CHANNEL_ID older than today (IST midnight).
   - Resets the live wins message.
   - Posts a daily cleanup summary in LOG_CHANNEL_ID.

3. Auto-Delete Bot Messages:
   - Deletes any bot message in AUTO_CHANNEL_ID and SECOND_AUTO_CHANNEL_ID
     that is older than 225 seconds.
   - Runs continuously every 15 seconds to catch old messages.

4. User Milestone Announcements:
   - Tracks per-user daily messages in AUTO_CHANNEL_ID.
   - Every 10 messages, announces the milestone in WINS_ANNOUNCE_CHANNEL_ID.
   - Deletes the previous milestone message to avoid spam.

5. Reaction-Based Deletion:
   - Monitors messages from TARGET_USER_ID in AUTO_CHANNEL_ID.
   - Deletes a message if it receives REACTION_THRESHOLD or more reactions of a specific custom emoji.

6. Timezone Handling:
   - All daily resets, counts, and cleanup tasks operate in IST (Asia/Kolkata).

7. Slash Command:
   - /daily_count: manually delete messages before today and log the result.

8. Stability and Safety:
   - Uses try/except to prevent crashes.
   - Skips bot messages where needed.
   - Async tasks prevent blocking.

"""

import discord
import asyncio
import os
from datetime import datetime, timedelta
import pytz
from discord import app_commands

# ================================
# CONFIG
# ================================
GUILD_ID = 1442370324858667041

AUTO_CHANNEL_ID = 1442370325831487608
SECOND_AUTO_CHANNEL_ID = 1449692284596523068
LOG_CHANNEL_ID = 1443852961502466090
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

BOT_AUTO_DELETE_CHANNEL_IDS = {
    AUTO_CHANNEL_ID,
    SECOND_AUTO_CHANNEL_ID
}

TARGET_USER_ID = 906546198754775082
TARGET_EMOJI_ID = 1444022259789467709
REACTION_THRESHOLD = 4

DELETE_BOT_MESSAGES_AFTER = 225  # seconds

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
live_total_message = None

# ================================
# HELPERS
# ================================
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
    ist_midnight = datetime.now(IST).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    deleted = 0
    async for msg in channel.history(limit=None, oldest_first=True):
        if msg.author.bot:
            continue

        if msg.created_at.astimezone(IST) < ist_midnight:
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.7)
            except:
                pass
        else:
            break

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
    await client.wait_until_ready()
    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while True:
        now = datetime.now(IST)
        next_midnight = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        await asyncio.sleep((next_midnight - now).total_seconds())

        if live_total_message:
            try:
                await live_total_message.delete()
            except:
                pass

        await cleanup_channel(channel)
        await update_live_total()

        if log:
            total = await count_total_messages_today(channel)
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win `{total}` in** <#{AUTO_CHANNEL_ID}>"
            )

# -------------------------------
# Auto-delete old bot messages
# -------------------------------
async def auto_delete_old_bot_messages():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.now(tz=pytz.UTC)  # ✅ offset-aware UTC
        for channel_id in BOT_AUTO_DELETE_CHANNEL_IDS:
            channel = client.get_channel(channel_id)
            if not channel:
                continue

            async for msg in channel.history(limit=None, oldest_first=True):
                if not msg.author.bot:
                    continue

                # Check age in seconds
                age = (now - msg.created_at).total_seconds()
                if age >= DELETE_BOT_MESSAGES_AFTER:
                    try:
                        await msg.delete()
                        await asyncio.sleep(0.5)  # small delay to avoid rate limits
                    except:
                        pass

        await asyncio.sleep(15)

# ================================
# EVENTS
# ================================
@client.event
async def on_ready():
    print(f"✅ Wins Bot logged in as {client.user}")
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    client.loop.create_task(live_wins_loop())
    client.loop.create_task(daily_cleanup_task())
    client.loop.create_task(auto_delete_old_bot_messages())

@client.event
async def on_message(message):
    if message.author.bot:
        return

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
            and reaction.message.channel.id == AUTO_CHANNEL_ID
            and reaction.message.author.id == TARGET_USER_ID
            and isinstance(reaction.emoji, discord.Emoji)
            and reaction.emoji.id == TARGET_EMOJI_ID
            and reaction.count >= REACTION_THRESHOLD
        ):
            await reaction.message.delete()
    except:
        pass

# ================================
# SLASH COMMAND
# ================================
@tree.command(
    name="daily_count",
    description="Delete messages before today (IST)",
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

    await interaction.followup.send(
        f"**🏆 todays win {deleted}**",
        ephemeral=True
    )

# ================================
# RUN
# ================================
client.run(TOKEN)

import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta, timezone
import pytz
import re

# ================================
# CONFIG
# ================================
toggle_tasks = {}

MIRROR_SOURCE_CHANNEL_ID = 1442370325831487608
MIRROR_TARGET_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

DELETE_AFTER = 225

ALLOWED_CHANNEL_IDS = {
    1442370325831487608,
    1449692284596523068
}

TARGET_BOT_IDS = {
    1457091181224661004,
    628400349979344919,
}

GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370325831487608
LOG_CHANNEL_ID = 1443852961502466090

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

WINS_SOURCE_CHANNEL_ID = 1442370325831487608
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

CODE_COUNTDOWN_SECONDS = 240
IST = pytz.timezone("Asia/Kolkata")

# ================================
# BOT SETUP
# ================================

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN not set")

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

last_win_message = {}
mirrored_messages = {}

daily_wins = 0
live_wins_message = None

# ================================
# HELPERS
# ================================
async def toggle_code_emoji(source_message_id: int):
    toggle = True

    while True:
        mirrored = mirrored_messages.get(source_message_id)
        if not mirrored:
            return  # stop if original deleted

        for msg in mirrored.values():
            try:
                content = msg.content

                if toggle:
                    content = content.replace("⏳", "🔚")
                else:
                    content = content.replace("🔚", "⏳")

                await msg.edit(content=content)
            except:
                pass

        toggle = not toggle
        await asyncio.sleep(5)


def discord_relative_timestamp(seconds_from_now: int) -> str:
    unix = int(datetime.now(timezone.utc).timestamp()) + seconds_from_now
    return f"<t:{unix}:R>"


async def count_today_messages(channel: discord.TextChannel):
    now = datetime.now(IST)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    count = 0
    async for msg in channel.history(limit=None, after=start):
        if not msg.author.bot:
            count += 1
    return count


async def count_user_messages(channel, user):
    count = 0
    async for msg in channel.history(limit=None):
        if msg.author.id == user.id and not msg.author.bot:
            count += 1
    return count


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


async def cleanup_channel(channel: discord.TextChannel):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=24)

    deleted = 0

    async for msg in channel.history(limit=None, oldest_first=True):
        # ignore bots
        if msg.author.bot:
            continue

        # ✅ delete messages sent WITHIN last 24 hours
        if msg.created_at >= cutoff:
            try:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.4)  # stay rate-limit safe
            except:
                pass

    return deleted





async def seconds_until_ist_midnight():
    now = datetime.now(IST)
    next_midnight = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return (next_midnight - now).total_seconds()


async def update_live_wins():
    global live_wins_message, daily_wins

    log_channel = client.get_channel(LOG_CHANNEL_ID)
    source_channel = client.get_channel(WINS_SOURCE_CHANNEL_ID)

    if not log_channel or not source_channel:
        return

    daily_wins = await count_today_messages(source_channel)
    content = f"🏆 **Live Wins Today:** `{daily_wins}`"

    if live_wins_message:
        try:
            await live_wins_message.edit(content=content)
            return
        except:
            live_wins_message = None

    live_wins_message = await log_channel.send(content)

# ================================
# BACKGROUND TASK
# ================================

async def daily_cleanup_task():
    global daily_wins, live_wins_message
    await client.wait_until_ready()

    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    while not client.is_closed():
        await asyncio.sleep(await seconds_until_ist_midnight())

        if live_wins_message:
            try:
                await live_wins_message.delete()
            except:
                pass
            live_wins_message = None

        await cleanup_channel(channel)

        if log:
            await log.send(
                f"🌙 **Auto Daily Cleanup (IST Midnight)**\n"
                f"**🏆 todays win `{daily_wins}` in** <#{AUTO_CHANNEL_ID}>"
            )

        daily_wins = 0
        await asyncio.sleep(60)

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

    if (
        message.author.bot
        and message.channel.id in ALLOWED_CHANNEL_IDS
        and message.author.id in TARGET_BOT_IDS
    ):
        await asyncio.sleep(DELETE_AFTER)
        try:
            await message.delete()
        except:
            pass
        return

    if message.author.bot:
        return

    if message.channel.id == MIRROR_SOURCE_CHANNEL_ID:
        match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", message.content)
        if match:
            code = match.group(0)
            timer = discord_relative_timestamp(CODE_COUNTDOWN_SECONDS)
            formatted = (
                f"# `     {code}     `\n"
                f"⏳ {timer}"
            )


            mirrored_messages[message.id] = {}

            for cid in MIRROR_TARGET_CHANNEL_IDS:
                ch = client.get_channel(cid)
                if ch:
                    mirrored_messages[message.id][cid] = await ch.send(formatted)
                    if message.id not in toggle_tasks:
                        toggle_tasks[message.id] = client.loop.create_task(
                            toggle_code_emoji(message.id)
                        )

    if message.channel.id == REACTION_CHANNEL_ID:
        client.loop.create_task(reaction_countdown(message))

    if message.channel.id == WINS_SOURCE_CHANNEL_ID:
        await update_live_wins()

        total = await count_user_messages(message.channel, message.author)

        if total > 0 and total % 10 == 0:
            announce = client.get_channel(WINS_ANNOUNCE_CHANNEL_ID)
            old = last_win_message.get(message.author.id)
            if old:
                try:
                    await old.delete()
                except:
                    pass
            last_win_message[message.author.id] = await announce.send(
                f"{message.author.mention} **wins done today so far ({total})**"
            )


@client.event
async def on_message_edit(before, after):
    mirrored = mirrored_messages.get(after.id)
    if not mirrored:
        return

    match = re.search(r"\b[a-zA-Z0-9]{5,6}\b", after.content)
    if not match:
        return

    timer = discord_relative_timestamp(CODE_COUNTDOWN_SECONDS)
    formatted = (
        f"# `     {match.group(0)}     `\n"
        f"⏳ {timer}"
    )


    for msg in mirrored.values():
        try:
            await msg.edit(content=formatted)
        except:
            pass


@client.event
async def on_message_delete(message):
    mirrored = mirrored_messages.pop(message.id, None)
    if not mirrored:
        return

    # Cancel the emoji toggle task for this message
    task = toggle_tasks.pop(message.id, None)
    if task:
        task.cancel()

    for msg in mirrored.values():
        try:
            await msg.delete()
        except:
            pass


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
    description="Delete human messages 24h+ and everything after",
    guild=discord.Object(id=GUILD_ID)
)
async def daily_count(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        channel = await client.fetch_channel(interaction.channel_id)
    except:
        await interaction.followup.send(
            "❌ Failed to fetch channel from Discord API.",
            ephemeral=True
        )
        return

    if not isinstance(channel, discord.TextChannel):
        await interaction.followup.send(
            "❌ This command must be used in a text channel.",
            ephemeral=True
        )
        return

    perms = channel.permissions_for(channel.guild.me)
    if not (
        perms.view_channel
        and perms.read_message_history
        and perms.manage_messages
    ):
        await interaction.followup.send(
            "❌ Missing permissions: View Channel / Read History / Manage Messages",
            ephemeral=True
        )
        return

    deleted = await cleanup_channel(channel)

    log = client.get_channel(LOG_CHANNEL_ID)
    if log:
        await log.send(
            f"🧹 **Manual Daily Cleanup**\n"
            f"📍 <#{channel.id}>\n"
            f"🏆 todays win **{deleted}**"
        )

    # ✅ THIS WAS THE BROKEN LINE — NOW CLOSED PROPERLY
    await interaction.followup.send(
        f"🏆 todays win **{deleted}**",
        ephemeral=True
    )



# ================================
# RUN
# ================================

try:
    client.run(TOKEN)
except discord.HTTPException as e:
    if e.status == 429:
        print("Hit Discord global rate limit. Wait before restarting.")
    else:
        raise









import discord
import asyncio
import os
from discord import app_commands
from datetime import datetime, timedelta
import pytz
from discord.errors import DiscordServerError

# ================================
# CONFIG
# ================================
GUILD_ID = 1442370324858667041
AUTO_CHANNEL_ID = 1442370325831487608
SECOND_AUTO_CHANNEL_ID = 1449692284596523068
LOG_CHANNEL_ID = 1443852961502466090
WINS_ANNOUNCE_CHANNEL_ID = 1457687458954350783

# Include webhook IDs here too
TARGET_USER_IDS = {
    906546198754775082,     # human
    1252645184777359391,    # human
    1463699794286346315,    # example webhook
    222222222222222222,     # example webhook
}

TARGET_EMOJI_ID = 1444022259789467709
REACTION_THRESHOLD = 4

IST = pytz.timezone("Asia/Kolkata")

ALLOWED_ROLE_IDS = {
    1442370325215182852,
    1442370325215182851,
    1442370325215182849,
    1442370325215182848,
}

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
daily_deleted_count = 0
last_reset_date = datetime.now(IST).date()

# ================================
# HELPERS
# ================================

def is_authorized(interaction: discord.Interaction) -> bool:
    member = interaction.user

    if interaction.guild and member.id == interaction.guild.owner_id:
        return True

    if member.guild_permissions.administrator:
        return True

    return any(role.id in ALLOWED_ROLE_IDS for role in member.roles)

def ensure_daily_bucket():
    global daily_deleted_count, last_reset_date
    today = datetime.now(IST).date()
    if today != last_reset_date:
        daily_deleted_count = 0
        last_reset_date = today

async def count_user_messages_today(channel, user):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    try:
        async for msg in channel.history(limit=None, after=start):
            # Include webhooks
            if msg.author.bot:
                if msg.webhook_id and msg.author.id == user.id:
                    count += 1
            else:
                if msg.author.id == user.id:
                    count += 1
    except DiscordServerError:
        pass
    return count

async def count_total_messages_today(channel):
    start = datetime.now(IST).replace(hour=0, minute=0, second=0, microsecond=0)
    count = 0
    try:
        async for msg in channel.history(limit=None, after=start):
            if msg.author.bot:
                if msg.webhook_id:
                    count += 1
            else:
                count += 1
    except DiscordServerError:
        pass
    return count

async def cleanup_channel(channel):
    global daily_deleted_count
    ensure_daily_bucket()

    now = datetime.now(IST)
    cutoff = now - timedelta(hours=24)

    deleted = 0
    try:
        async for msg in channel.history(limit=None, oldest_first=True):
            # Ignore normal bots but NOT webhooks
            if msg.author.bot and not msg.webhook_id:
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
    except DiscordServerError:
        pass

    return deleted

async def update_live_total():
    global live_total_message
    log = client.get_channel(LOG_CHANNEL_ID)
    channel = client.get_channel(AUTO_CHANNEL_ID)
    if not log or not channel:
        return

    try:
        total = await count_total_messages_today(channel)
    except DiscordServerError:
        return

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
        try:
            await update_live_total()
        except DiscordServerError:
            pass
        except Exception:
            pass

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
    # Include webhooks in message handling
    if message.author.bot and not message.webhook_id:
        return  # ignore regular bots

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

            # ✅ REQUIRED CHANGE
            # Ping humans, show webhook name only
            if message.webhook_id:
                display = f"**{message.author.name}**"
            else:
                display = message.author.mention  # pings human

            last_win_message[message.author.id] = await announce.send(
                f"🏆 {display} **wins done today so far ({user_total})**"
            )


@client.event
async def on_reaction_add(reaction, user):
    try:
        if (
            reaction.message.author.id in TARGET_USER_IDS
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
    if not is_authorized(interaction):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

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

@tree.command(
    name="reset_now",
    description="Force delete messages sent in the past 24h",
    guild=discord.Object(id=GUILD_ID)
)
async def reset_now(interaction: discord.Interaction):
    if not is_authorized(interaction):
        await interaction.response.send_message(
            "❌ You do not have permission to use this command.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    ensure_daily_bucket()

    channel = client.get_channel(AUTO_CHANNEL_ID)
    log = client.get_channel(LOG_CHANNEL_ID)

    deleted_count = await cleanup_channel(channel)
    await update_live_total()

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


import discord

TOKEN = "PASTE THE SAME TOKEN HERE TEMPORARILY"

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    print("SUCCESS:", client.user)

client.run(TOKEN)

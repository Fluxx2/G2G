import discord

TOKEN = "MTQ1NzA5MTE4MTIyNDY2MTAwNA.GYfaAQ.4P9lO280AU14SXK3wZpXm0DNq2FNoES1iYnDfw"

client = discord.Client(intents=discord.Intents.default())

@client.event
async def on_ready():
    print("SUCCESS:", client.user)

client.run(TOKEN)

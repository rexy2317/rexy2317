import discord
from discord.ext import commands
import os

bot = commands.Bot(intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(f"Connesso come {bot.user}")

@bot.slash_command(name="ciao")
async def ciao(ctx):
    await ctx.respond("Ciao! Funziono 🎉")

TOKEN = os.getenv("DISCORD_TOKEN")
bot.run(TOKEN)

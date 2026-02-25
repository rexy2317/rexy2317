import discord
from discord.ext import commands
import os

# ================= CONFIG =================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Token non trovato nelle variabili ambiente!")

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True  # necessario se vuoi leggere messaggi
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= EVENTI =================
@bot.event
async def on_ready():
    print(f"✅ Bot connesso come {bot.user}")
    print("Pronto a ricevere comandi slash su tutti i server!")

# ================= COMANDI SLASH =================
@bot.slash_command(name="ciao", description="Risponde che funziona")
async def ciao(ctx: discord.ApplicationContext):
    await ctx.respond("Ciao Piz 🎉")

# ================= AVVIO =================
bot.run(TOKEN)




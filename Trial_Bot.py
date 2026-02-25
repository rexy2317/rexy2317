import discord
from discord.ext import commands
import os

# ================= CONFIG =================
# Prendi il token direttamente dalle variabili d'ambiente
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("Token non trovato nelle variabili ambiente!")

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True  # se vuoi leggere i messaggi in futuro

bot = commands.Bot(command_prefix="!", intents=intents)

# ================= EVENTI =================
@bot.event
async def on_ready():
    # Sincronizza i comandi slash al login
    await bot.tree.sync(guild=discord.Object())
    print(f"✅ Bot connesso come {bot.user}")
    print("Slash commands sincronizzati sul server di test.")

# ================= COMANDI SLASH =================
@bot.tree.command(name="ciao", description="Risponde che funziona",)
async def ciao(interaction: discord.Interaction):
    await interaction.response.send_message("Ciao Piz 🎉")

# ================= AVVIO =================
bot.run(TOKEN)



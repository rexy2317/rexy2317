import discord
from discord.ext import commands
import os

# Prendi il token direttamente dalle variabili d'ambiente
TOKEN = os.environ["DISCORD_TOKEN"]

# Intents di base
intents = discord.Intents.default()

# Bot unico per Py-cord (comandi classici opzionali)
bot = commands.Bot(command_prefix="!", intents=intents)

# Evento on_ready
@bot.event
async def on_ready():
    # Sincronizza i comandi slash al login
    await bot.tree.sync()
    print(f"Connesso come {bot.user}")

# Comando slash /ciao
@bot.tree.command(name="ciao", description="Risponde che funziona")
async def ciao(interaction: discord.Interaction):
    await interaction.response.send_message("Ciao Piz 🎉")

# Avvia il bot
bot.run(TOKEN)



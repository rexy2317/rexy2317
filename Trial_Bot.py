import discord
from discord.ext import commands
from discord import app_commands
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="\\", intents=intents)

# Definizione del comando slash
class MyClient(discord.Client):
    def __init__(self, *, intents):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

client = MyClient(intents=intents)

@client.event
async def on_ready():
    await client.tree.sync()  # sincronizza i comandi slash
    print(f"Connesso come {client.user}")

# Definizione comando slash
@client.tree.command(name="ciao", description="Risponde che funziona")
async def ciao(interaction: discord.Interaction):
    await interaction.response.send_message("Ciao Piz")

TOKEN = os.getenv("DISCORD_TOKEN")
client.run(TOKEN)



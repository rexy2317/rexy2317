import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import ast
import operator
import math

# ================= CONFIG =================
TOKEN = os.getenv("TOKEN")
if TOKEN is None:
    raise ValueError("Token non trovato nelle variabili ambiente!")
    
DATA_FILE = "/mnt/data/counting_data.json"

# ================= CARICAMENTO DATI =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            guild_data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ JSON corrotto! Inizializzo vuoto.")
            guild_data = {}
else:
    guild_data = {}

last_user = {}  # salva ultimo utente per ogni server

def save_data():
    tmp_file = DATA_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(guild_data, f, indent=4)
    os.replace(tmp_file, DATA_FILE)

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CALCOLATORE SICURO =================
operators = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

allowed_funcs = {
    "sqrt": math.sqrt,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
    "pow": math.pow,
}

def eval_expr(expr):
    def _eval(node):
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in operators:
                raise ValueError("Operatore non permesso")
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.Call):
            func_name = node.func.id
            if func_name not in allowed_funcs:
                raise ValueError("Funzione non permessa")
            args = [_eval(arg) for arg in node.args]
            return allowed_funcs[func_name](*args)
        else:
            raise ValueError("Espressione non valida")
    
    node = ast.parse(expr, mode="eval").body
    return _eval(node)

# ================= EVENTI =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot online come {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)

    # se server nuovo, inizializza i dati
    if guild_id not in guild_data:
        guild_data[guild_id] = {
            "current": 0,
            "record": 0,
            "channel": None
        }
        save_data()

    data = guild_data[guild_id]

    # se il canale non è ancora impostato, ignoriamo
    if not data["channel"] or message.channel.id != data["channel"]:
        return

    # prova a calcolare numero/calcolo
    try:
        result = eval_expr(message.content.replace(" ", ""))
        result = int(result)
    except Exception:
        return  # messaggio non valido → ignorato

    expected = data["current"] + 1

    # ===== NUMERO CORRETTO =====
    if result == expected:
        # blocco doppio turno
        if last_user.get(guild_id) == message.author.id:
            await message.channel.send(
                f"❌ {message.author.mention} non puoi contare due volte! Reset."
            )
            data["current"] = 0
            last_user[guild_id] = None
            save_data()
            return

        data["current"] = result
        last_user[guild_id] = message.author.id

        # aggiorna record se necessario
        new_record = False
        if result > data["record"]:
            data["record"] = result
            new_record = True

        # reazione sempre per nuovo record
        if new_record:
            await message.add_reaction("🏆")
            if result % 10 == 0:
                await message.channel.send(f"🏆 Nuovo record: **{result}**!")

        await message.add_reaction("✅")

    # ===== ERRORE =====
    else:
        await message.add_reaction("❌")
        await message.channel.send(
            f"💥 Sbagliato! Era **{expected}**.\nSi riparte da **1**."
        )
        data["current"] = 0
        last_user[guild_id] = None

    save_data()
    await bot.process_commands(message)

# ================= SLASH COMMANDS =================
@bot.tree.command(
    name="setcounting",
    description="Imposta questo canale come counting",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.checks.has_permissions(administrator=True)
async def setcounting(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)

    # crea o aggiorna la voce del server
    guild_data[guild_id] = {
        "current": guild_data.get(guild_id, {}).get("current", 0),
        "record": guild_data.get(guild_id, {}).get("record", 0),
        "channel": interaction.channel.id
    }

    save_data()
    await interaction.response.send_message("✅ Canale counting impostato!")

@bot.tree.command(
    name="count",
    description="Mostra il numero attuale",
    guild=discord.Object(id=GUILD_ID)
)
async def count(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_data:
        await interaction.response.send_message(
            "⚠️ Counting non configurato. Usa /setcounting",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"🔢 Numero attuale: **{guild_data[guild_id]['current']}**"
    )

@bot.tree.command(
    name="record",
    description="Mostra il record del server",
    guild=discord.Object(id=GUILD_ID)
)
async def record(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    if guild_id not in guild_data:
        await interaction.response.send_message(
            "⚠️ Counting non configurato.",
            ephemeral=True,
        )
        return
    await interaction.response.send_message(
        f"🏆 Record massimo: **{guild_data[guild_id]['record']}**"
    )

@bot.tree.command(
    name="reset",
    description="Resetta il counting",
    guild=discord.Object(id=GUILD_ID)
)
@app_commands.checks.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    guild_data[guild_id]["current"] = 0
    last_user[guild_id] = None
    save_data()
    await interaction.response.send_message("🔄 Counting resettato!")

# ================= AVVIO =================
bot.run(TOKEN)



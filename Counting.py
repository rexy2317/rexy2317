import discord
from discord.ext import commands
import os
import json
import ast
import operator
import math

# ================= CONFIG =================
TOKEN = os.environ.get("DISCORD_TOKEN")
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
    print(f"✅ Bot connesso come {bot.user}")
    print("Slash commands sincronizzati globalmente.")

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
            "channel": None,
            "user_counts": {}
        }
        save_data()

    data = guild_data[guild_id]

    # se il canale non è impostato o non è quello corretto, ignoriamo
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

        # aggiorna contributo utente
        data["user_counts"][str(message.author.id)] = data["user_counts"].get(str(message.author.id), 0) + 1

        # aggiorna record
        if result > data["record"]:
            data["record"] = result
            await message.add_reaction("🏆")

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

# ================= COMANDI SLASH =================
@bot.tree.command(name="setcounting", description="Imposta questo canale come counting")
async def setcounting(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id, {"current":0,"record":0,"user_counts":{}})

    data["channel"] = ctx.channel.id
    guild_data[guild_id] = data
    save_data()
    await ctx.respond("✅ Canale counting impostato!")

@bot.tree.command(name="count", description="Mostra il numero attuale")
async def count(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("channel"):
        await ctx.respond("⚠️ Counting non configurato. Usa /setcounting", ephemeral=True)
        return
    await ctx.respond(f"🔢 Numero attuale: **{data['current']}**")

@bot.tree.command(name="record", description="Mostra il record del server")
async def record(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("channel"):
        await ctx.respond("⚠️ Counting non configurato.", ephemeral=True)
        return
    await ctx.respond(f"🏆 Record massimo: **{data['record']}**")

@bot.tree.command(name="reset", description="Resetta il counting")
async def reset(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data:
        await ctx.respond("⚠️ Counting non configurato.", ephemeral=True)
        return
    data["current"] = 0
    last_user[guild_id] = None
    save_data()
    await ctx.respond("🔄 Counting resettato!")

@bot.tree.command(name="top10", description="Mostra i primi 10 utenti per contributi")
async def top10(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("user_counts"):
        await ctx.respond("⚠️ Nessun contributo ancora registrato.", ephemeral=True)
        return

    sorted_users = sorted(data["user_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
    description = ""
    for i, (user_id, count) in enumerate(sorted_users, start=1):
        user = ctx.guild.get_member(int(user_id))
        name = user.display_name if user else f"Utente {user_id}"
        description += f"**{i}. {name}** — {count} punti\n"

    await ctx.respond(f"🏆 **Classifica Counting**\n{description}")

# ================= AVVIO =================
bot.run(TOKEN)

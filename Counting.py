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

# Railway volume persistente
DATA_FILE = "/mnt/data/counting_data.json"

# ================= CARICAMENTO DATI =================
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            guild_data = json.load(f)
    except json.JSONDecodeError:
        print("⚠️ JSON corrotto, ricreo file.")
        guild_data = {}
else:
    guild_data = {}

last_user = {}

def save_data():
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(guild_data, f, indent=4)
    os.replace(tmp, DATA_FILE)

# ================= BOT =================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(intents=intents)

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
                raise ValueError
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.Call):
            name = node.func.id
            if name not in allowed_funcs:
                raise ValueError
            args = [_eval(a) for a in node.args]
            return allowed_funcs[name](*args)
        raise ValueError

    node = ast.parse(expr, mode="eval").body
    return _eval(node)

# ================= EVENTI =================
@bot.event
async def on_ready():
    await bot.sync_commands()  # GLOBAL COMMANDS
    print(f"✅ Online come {bot.user}")
    print("🌍 Slash commands globali sincronizzati")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)

    if guild_id not in guild_data:
        guild_data[guild_id] = {
            "current": 0,
            "record": 0,
            "channel": None
        }
        save_data()

    data = guild_data[guild_id]

    if not data["channel"] or message.channel.id != data["channel"]:
        return

    try:
        result = int(eval_expr(message.content.replace(" ", "")))
    except Exception:
        return

    expected = data["current"] + 1

    # ===== CORRETTO =====
    if result == expected:

        if last_user.get(guild_id) == message.author.id:
            await message.channel.send(
                f"❌ {message.author.mention} non puoi contare due volte!"
            )
            data["current"] = 0
            last_user[guild_id] = None
            save_data()
            return

        data["current"] = result
        last_user[guild_id] = message.author.id

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

# ================= SLASH COMMANDS =================

@bot.slash_command(name="setcounting", description="Imposta il canale counting")
async def setcounting(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)

    guild_data[guild_id] = {
        "current": guild_data.get(guild_id, {}).get("current", 0),
        "record": guild_data.get(guild_id, {}).get("record", 0),
        "channel": ctx.channel.id
    }

    save_data()
    await ctx.respond("✅ Canale counting impostato!")

@bot.slash_command(name="count", description="Mostra il numero attuale")
async def count(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)

    if guild_id not in guild_data:
        await ctx.respond("⚠️ Counting non configurato.", ephemeral=True)
        return

    await ctx.respond(
        f"🔢 Numero attuale: **{guild_data[guild_id]['current']}**"
    )

@bot.slash_command(name="record", description="Mostra il record")
async def record(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)

    if guild_id not in guild_data:
        await ctx.respond("⚠️ Counting non configurato.", ephemeral=True)
        return

    await ctx.respond(
        f"🏆 Record massimo: **{guild_data[guild_id]['record']}**"
    )

@bot.slash_command(name="reset", description="Resetta il counting")
@commands.has_permissions(administrator=True)
async def reset(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)

    guild_data[guild_id]["current"] = 0
    last_user[guild_id] = None
    save_data()

    await ctx.respond("🔄 Counting resettato!")

# ================= AVVIO =================
bot.run(TOKEN)


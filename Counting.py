import discord
from discord.ext import commands
import os
import json
import ast
import operator
import math

# ================= CONFIG =================
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
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
        if isinstance(node, ast.Constant):
            return node.value
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
    print(f"✅ Bot connesso come {bot.user}")
    print("Slash commands Py-Cord pronti.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    guild_id = str(message.guild.id)

    if guild_id not in guild_data:
        guild_data[guild_id] = {"current":0,"record":0,"channel":None,"user_counts":{}}
        save_data()

    data = guild_data[guild_id]

    if not data["channel"] or message.channel.id != data["channel"]:
        return

    try:
        result = eval_expr(message.content.replace(" ", ""))
        result = int(result)
    except Exception:
        return

    expected = data["current"] + 1

    if result == expected:
        # Controllo doppio conteggio
        if last_user.get(guild_id) == message.author.id:
            await message.channel.send(
                f"❌ {message.author.mention} non puoi contare due volte! Reset."
            )
            data["current"] = 0
            last_user[guild_id] = None
            await message.add_reaction("💥")
            save_data()
            return

        # Aggiornamento numero corrente
        data["current"] = result
        last_user[guild_id] = message.author.id
        data["user_counts"][str(message.author.id)] = data["user_counts"].get(str(message.author.id),0)+1

        # Reazioni
        await message.add_reaction("✅")  # ✅ per ogni numero corretto
        if result > data["record"]:
            data["record"] = result
            await message.add_reaction("🏆")  # 🏆 nuovo record

        # Messaggio speciale per multipli di 10
        if result % 10 == 0:
            await message.channel.send(f"🎉 Wow! Il counting ha raggiunto **{result}**! Continua così! 🎉")

    else:
        # Numero sbagliato
        await message.add_reaction("❌")
        await message.channel.send(f"💥 Sbagliato! Era **{expected}**.\nSi riparte da **1**.")
        data["current"] = 0
        last_user[guild_id] = None

    save_data()
    await bot.process_commands(message)

# ================= SLASH COMMANDS =================
@bot.slash_command(name="setcounting", description="Imposta questo canale come counting")
async def setcounting(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id, {"current":0,"record":0,"user_counts":{}})
    data["channel"] = ctx.channel.id
    guild_data[guild_id] = data
    save_data()
    await ctx.respond("✅ Canale counting impostato!")

@bot.slash_command(name="count", description="Mostra il numero attuale")
async def count(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("channel"):
        await ctx.respond("⚠️ Counting non configurato. Usa /setcounting", ephemeral=True)
        return
    await ctx.respond(f"🔢 Numero attuale: **{data['current']}**")

@bot.slash_command(name="record", description="Mostra il record del server")
async def record(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("channel"):
        await ctx.respond("⚠️ Counting non configurato.", ephemeral=True)
        return
    await ctx.respond(f"🏆 Record massimo: **{data['record']}**")

@bot.slash_command(name="reset", description="Resetta il counting")
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

@bot.slash_command(name="top10", description="Mostra i primi 10 utenti per contributi")
async def top10(ctx: discord.ApplicationContext):
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data or not data.get("user_counts"):
        await ctx.respond("⚠️ Nessun contributo registrato.", ephemeral=True)
        return

    sorted_users = sorted(data["user_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
    description = ""
    for i, (user_id, count) in enumerate(sorted_users, start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"Utente {user_id}"
        description += f"**{i}. {name}** — {count} punti\n"

    await ctx.respond(f"🏆 **Classifica Counting**\n{description}")

@bot.slash_command(name="info", description="Mostra informazioni sui comandi del bot di counting")
async def info(ctx: discord.ApplicationContext):
    embed = discord.Embed(
        title="ℹ️ Info Bot Counting",
        description="Questo bot ti permette di giocare al counting in questo server. Ecco i comandi disponibili e le regole principali:",
        color=0x00ff00
    )

    embed.add_field(
        name="✅ /setcounting",
        value="Imposta il canale corrente come canale di counting. Solo qui i numeri saranno validi.",
        inline=False
    )
    embed.add_field(
        name="🔢 /count",
        value="Mostra il numero corrente da contare.",
        inline=False
    )
    embed.add_field(
        name="🏆 /record",
        value="Mostra il record massimo raggiunto nel counting di questo server.",
        inline=False
    )
    embed.add_field(
        name="🔄 /reset",
        value="Resetta il counting a 0. Utile in caso di errori o per ricominciare.",
        inline=False
    )
    embed.add_field(
        name="🥇 /top10",
        value="Mostra la classifica dei primi 10 utenti con più conteggi validi.",
        inline=False
    )
    embed.add_field(
        name="📜 Regole principali",
        value="- I numeri devono essere inviati in ordine crescente, partendo da 1.\n"
              "- Non puoi contare due volte di seguito.\n"
              "- Puoi usare espressioni matematiche semplici (es: `2+1`, `sqrt(9)`).",
        inline=False
    )

    await ctx.respond(embed=embed)

# ================= AVVIO =================
bot.run(TOKEN)

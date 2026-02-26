import discord
from discord.ext import commands
import os
import json
import ast
import operator
import math

# ================= CONFIGURAZIONE =================
TOKEN = os.environ.get("DISCORD_TOKEN")
DATA_FILE = "counting_data.json"

# ================= GESTIONE DATI =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            guild_data = json.load(f)
        except:
            guild_data = {}
else:
    guild_data = {}

last_user = {}  # ultimo utente che ha contato per server

def save_data():
    """Salva i dati correnti nel file JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(guild_data, f, indent=4)

# ================= INIZIALIZZAZIONE BOT =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CALCOLATORE SICURO =================
operators = {
    ast.Add: operator.add, ast.Sub: operator.sub, 
    ast.Mult: operator.mul, ast.Div: operator.truediv, 
    ast.Pow: operator.pow, ast.USub: operator.neg
}
allowed_funcs = {
    "sqrt": math.sqrt, "log": math.log, 
    "log10": math.log10, "exp": math.exp, "pow": math.pow
}

def eval_expr(expr):
    """Valuta stringhe matematiche senza usare eval() insicuro."""
    def _eval(node):
        if isinstance(node, ast.Constant): 
            return node.value
        elif isinstance(node, ast.BinOp):
            return operators[type(node.op)](_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            return operators[type(node.op)](_eval(node.operand))
        elif isinstance(node, ast.Call):
            args = [_eval(arg) for arg in node.args]
            return allowed_funcs[node.func.id](*args)
        raise ValueError("Operazione non permessa")
    return _eval(ast.parse(expr, mode="eval").body)

# ================= EVENTI =================
@bot.event
async def on_ready():
    print(f"✅ Bot Counting Online come {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return

    guild_id = str(message.guild.id)
    if guild_id not in guild_data:
        guild_data[guild_id] = {
            "current": 0, "record": 0, "channel": None,
            "user_counts": {}, "user_errors": {},
            "user_streak": {}, "user_maxcombo": {}
        }

    data = guild_data[guild_id]

    if not data.get("channel") or message.channel.id != data["channel"]:
        return

    try:
        result = int(round(eval_expr(message.content.replace(" ", ""))))
    except:
        return

    expected = data["current"] + 1

    # ---------- ERRORE ----------
    if result != expected:
        await message.channel.send(f"💥 {message.author.mention} ha scritto **{result}**, doveva essere **{expected}**. Reset a 1!")
        data["current"] = 0
        last_user[guild_id] = None

        # Incrementa errori utente
        uid = str(message.author.id)
        data["user_errors"][uid] = data["user_errors"].get(uid,0)+1
        # Reset streak
        data["user_streak"][uid] = 0

        try: await message.add_reaction("❌")
        except: pass

    # ---------- DOPPIO MESSAGGIO ----------
    elif last_user.get(guild_id) == message.author.id:
        await message.channel.send(f"❌ {message.author.mention}, non puoi contare due volte di fila! Reset a 1.")
        data["current"] = 0
        last_user[guild_id] = None

        uid = str(message.author.id)
        data["user_errors"][uid] = data["user_errors"].get(uid,0)+1
        data["user_streak"][uid] = 0
        try: await message.add_reaction("⚠️")
        except: pass

    # ---------- NUMERO CORRETTO ----------
    else:
        data["current"] = result
        last_user[guild_id] = message.author.id

        uid = str(message.author.id)
        data["user_counts"][uid] = data["user_counts"].get(uid,0)+1
        data["user_streak"][uid] = data["user_streak"].get(uid,0)+1

        # Aggiorna combo massima
        data["user_maxcombo"][uid] = max(data["user_streak"][uid], data["user_maxcombo"].get(uid,0))

        try: await message.add_reaction("✅")
        except: pass

        # Nuovo record globale
        if result > data["record"]:
            data["record"] = result
            try: await message.add_reaction("🏆")
            except: pass
            if result % 10 == 0:
                await message.channel.send(f"🎉 Nuovo Record Server: **{result}**!")

    save_data()
    await bot.process_commands(message)

# ================= COMANDI SLASH =================
@bot.slash_command(name="setcounting", description="Imposta il canale attuale per il counting")
async def setcounting(ctx):
    guild_id = str(ctx.guild.id)
    guild_data.setdefault(guild_id, {"current":0,"record":0,"channel":None,"user_counts":{}, "user_errors":{}, "user_streak":{}, "user_maxcombo":{}})
    guild_data[guild_id]["channel"] = ctx.channel.id
    save_data()
    await ctx.respond(f"✅ Canale {ctx.channel.mention} configurato per il Counting!")

@bot.slash_command(name="count", description="Mostra il numero attuale")
async def count(ctx):
    data = guild_data.get(str(ctx.guild.id), {"current":0})
    await ctx.respond(f"🔢 Numero attuale: **{data['current']}**. Prossimo: **{data['current']+1}**")

@bot.slash_command(name="record", description="Mostra il record del server")
async def record(ctx):
    data = guild_data.get(str(ctx.guild.id), {"record":0})
    await ctx.respond(f"🏆 Record massimo: **{data['record']}**")

@bot.slash_command(name="top10", description="Mostra i top 10 utenti")
async def top10(ctx):
    data = guild_data.get(str(ctx.guild.id), {"user_counts":{}})
    sorted_users = sorted(data["user_counts"].items(), key=lambda x:x[1], reverse=True)[:10]
    description = ""
    for i,(uid,count) in enumerate(sorted_users,1):
        description += f"**{i}.** <@{uid}> — `{count}` punti\n"
    embed = discord.Embed(title="🏆 Top 10 Counting", description=description, color=0x3498db)
    await ctx.respond(embed=embed)

@bot.slash_command(name="top10errors", description="Mostra i top 10 errori")
async def top10errors(ctx):
    data = guild_data.get(str(ctx.guild.id), {"user_errors":{}})
    sorted_users = sorted(data["user_errors"].items(), key=lambda x:x[1], reverse=True)[:10]
    if not sorted_users:
        return await ctx.respond("😇 Nessun errore registrato.")
    description = ""
    for i,(uid,count) in enumerate(sorted_users,1):
        description += f"**{i}.** <@{uid}> — `{count}` errori\n"
    embed = discord.Embed(title="🤡 Top 10 Errori", description=description, color=0xe74c3c)
    await ctx.respond(embed=embed)

@bot.slash_command(name="stats", description="Mostra le statistiche di un utente")
async def stats(ctx, member: discord.Member):
    guild_id = str(ctx.guild.id)
    uid = str(member.id)
    data = guild_data.get(guild_id, {})
    streak = data.get("user_streak",{}).get(uid,0)
    maxcombo = data.get("user_maxcombo",{}).get(uid,0)
    errors = data.get("user_errors",{}).get(uid,0)

    # Posizione nella classifica
    counts = data.get("user_counts",{})
    sorted_users = sorted(counts.items(), key=lambda x:x[1], reverse=True)
    position = next((i+1 for i,(u,c) in enumerate(sorted_users) if u==uid), "-")

    embed = discord.Embed(title=f"📊 Statistiche {member.display_name}", color=0x00ff00)
    embed.add_field(name="👑 Streak attuale", value=str(streak), inline=True)
    embed.add_field(name="🔥 Combo max senza errori", value=str(maxcombo), inline=True)
    embed.add_field(name="❌ Errori totali", value=str(errors), inline=True)
    embed.add_field(name="🥇 Posizione classifica", value=str(position), inline=True)
    await ctx.respond(embed=embed)

@bot.slash_command(name="resetall", description="Reset totale (corrente, record e punti) - Solo Counting Admin")
async def resetall(ctx):
    role_name = "Counting Admin"
    if not any(role.name==role_name for role in ctx.author.roles):
        return await ctx.respond(f"❌ Devi avere il ruolo `{role_name}`.", ephemeral=True)

    guild_id = str(ctx.guild.id)
    if guild_id in guild_data:
        guild_data[guild_id]["current"]=0
        guild_data[guild_id]["record"]=0
        guild_data[guild_id]["user_counts"]={}
        guild_data[guild_id]["user_errors"]={}
        guild_data[guild_id]["user_streak"]={}
        guild_data[guild_id]["user_maxcombo"]={}
        last_user[guild_id]=None
        save_data()
        await ctx.respond("🔄 Reset Totale effettuato!")

@bot.slash_command(name="info", description="Mostra info sul bot")
async def info(ctx):
    embed = discord.Embed(title="ℹ️ Info Bot Counting", description="Comandi disponibili:", color=0x00ff00)
    embed.add_field(name="✅ /setcounting", value="Imposta il canale per il counting", inline=False)
    embed.add_field(name="🔢 /count", value="Mostra il numero attuale", inline=False)
    embed.add_field(name="🏆 /record", value="Mostra il record del server", inline=False)
    embed.add_field(name="🔄 /resetall", value="Reset totale (admin)", inline=False)
    embed.add_field(name="🥇 /top10", value="Top 10 utenti con più conteggi", inline=False)
    embed.add_field(name="🤡 /top10errors", value="Top 10 utenti con più errori", inline=False)
    embed.add_field(name="📊 /stats @utente", value="Mostra statistiche di un utente", inline=False)
    embed.add_field(name="📜 Regole principali", value="- Numeri in ordine crescente\n- Non puoi contare due volte di seguito\n- Puoi usare semplici espressioni matematiche", inline=False)
    await ctx.respond(embed=embed)

# ================= AVVIO =================
bot.run(TOKEN)

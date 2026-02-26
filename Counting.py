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

last_user = {}  # ultimo utente per server

def save_data():
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
    def _eval(node):
        if isinstance(node, ast.Constant): 
            return node.value
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.Pow):
                exponent = _eval(node.right)
                if exponent > 100: raise ValueError("Esponente troppo alto")
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
            "user_counts": {}, "user_errors": {}, "streaks": {}, "max_combo": {}
        }

    data = guild_data[guild_id]
    if not data.get("channel") or message.channel.id != data["channel"]:
        return

    # Prova a leggere come numero
    try:
        clean_content = message.content.replace(" ", "").replace(",", ".")
        result = int(round(eval_expr(clean_content)))
    except:
        return

    expected = data["current"] + 1

    # --- CONTROLLO ERRORI ---
    if result != expected:
        # Reset corrente
        await message.channel.send(f"💥 Errore! {message.author.mention} ha scritto **{result}** invece di **{expected}**.\nSi riparte da **1**!")
        data["current"] = 0
        last_user[guild_id] = None
        uid = str(message.author.id)
        data["user_errors"][uid] = data.get("user_errors", {}).get(uid, 0) + 1
        data["streaks"][uid] = 0  # reset streak
        try: await message.add_reaction("❌")
        except: pass

    elif last_user.get(guild_id) == message.author.id:
        # Stesso utente consecutivo
        await message.channel.send(f"❌ {message.author.mention}, non puoi contare due volte di fila! Reset a **1**.")
        data["current"] = 0
        last_user[guild_id] = None
        uid = str(message.author.id)
        data["user_errors"][uid] = data.get("user_errors", {}).get(uid, 0) + 1
        data["streaks"][uid] = 0
        try: await message.add_reaction("⚠️")
        except: pass

    else:
        # --- NUMERO CORRETTO ---
        data["current"] = result
        last_user[guild_id] = message.author.id
        uid = str(message.author.id)
        data["user_counts"][uid] = data["user_counts"].get(uid, 0) + 1

        # Gestione streak e combo
        data["streaks"][uid] = data.get("streaks", {}).get(uid, 0) + 1
        if data.get("max_combo") is None:
            data["max_combo"] = {}
        data["max_combo"][uid] = max(data["streaks"][uid], data.get("max_combo", {}).get(uid, 0))

        # Reazioni sempre corrette
        reactions = ["✅"]
        if result > data["record"]:
            data["record"] = result
            reactions.append("🏆")
            if result % 10 == 0:
                await message.channel.send(f"🎉 Nuovo Record del Server! Raggiunto quota **{result}**!")

        for r in reactions:
            try:
                await message.add_reaction(r)
            except: pass

    save_data()
    await bot.process_commands(message)

# ================= COMANDI SLASH =================
@bot.slash_command(name="setcounting", description="Imposta il canale attuale per il gioco")
async def setcounting(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in guild_data:
        guild_data[guild_id] = {"current":0,"record":0,"channel":None,"user_counts":{},"user_errors":{},"streaks":{},"max_combo":{}}
    guild_data[guild_id]["channel"] = ctx.channel.id
    save_data()
    await ctx.respond(f"✅ Canale {ctx.channel.mention} configurato per il Counting!")

@bot.slash_command(name="count", description="Mostra il numero attuale")
async def count(ctx):
    data = guild_data.get(str(ctx.guild.id), {"current":0})
    await ctx.respond(f"🔢 Numero attuale: **{data['current']}**. Prossimo numero: **{data['current'] + 1}**")

@bot.slash_command(name="top10", description="Mostra i migliori 10 utenti")
async def top10(ctx):
    data = guild_data.get(str(ctx.guild.id))
    if not data or not data.get("user_counts"):
        return await ctx.respond("📭 Nessun dato disponibile.")
    sorted_users = sorted(data["user_counts"].items(), key=lambda x:x[1], reverse=True)[:10]
    desc = "".join([f"**{i+1}.** <@{uid}> — `{cnt}` punti\n" for i,(uid,cnt) in enumerate(sorted_users)])
    await ctx.respond(embed=discord.Embed(title="🏆 Classifica Counting", description=desc, color=0x3498db))

@bot.slash_command(name="top10errors", description="Mostra i peggiori 10 utenti")
async def top10errors(ctx):
    data = guild_data.get(str(ctx.guild.id))
    if not data or not data.get("user_errors"):
        return await ctx.respond("😇 Nessuno ha ancora commesso errori.")
    sorted_users = sorted(data["user_errors"].items(), key=lambda x:x[1], reverse=True)[:10]
    desc = "".join([f"**{i+1}.** <@{uid}> — `{cnt}` errori 🤡\n" for i,(uid,cnt) in enumerate(sorted_users)])
    await ctx.respond(embed=discord.Embed(title="🤡 Classifica Errori", description=desc, color=0xe74c3c))

@bot.slash_command(name="stats", description="Mostra le statistiche di un utente")
async def stats(ctx, member: discord.Member):
    uid = str(member.id)
    guild_id = str(ctx.guild.id)
    data = guild_data.get(guild_id)
    if not data:
        return await ctx.respond("⚠️ Nessun dato disponibile.")
    streak = data.get("streaks", {}).get(uid, 0)
    combo = data.get("max_combo", {}).get(uid, 0)
    errors = data.get("user_errors", {}).get(uid, 0)
    # Calcola posizione in classifica
    sorted_users = sorted(data.get("user_counts", {}).items(), key=lambda x:x[1], reverse=True)
    position = next((i+1 for i,(u,_) in enumerate(sorted_users) if u==uid), "N/A")
    await ctx.respond(embed=discord.Embed(
        title=f"📊 Stats di {member.display_name}",
        description=f"👑 Streak personale: `{streak}`\n"
                    f"🔥 Combo senza errori: `{combo}`\n"
                    f"❌ Errori totali: `{errors}`\n"
                    f"🥇 Posizione in classifica: `{position}`",
        color=0x00ff00
    ))

@bot.slash_command(name="resetall", description="Resetta tutto (solo Counting Admin)")
async def resetall(ctx):
    role_name = "Counting Admin"
    if not isinstance(ctx.author, discord.Member) or not any(r.name==role_name for r in ctx.author.roles):
        return await ctx.respond(f"❌ Devi avere il ruolo `{role_name}`.", ephemeral=True)
    guild_id = str(ctx.guild.id)
    if guild_id in guild_data:
        guild_data[guild_id] = {"current":0,"record":0,"channel":guild_data[guild_id].get("channel"), "user_counts":{},"user_errors":{},"streaks":{},"max_combo":{}}
        last_user[guild_id] = None
        save_data()
        await ctx.respond("🔄 **Reset Totale completato!**")

@bot.slash_command(name="info", description="Mostra i comandi del bot")
async def info(ctx):
    embed = discord.Embed(
        title="ℹ️ Info Bot Counting",
        description="Comandi disponibili e regole principali:",
        color=0x00ff00
    )
    embed.add_field("✅ /setcounting","Imposta il canale per il counting.",inline=False)
    embed.add_field("🔢 /count","Mostra il numero corrente.",inline=False)
    embed.add_field("🏆 /record","Mostra il record massimo.",inline=False)
    embed.add_field("🔄 /resetall","Resetta tutto (solo Counting Admin).",inline=False)
    embed.add_field("🥇 /top10","Mostra i migliori 10 utenti.",inline=False)
    embed.add_field("🤡 /top10errors","Mostra i peggiori 10 utenti.",inline=False)
    embed.add_field("📊 /stats @utente","Mostra streak, combo, errori e posizione.",inline=False)
    embed.add_field("📜 Regole","- I numeri devono essere inviati in ordine crescente.\n- Non puoi contare due volte di seguito.\n- Puoi usare espressioni matematiche semplici (es: 2+1, sqrt(9)).",inline=False)
    await ctx.respond(embed=embed)

# ================= AVVIO BOT =================
bot.run(TOKEN)

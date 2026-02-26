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

# ================= GESTIONE DATI (JSON) =================
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        try:
            guild_data = json.load(f)
        except:
            guild_data = {}
else:
    guild_data = {}

# Memoria temporanea per l'ultimo utente (si resetta a None se c'è un errore)
last_user = {} 

def save_data():
    """Salva i dati correnti nel file JSON."""
    with open(DATA_FILE, "w") as f:
        json.dump(guild_data, f, indent=4)

# ================= INIZIALIZZAZIONE BOT =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= CALCOLATORE MATEMATICO SICURO =================
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

# ================= LOGICA DI GIOCO (EVENTO MESSAGGIO) =================
@bot.event
async def on_ready():
    print(f"✅ Bot Counting Online come {bot.user}")

@bot.event
async def on_message(message):
    # Ignora bot e messaggi privati
    if message.author.bot or not message.guild: return

    guild_id = str(message.guild.id)
    
    # Inizializza dati se il server è nuovo
    if guild_id not in guild_data:
        guild_data[guild_id] = {"current": 0, "record": 0, "channel": None, "user_counts": {}}
    
    data = guild_data[guild_id]
    
    # Controlla se il messaggio è nel canale dedicato
    if not data.get("channel") or message.channel.id != data["channel"]: 
        return

    # Tenta di leggere il contenuto come numero o operazione
    try:
        clean_content = message.content.replace(" ", "").replace(",", ".")
        result = int(round(eval_expr(clean_content)))
    except:
        return # Se non è un numero, il bot ignora il messaggio senza rispondere

    expected = data["current"] + 1

    # --- CONTROLLO ERRORI ---
    if result != expected:
        # Errore nel numero: Reset
        await message.channel.send(f"💥 Errore! {message.author.mention} ha scritto **{result}** invece di **{expected}**.\nSi riparte da **1**!")
        data["current"] = 0
        last_user[guild_id] = None # Reset memoria ultimo utente
        try: await message.add_reaction("❌")
        except: pass
    
    elif last_user.get(guild_id) == message.author.id:
        # Lo stesso utente ha scritto due volte di fila: Reset
        await message.channel.send(f"❌ {message.author.mention}, non puoi contare due volte di fila! Reset a **1**.")
        data["current"] = 0
        last_user[guild_id] = None # Reset memoria ultimo utente
        try: await message.add_reaction("⚠️")
        except: pass
    
    else:
        # --- NUMERO CORRETTO ---
        data["current"] = result
        last_user[guild_id] = message.author.id # Registra l'ultimo utente
        
        uid = str(message.author.id)
        data["user_counts"][uid] = data["user_counts"].get(uid, 0) + 1
        
        try: await message.add_reaction("✅")
        except: pass
        
        # Gestione Record
        if result > data["record"]:
            data["record"] = result
            try: await message.add_reaction("🏆")
            except: pass
            if result % 10 == 0:
                await message.channel.send(f"🎉 Nuovo Record del Server! Raggiunto quota **{result}**!")

    save_data()

# ================= COMANDI SLASH =================

@bot.slash_command(name="setcounting", description="Imposta il canale attuale per il gioco")
async def setcounting(ctx):
    guild_id = str(ctx.guild.id)
    if guild_id not in guild_data:
        guild_data[guild_id] = {"current": 0, "record": 0, "user_counts": {}}
    guild_data[guild_id]["channel"] = ctx.channel.id
    save_data()
    await ctx.respond(f"✅ Canale {ctx.channel.mention} configurato per il Counting!")

@bot.slash_command(name="count", description="Mostra il numero attuale")
async def count(ctx):
    data = guild_data.get(str(ctx.guild.id), {"current": 0})
    await ctx.respond(f"🔢 Numero attuale: **{data['current']}**. Prossimo numero: **{data['current'] + 1}**")

@bot.slash_command(name="top10", description="Mostra i migliori 10 utenti del server")
async def top10(ctx):
    data = guild_data.get(str(ctx.guild.id))
    if not data or not data.get("user_counts"):
        return await ctx.respond("📭 Nessun dato disponibile.")
    
    sorted_users = sorted(data["user_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
    description = ""
    for i, (user_id, count) in enumerate(sorted_users, 1):
        description += f"**{i}.** <@{user_id}> — `{count}` punti\n"
    
    embed = discord.Embed(title="🏆 Classifica Counting", description=description, color=0x3498db)
    await ctx.respond(embed=embed)
    
@bot.slash_command(name="top10errors", description="Mostra i peggiori 10 utenti del server")
async def toperrors(ctx):
    data = guild_data.get(str(ctx.guild.id))
    # Controlla se ci sono dati o se qualcuno ha mai sbagliato
    if not data or not data.get("user_errors"):
        return await ctx.respond("😇 Che bravi! Nessuno ha ancora commesso errori.")
    
    # Ordina gli utenti dal numero di errori più alto a quello più basso
    sorted_losers = sorted(data["user_errors"].items(), key=lambda x: x[1], reverse=True)[:10]
    
    description = ""
    for i, (u_id, count) in enumerate(sorted_losers, 1):
        # Aggiunge la posizione, la menzione dell'utente e il numero di errori
        description += f"**{i}.** <@{u_id}> — `{count}` fallimenti 🤡\n"
    
    embed = discord.Embed(
        title="🤡 Classifica Pagliacci", 
        description=description, 
        color=0xe74c3c # Rosso per indicare l'errore
    )
    await ctx.respond(embed=embed)

@bot.slash_command(name="resetall", description="Resetta tutto (corrente, record e punti) - Solo Counting Admin")
async def resetall(ctx: discord.ApplicationContext):
    role_name = "Counting Admin" 
    if not isinstance(ctx.author, discord.Member) or not any(role.name == role_name for role in ctx.author.roles):
        await ctx.respond(f"❌ Errore: Devi avere il ruolo `{role_name}`.", ephemeral=True)
        return

    guild_id = str(ctx.guild.id)
    if guild_id in guild_data:
        guild_data[guild_id]["current"] = 0
        guild_data[guild_id]["record"] = 0
        guild_data[guild_id]["user_counts"] = {}
        last_user[guild_id] = None # Fondamentale per far ripartire chiunque
        save_data()
        await ctx.respond("🔄 **Reset Totale!** Il gioco ricomincia da zero per tutti.")
    else:
        await ctx.respond("⚠️ Errore: Dati non trovati.", ephemeral=True)

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
        name="🤡 /top10errors",
        value="Mostra la classifica dei primi 10 utenti con più errori validi.",
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


# ================= AVVIO BOT =================
bot.run(TOKEN)




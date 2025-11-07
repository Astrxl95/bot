import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
import os
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import json
import asyncio
from datetime import datetime
import html
import textwrap

# ---------------------- CONFIG ----------------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("ERREUR : DISCORD_TOKEN manquant dans .env !")
    exit()

AUTHORIZED_ROLES = [
    "Modérateur/Modératrice", "Apprenti(e) Modérateur/Modératrice",
    "Administrateur/Administratrice"
]
TICKET_ROLE = "Recruteur"
TICKET_CATEGORY_ID = 1411027780723806342
RECRUITER_ROLE_ID = 1411027753586659409
LOG_CHANNEL_NAME = "logs-warns"
TICKET_LOG_CHANNEL = "logs-tickets"
TRANSCRIPT_CHANNEL = "logs-tickets"
WARNS_FILE = "warns.json"

# ---------------------- BOT ----------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------------- SERVEUR FLASK (pour BetterStack) ----------------------
app = Flask('')

@app.route('/')
def home():
    return "Bot Discord en ligne !"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# ---------------------- CHECKS ----------------------
def is_authorized():
    def predicate(interaction: discord.Interaction) -> bool:
        return any(role.name in AUTHORIZED_ROLES for role in interaction.user.roles)
    return app_commands.check(predicate)

def has_ticket_permission():
    def predicate(interaction: discord.Interaction) -> bool:
        return any(role.name in (AUTHORIZED_ROLES + [TICKET_ROLE]) for role in interaction.user.roles)
    return app_commands.check(predicate)

# ---------------------- UTILITAIRES ----------------------
def get_channel_by_name(guild, name):
    cleaned = name.lower().replace("・", "").replace(" ", "-")
    return next((c for c in guild.text_channels if c.name.lower().replace("・", "").replace(" ", "-") == cleaned), None)

def load_warns():
    try:
        with open(WARNS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_warns(data):
    with open(WARNS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def generate_transcript(channel: discord.TextChannel) -> discord.File:
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%d/%m/%Y %H:%M:%S")
        author = html.escape(message.author.display_name)
        content = html.escape(message.content) if message.content else ""
        attachments = ""
        for a in message.attachments:
            if a.content_type and a.content_type.startswith("image"):
                attachments += f'<br><img src="{a.url}" width="200">'
            else:
                attachments += f'<br><a href="{a.url}">[Fichier]</a>'
        msg_html = (
            '<div class="message">'
            f'<img src="{message.author.avatar.url if message.author.avatar else message.author.default_avatar.url}" class="avatar">'
            '<div class="content">'
            f'<span class="author">{author}</span>'
            f'<span class="timestamp">{timestamp}</span>'
            f'<div class="text">{content.replace(chr(10), "<br>")}</div>'
            f'{attachments}'
            '</div>'
            '</div>')
        messages.append(msg_html)

    html_content = f"""    <!DOCTYPE html>
    <html><head><meta charset="utf-8"><title>Transcript - {channel.name}</title>
    <style>body {{font-family:Segoe UI;background:#36393f;color:#dcddde;padding:20px}}
    .message {{display:flex;margin-bottom:15px}}.avatar {{width:40px;height:40px;border-radius:50%;margin-right:10px}}
    .content {{flex:1}}.author {{font-weight:600;color:#fff}}.timestamp {{font-size:0.75rem;color:#72767d;margin-left:5px}}
    .text {{margin-top:2px}}a {{color:#00aff4}}</style></head><body>
    <h1>Transcript du ticket : {channel.name}</h1>
    <p><strong>Fermé le :</strong> {datetime.utcnow().strftime("%d/%m/%Y à %H:%M:%S")} UTC</p><hr>
    {''.join(messages)}</body></html>"""
    filename = f"transcript-{channel.name}-{int(datetime.utcnow().timestamp())}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(html_content))
    return discord.File(filename, filename=filename)

# ---------------------- EVENTS ----------------------
@bot.event
async def on_ready():
    print(f"Connecté : {bot.user} (ID: {bot.user.id})")
    print("Synchronisation des commandes...")
    try:
        synced = await tree.sync()
        print(f"{len(synced)} commandes synchronisées !")
    except Exception as e:
        print(f"ERREUR SYNC : {e}")

# ---------------------- TICKETS ----------------------
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un ticket", style=discord.ButtonStyle.success, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        role = guild.get_role(RECRUITER_ROLE_ID)
        if role:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("Erreur : catégorie introuvable.", ephemeral=True)
            return
        channel = await guild.create_text_channel(f"ticket-{interaction.user.name}", category=category, overwrites=overwrites)
        view = CloseTicketView()
        msg = f"Bonjour {interaction.user.mention}, un <@&{RECRUITER_ROLE_ID}> va s'occuper de toi.\nPour faciliter la gestion, merci de **fournir un screen de ton profil en jeu**"
        await channel.send(msg, view=view)
        await interaction.response.send_message(f"Ticket créé : {channel.mention}", ephemeral=True)

class CloseTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button):
        await interaction.response.send_message("Fermeture dans 5s...", ephemeral=True)
        await asyncio.sleep(5)
        log = get_channel_by_name(interaction.guild, TICKET_LOG_CHANNEL)
        if log:
            await log.send(f"Ticket fermé : `{interaction.channel.name}` par {interaction.user.mention}")
        transcript = get_channel_by_name(interaction.guild, TRANSCRIPT_CHANNEL)
        if transcript:
            try:
                file = await generate_transcript(interaction.channel)
                await transcript.send(f"Transcript `{interaction.channel.name}`", file=file)
                os.remove(file.filename)
            except Exception as e:
                print(f"Transcript erreur: {e}")
        await interaction.channel.delete()

@tree.command(name="ticketpanel", description="Crée un panel de tickets")
@has_ticket_permission()
@app_commands.describe(channel="Salon pour le panel")
async def ticketpanel(interaction: discord.Interaction, channel: discord.TextChannel):
    embed = discord.Embed(title="Rejoindre Brawler War", description="Clique pour ouvrir un ticket", color=discord.Color.red())
    view = TicketView()
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(f"Panel créé dans {channel.mention}", ephemeral=True)

# ---------------------- LANCEMENT ----------------------
keep_alive()
print("Démarrage du bot...")
bot.run(TOKEN)

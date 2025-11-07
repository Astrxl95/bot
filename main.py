import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
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
AUTHORIZED_ROLES = [
    "Modérateur/Modératrice", "Apprenti(e) Modérateur/Modératrice",
    "Administrateur/Administratrice"
]
FOUNDER_ADMIN_ROLES = ["Fondateur/Fondatrice", "Administrateur/Administratrice"]  # Pour /embed
TICKET_ROLES = ["Fondateur", "Administrateur/Administratrice"]
TICKET_ROLE = "Recruteur"
TICKET_CATEGORY_ID = 1411027780723806342  # ID de la catégorie
RECRUITER_ROLE_ID = 1411027753586659409  # ID du rôle Recruteur
WARN_ROLES = [
    "Modérateur/Modératrice", "Apprenti(e) Modérateur/Modératrice",
    "Administrateur/Administratrice"
]
LOG_CHANNEL_NAME = "🟤・logs-warns"
TICKET_LOG_CHANNEL = "🟤・logs-tickets"
TRANSCRIPT_CHANNEL = "🟤・logs-tickets"
WARNS_FILE = "warns.json"

# ---------------------- BOT ----------------------
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------------- SERVEUR FLASK ----------------------
app = Flask('')


@app.route('/')
def home():
    return "Bot Discord en ligne !"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    if os.getenv("REPLIT") or os.getenv("RAILWAY"):
        t = Thread(target=run)
        t.start()


# ---------------------- CHECKS ----------------------
def is_authorized():

    def predicate(interaction: discord.Interaction) -> bool:
        user_roles = [role.name for role in interaction.user.roles]
        return any(role in AUTHORIZED_ROLES for role in user_roles)

    return app_commands.check(predicate)


def has_warn_role():

    def predicate(interaction: discord.Interaction) -> bool:
        user_roles = [role.name for role in interaction.user.roles]
        return any(role in WARN_ROLES for role in user_roles)

    return app_commands.check(predicate)


def has_ticket_permission():

    def predicate(interaction: discord.Interaction) -> bool:
        user_roles = [role.name for role in interaction.user.roles]
        return any(role in (AUTHORIZED_ROLES + [TICKET_ROLE])
                   for role in user_roles)

    return app_commands.check(predicate)


# ---------------------- UTILITAIRES ----------------------
def get_channel_by_name(guild, name):
    cleaned = name.lower().replace("・", "").replace(" ", "-")
    return next(
        (c for c in guild.text_channels
         if c.name.lower().replace("・", "").replace(" ", "-") == cleaned),
        None)


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

    html_content = f"""\
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Transcript - {channel.name}</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #36393f; color: #dcddde; padding: 20px; }}
            .message {{ display: flex; margin-bottom: 15px; }}
            .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 10px; }}
            .content {{ flex: 1; }}
            .author {{ font-weight: 600; color: #fff; }}
            .timestamp {{ font-size: 0.75rem; color: #72767d; margin-left: 5px; }}
            .text {{ margin-top: 2px; }}
            a {{ color: #00aff4; }}
        </style>
    </head>
    <body>
        <h1>Transcript du ticket : {channel.name}</h1>
        <p><strong>Fermé le :</strong> {datetime.utcnow().strftime("%d/%m/%Y à %H:%M:%S")} UTC</p>
        <hr>
        {''.join(messages)}
    </body>
    </html>
    """
    filename = f"transcript-{channel.name}-{int(datetime.utcnow().timestamp())}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(html_content))
    return discord.File(filename, filename=filename)


# ---------------------- EVENTS ----------------------
@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    try:
        await tree.sync()
        print("Commandes slash synchronisées.")
    except Exception as e:
        print(f"Erreur de sync: {e}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if bot.user in message.mentions:
        await message.add_reaction("wave")
    await bot.process_commands(message)


# ---------------------- COMMANDES MODÉRATION ----------------------
@tree.command(name="kick", description="Expulse un membre du serveur.")
@is_authorized()
@app_commands.describe(user="Utilisateur à expulser", reason="Raison du kick")
async def kick(interaction: discord.Interaction,
               user: discord.Member,
               reason: str = "Aucune raison"):
    await user.kick(reason=reason)
    await interaction.response.send_message(
        f"{user.mention} a été expulsé. Raison : {reason}", ephemeral=True)


@tree.command(name="ban", description="Bannit un membre du serveur.")
@is_authorized()
@app_commands.describe(user="Utilisateur à bannir", reason="Raison du ban")
async def ban(interaction: discord.Interaction,
              user: discord.Member,
              reason: str = "Aucune raison"):
    await user.ban(reason=reason)
    await interaction.response.send_message(
        f"{user.mention} a été banni. Raison : {reason}", ephemeral=True)


@tree.command(name="unban",
              description="Débannit un utilisateur via ID ou nom#tag")
@is_authorized()
@app_commands.describe(name="ID ou nom#tag (ex: pseudo#1234 ou 123456789)")
async def unban(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        user_id = int(name)
        user = await bot.fetch_user(user_id)
        await interaction.guild.unban(discord.Object(id=user_id))
        await interaction.followup.send(f"{user} (`{user_id}`) a été débanni.")
        return
    except ValueError:
        pass
    except discord.NotFound:
        await interaction.followup.send("Aucun ban trouvé pour cet ID.")
        return
    bans = await interaction.guild.bans()
    for ban_entry in bans:
        user = ban_entry.user
        full = f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name
        if name.lower() in [full.lower(), str(user.id)]:
            await interaction.guild.unban(user)
            await interaction.followup.send(f"{user.mention} a été débanni.")
            return
    await interaction.followup.send(
        "Aucun utilisateur correspondant trouvé dans les bans.")


@tree.command(name="clear", description="Supprime un nombre de messages.")
@is_authorized()
@app_commands.describe(amount="Nombre de messages à supprimer (1-100)")
async def clear(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("Entre 1 et 100 messages.",
                                                ephemeral=True)
        return
    await interaction.channel.purge(limit=amount + 1)
    await interaction.response.send_message(f"{amount} messages supprimés.",
                                            ephemeral=True)


@tree.command(name="mute", description="Rend un utilisateur muet.")
@is_authorized()
@app_commands.describe(user="Utilisateur à mute", reason="Raison du mute")
async def mute(interaction: discord.Interaction,
               user: discord.Member,
               reason: str = "Aucune raison"):
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role:
        muted_role = await interaction.guild.create_role(
            name="Muted", reason="Rôle pour mute")
    for channel in interaction.guild.channels:
        await channel.set_permissions(muted_role,
                                      send_messages=False,
                                      speak=False,
                                      add_reactions=False)
    if muted_role in user.roles:
        await interaction.response.send_message(
            f"{user.mention} est déjà muté.", ephemeral=True)
        return
    await user.add_roles(muted_role, reason=reason)
    await interaction.response.send_message(
        f"{user.mention} a été muté. Raison : {reason}", ephemeral=True)


@tree.command(name="unmute", description="Démute un utilisateur.")
@is_authorized()
@app_commands.describe(user="Utilisateur à démute")
async def unmute(interaction: discord.Interaction, user: discord.Member):
    muted_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not muted_role or muted_role not in user.roles:
        await interaction.response.send_message(
            "Cet utilisateur n'est pas muté.", ephemeral=True)
        return
    await user.remove_roles(muted_role)
    await interaction.response.send_message(f"{user.mention} a été démute.",
                                            ephemeral=True)


# ---------------------- LOCK / UNLOCK ----------------------
@tree.command(name="lock", description="Verrouille un salon")
@is_authorized()
@app_commands.describe(channel="Salon à verrouiller (optionnel)")
async def lock(interaction: discord.Interaction,
               channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role,
                                  send_messages=False)
    await interaction.response.send_message(
        f"Salon {channel.mention} verrouillé.", ephemeral=True)


@tree.command(name="unlock", description="Déverrouille un salon")
@is_authorized()
@app_commands.describe(channel="Salon à déverrouiller (optionnel)")
async def unlock(interaction: discord.Interaction,
                 channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    await channel.set_permissions(interaction.guild.default_role,
                                  send_messages=None)
    await interaction.response.send_message(
        f"Salon {channel.mention} déverrouillé.", ephemeral=True)


# ---------------------- ADD USER TO TICKET ----------------------
@tree.command(name="add",
              description="Ajoute un utilisateur au ticket en cours")
@has_ticket_permission()
@app_commands.describe(user="Utilisateur à ajouter")
async def add_user(interaction: discord.Interaction, user: discord.Member):
    if not interaction.channel.name.startswith("ticket-"):
        await interaction.response.send_message(
            "Cette commande ne peut être utilisée que dans un ticket.",
            ephemeral=True)
        return
    overwrites = interaction.channel.overwrites_for(user)
    if overwrites.read_messages is True:
        await interaction.response.send_message(
            f"{user.mention} est déjà dans le ticket.", ephemeral=True)
        return
    await interaction.channel.set_permissions(user,
                                              read_messages=True,
                                              send_messages=True,
                                              attach_files=True,
                                              read_message_history=True)
    await interaction.response.send_message(
        f"{user.mention} a été ajouté au ticket.", ephemeral=True)
    await interaction.channel.send(
        f"{user.mention} a été ajouté par {interaction.user.mention}.")


# ---------------------- TICKETS ----------------------
class TicketView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ouvrir un ticket",
                       style=discord.ButtonStyle.success,
                       custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        guild = interaction.guild
        overwrites = {
            guild.default_role:
            discord.PermissionOverwrite(read_messages=False),
            interaction.user:
            discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        # Ajouter le rôle Recruteur par ID
        recruiter_role = guild.get_role(RECRUITER_ROLE_ID)
        if recruiter_role:
            overwrites[recruiter_role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True)

        # Récupérer la catégorie par ID
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "Erreur : catégorie de tickets introuvable.", ephemeral=True)
            return

        ticket_channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites)
        view = CloseTicketView()
        message = (
            f"Bonjour {interaction.user.mention}, un <@&{RECRUITER_ROLE_ID}> va s'occuper de toi.\n"
            "Pour faciliter la gestion, merci de **fournir un screen de ton profil en jeu**"
        )
        await ticket_channel.send(message, view=view)
        await interaction.response.send_message(
            f"Ton ticket a été créé : {ticket_channel.mention}",
            ephemeral=True)


class CloseTicketView(View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Fermer le ticket",
                       style=discord.ButtonStyle.red,
                       custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await interaction.response.send_message(
            "Fermeture du ticket dans 5 secondes...", ephemeral=True)
        await asyncio.sleep(5)
        log_channel = get_channel_by_name(interaction.guild,
                                          TICKET_LOG_CHANNEL)
        if log_channel:
            await log_channel.send(
                f"Ticket fermé : `{interaction.channel.name}` par {interaction.user.mention}"
            )
        transcript_channel = get_channel_by_name(interaction.guild,
                                                 TRANSCRIPT_CHANNEL)
        if transcript_channel:
            try:
                transcript_file = await generate_transcript(interaction.channel
                                                            )
                await transcript_channel.send(
                    f"Transcript du ticket `{interaction.channel.name}`",
                    file=transcript_file)
                os.remove(transcript_file.filename)
            except Exception as e:
                print(f"Erreur transcript: {e}")
        await interaction.channel.delete()


@tree.command(name="ticketpanel",
              description="Crée un panel pour ouvrir des tickets.")
@has_ticket_permission()
@app_commands.describe(channel="Salon où poster le panel")
async def ticketpanel(interaction: discord.Interaction,
                      channel: discord.TextChannel):
    embed = discord.Embed(
        title="Rejoindre Brawler War",
        description="Clique sur le bouton ci-dessous pour ouvrir un ticket",
        color=discord.Color.red())
    view = TicketView()
    await channel.send(embed=embed, view=view)
    await interaction.response.send_message(
        f"Panel de ticket créé dans {channel.mention}", ephemeral=True)


# ---------------------- WARN SYSTEM ----------------------
@tree.command(name="warn", description="Warn un membre avec une raison.")
@has_warn_role()
@app_commands.describe(user="Utilisateur à warn", reason="Raison du warn")
async def warn(interaction: discord.Interaction, user: discord.Member,
               reason: str):
    try:
        await user.send(
            f"Tu as reçu un warn sur **{interaction.guild.name}**.\n**Raison** : {reason}"
        )
    except discord.Forbidden:
        pass
    log_channel = get_channel_by_name(interaction.guild, LOG_CHANNEL_NAME)
    if log_channel:
        embed = discord.Embed(title="Nouveau Warn",
                              color=discord.Color.orange())
        embed.add_field(name="Utilisateur", value=user.mention, inline=False)
        embed.add_field(name="Modérateur",
                        value=interaction.user.mention,
                        inline=False)
        embed.add_field(name="Raison", value=reason, inline=False)
        embed.set_footer(text=f"ID: {user.id}")
        await log_channel.send(embed=embed)
    warns = load_warns()
    user_id = str(user.id)
    if user_id not in warns:
        warns[user_id] = []
    warns[user_id].append({
        "reason": reason,
        "moderator": str(interaction.user),
        "timestamp": datetime.utcnow().isoformat()
    })
    save_warns(warns)
    await interaction.response.send_message(
        f"{user.mention} a été warn. Log envoyé.", ephemeral=True)


@tree.command(name="warns", description="Voir les warns d'un membre")
@has_warn_role()
@app_commands.describe(user="Membre à vérifier")
async def warns_cmd(interaction: discord.Interaction, user: discord.Member):
    warns = load_warns()
    user_warns = warns.get(str(user.id), [])
    if not user_warns:
        await interaction.response.send_message(
            f"{user.mention} n'a aucun warn.", ephemeral=True)
        return
    embed = discord.Embed(title=f"Warns de {user}",
                          color=discord.Color.orange())
    for i, w in enumerate(user_warns[-5:], 1):
        ts = datetime.fromisoformat(w["timestamp"].split('.')[0])
        timestamp = int(ts.timestamp())
        embed.add_field(
            name=f"Warn {i}",
            value=
            f"**Modérateur** : {w['moderator']}\n**Raison** : {w['reason']}\n**Date** : <t:{timestamp}:R>",
            inline=False)
    if len(user_warns) > 5:
        embed.set_footer(text=f"... et {len(user_warns) - 5} autre(s)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# --- /embed (avec preview) ---
@bot.tree.command(name="embed", description="Créer un embed personnalisé avec preview avant envoi")
@app_commands.describe(title="Titre de l'embed", description="Contenu de l'embed", color_hex="Couleur (hex, ex: #ff0000)")
async def embed(interaction: discord.Interaction, title: str, description: str, color_hex: str = "#00ffcc"):
    try:
        color = discord.Color(int(color_hex.replace("#", ""), 16))
    except ValueError:
        color = discord.Color.blue()

    preview = discord.Embed(title=title, description=description, color=color)
    await interaction.response.send_message("📝 **Prévisualisation de ton embed :**", embed=preview, ephemeral=True)

    view = discord.ui.View()
    view.add_item(discord.ui.Button(label="Envoyer", style=discord.ButtonStyle.green, custom_id="send"))
    view.add_item(discord.ui.Button(label="Annuler", style=discord.ButtonStyle.red, custom_id="cancel"))

    async def callback(inter):
        if inter.data["custom_id"] == "send":
            await inter.response.send_message("✅ Embed envoyé !", ephemeral=True)
            await interaction.channel.send(embed=preview)
        elif inter.data["custom_id"] == "cancel":
            await inter.response.send_message("❌ Envoi annulé.", ephemeral=True)
        view.stop()

    for child in view.children:
        child.callback = callback

    await interaction.followup.send("Souhaites-tu envoyer cet embed ?", view=view, ephemeral=True)

# ---------------------- ERREURS ----------------------
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message("Tu n’as pas la permission.",
                                                ephemeral=True)
    else:
        print(f"Erreur: {error}")


# ---------------------- LANCEMENT ----------------------
keep_alive()
bot.run(TOKEN)

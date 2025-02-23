#!/usr/bin/python3
##########################################
#----------------------------------------#
##########################################


import discord
from discord.ext import commands, tasks
from discord import Embed, Color
from datetime import datetime, timezone
import json
import asyncio
import random
import sqlite3
import sys

##########################################
#----------------------------------------#
##########################################


with open('config.json', 'r') as config_file:
    config_data = json.load(config_file)

token = config_data.get('token')
if token == "":
    print("Bot token required in config.json file")
    sys.exit()


prefix = config_data.get('prefix')

intents = discord.Intents().all()
intents.voice_states = True
bot = commands.Bot(command_prefix=prefix, intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"{bot.user.name} s'est bien connecté sur Discord !")
    await update_presence()

async def update_presence():
    twitch_url = "https://twitch.tv/mithaanne"
    custom_activity = discord.Streaming(name="sur Twitch | Vendredi et Samedi, 21h", url=twitch_url)
    await bot.change_presence(activity=custom_activity, status=discord.Status.online)


##########################################
#----------------------------------------#
##########################################
    

@bot.command(name='delete', help='Supprime <amount> messages', hidden=True)
async def delete_messages(ctx, amount: int):
    if ctx.message.author.guild_permissions.manage_messages:
        await ctx.message.delete()
        await ctx.channel.purge(limit=amount)
        await ctx.send(f"{amount} messages supprimés par {ctx.message.author.mention}.", delete_after=5)
    else:
        await ctx.send("Vous n'avez pas la permission de supprimer des messages.", delete_after=5)


##########################################
#----------------------------------------#
##########################################
        

@bot.command(name='help', help="Affiche les commandes disponibles pour les membres")
async def help_command(ctx):
    prefix = '%'

    embed = Embed(
        title="Supervision - Commandes Membres",
        color=Color.green()
    )

    commands_text = ""
    for i, command in enumerate(bot.commands):
        if not command.hidden:
            signature = f"{prefix}{command.name} {command.signature}" if command.signature else f"{prefix}{command.name}"
            commands_text += f"```{signature}```{command.help or 'Aucune description disponible.'}{'' if i == len(bot.commands) - 1 else '\n\n'}"

    embed.add_field(name="Commandes :", value=commands_text, inline=False)
    embed.set_footer(text=f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})")

    await ctx.send(embed=embed)


##########################################
#----------------------------------------#
##########################################

@bot.command(name='adhelp', help="Affiche toutes les commandes (réservé aux admins)", hidden=True)
@commands.has_permissions(administrator=True)
async def admin_help_command(ctx):
    prefix = '%'

    embed = Embed(
        title="Supervision - Toutes les Commandes",
        color=Color.red()
    )

    commands_text = ""
    for i, command in enumerate(bot.commands):
        signature = f"{prefix}{command.name} {command.signature}" if command.signature else f"{prefix}{command.name}"
        commands_text += f"```{signature}```{command.help or 'Aucune description disponible.'}{'' if i == len(bot.commands) - 1 else '\n\n'}"

    embed.add_field(name="Commandes :", value=commands_text, inline=False)
    embed.set_footer(text=f"({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')})")
    await ctx.send(embed=embed)


##########################################
#----------------------------------------#
##########################################


@bot.command(name='mp', help='Envoie à <user> le message <content>', hidden=True)
@commands.has_permissions(administrator=True)
async def send_private_message(ctx, user: discord.User, *, content: str):
    try:
        await user.send(content)
    except discord.Forbidden:
        await ctx.send(f"Impossible d'envoyer un message privé à {user.display_name}. Il se peut que les messages privés soient désactivés.")
        return

    def check(message):
        return message.author == user and message.channel == message.author.dm_channel

    try:
        response = await bot.wait_for('message', check=check, timeout=600)
        await ctx.send(f"Réponse de {user.display_name}: {response.content}")
    except asyncio.TimeoutError:
        await ctx.send(f"Aucune réponse de {user.display_name} dans le délai imparti.")

@send_private_message.error
async def mp_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Vous n'avez pas les permissions nécessaires pour utiliser cette commande.")
        
        await ctx.message.delete()

@bot.event
async def on_message(message):
    if message.author != bot.user:
        if message.author.id in pending_messages:
            print(f"Utilisateur {message.author.name} ({message.author.id}) a répondu : {message.content}")

            del pending_messages[message.author.id]

    await bot.process_commands(message)  

pending_messages = {}


##########################################
#----------------------------------------#
##########################################


@bot.command(name='follow', help='<user_id> est suivi par Supervision à travers tout les salons vocaux du serveur')
async def follow(ctx, user_id: int):
    if user_id == 0:
        voice_client = discord.utils.get(bot.voice_clients, guild=ctx.guild)
        if voice_client:
            await voice_client.disconnect()
            await ctx.send("Le bot a cessé de suivre.")
        else:
            await ctx.send("Le bot n'est pas actuellement connecté à un canal vocal.")
        return

    member_to_follow = ctx.guild.get_member(user_id)

    if member_to_follow is None:
        await ctx.send("Membre introuvable.")
        return

    voice_channel = member_to_follow.voice.channel
    if voice_channel is None:
        await ctx.send(f"{member_to_follow.name} n'est pas actuellement dans un canal vocal.")
        return

    voice_client = await voice_channel.connect()

    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.id == member_to_follow.id and before.channel != after.channel:
            if after.channel is None:
                await voice_client.disconnect()
                await ctx.send("Le bot a cessé de suivre.")
            else:
                await voice_client.move_to(after.channel)


##########################################
#----------------------------------------#
##########################################


@bot.command(name='set_logs', help='Définit le salon des logs', hidden=True)
async def set_logs(ctx, channel: discord.TextChannel):
    config = load_config()

    config['logs_channel'] = channel.id
    save_config(config)

    await ctx.send(f"Le salon de logs a été défini sur {channel.mention}")

@bot.event
async def on_message_edit(before, after):
    await log_event("Message Modifié", before.guild, f"**Auteur :** {before.author.mention}\n**Avant :** {before.content}\n**Après :** {after.content}", color=discord.Color.orange())

@bot.event
async def on_message_delete(message):
    config = load_config()
    logs_channel_id = config.get('logs_channel')

    if message.channel.id != logs_channel_id:
        await log_event("Message Supprimé", message.guild, f"**Auteur :** {message.author.mention}\n**Contenu :** {message.content}", color=discord.Color.red())

@bot.event
async def on_guild_role_create(role):
    await log_event("Rôle Créé", role.guild, f"**Nom :** {role.name}", color=discord.Color.green())

@bot.event
async def on_guild_role_update(before, after):
    await log_event("Rôle Modifié", before.guild, f"**Avant :** {before.name}\n**Après :** {after.name}", color=discord.Color.blue())

@bot.event
async def on_guild_role_delete(role):
    await log_event("Rôle Supprimé", role.guild, f"**Nom :** {role.name}", color=discord.Color.red())

@bot.event
async def on_member_update(before, after):
    if before.roles != after.roles:
        removed_roles = set(before.roles) - set(after.roles)
        added_roles = set(after.roles) - set(before.roles)

        if removed_roles:
            for role in removed_roles:
                await log_event("Utilisateur Enlevé d'un Rôle", before.guild, f"**Utilisateur :** {after.mention}\n**Rôle Enlevé :** {role.name}", color=discord.Color.red())

        if added_roles:
            for role in added_roles:
                await log_event("Utilisateur Reçu un Rôle", before.guild, f"**Utilisateur :** {after.mention}\n**Rôle Reçu :** {role.name}", color=discord.Color.green())
    
    if before.nick != after.nick:
        await log_event("Pseudonyme Changé", before.guild, f"**Utilisateur :** {after.mention}\n**Avant :** {before.nick}\n**Après :** {after.nick}", color=discord.Color.blue())

@bot.event
async def on_voice_state_update(member, before, after):
    if before.channel != after.channel:
        if after.channel:
            await log_event("Utilisateur Rejoint un Salon Vocal", member.guild, f"**Utilisateur :** {member.mention}\n**Salon :** {after.channel.name}", color=discord.Color.green())
        elif before.channel:
            await log_event("Utilisateur Quitte un Salon Vocal", member.guild, f"**Utilisateur :** {member.mention}\n**Salon :** {before.channel.name}", color=discord.Color.red())

@bot.event
async def on_member_join(member):
    await log_event("Utilisateur Rejoint le Serveur", member.guild, f"**Utilisateur :** {member.mention}", color=discord.Color.green())

@bot.event
async def on_member_remove(member):
    await log_event("Utilisateur Quitte le Serveur", member.guild, f"**Utilisateur :** {member.mention}", color=discord.Color.red())

@bot.event
async def on_member_ban(guild, user):
    await log_event("Utilisateur Banni", guild, f"**Utilisateur :** {user.mention}", color=discord.Color.red())

@bot.event
async def on_member_unban(guild, user):
    await log_event("Utilisateur Débanni", guild, f"**Utilisateur :** {user.mention}", color=discord.Color.green())

async def log_event(title, guild, description, color):
    config = load_config()
    logs_channel_id = config.get('logs_channel')

    if logs_channel_id:
        logs_channel = guild.get_channel(logs_channel_id)

        if logs_channel:
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=f"ID de l'utilisateur : {guild.id} • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            await logs_channel.send(embed=embed)

def load_config():
    with open('config.json', 'r') as f:
        return json.load(f)

def save_config(config):
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)


##########################################
#----------------------------------------#
##########################################


try:
    with open('warn.json', 'r') as f:
        warns = json.load(f)
except FileNotFoundError:
    warns = {}

@bot.command(name='warn', help="Sanctionne <user> pour <reason>", hidden=True)
async def warn(ctx, user: discord.User, *, reason: str):
    if str(user.id) not in warns:
        warns[str(user.id)] = []
    
    warn_entry = {"reason": reason, "date": str(datetime.now())}
    warns[str(user.id)].append(warn_entry)
    
    with open('warn.json', 'w') as f:
        json.dump(warns, f, indent=4)
    
    embed = discord.Embed(title="Warn", description=f"{user.mention} a été warn pour : {reason}", color=discord.Color.orange())
    await ctx.send(embed=embed)

@bot.command(name='warnlist', help="Affiche les sanctions de <user>", hidden=True)
async def warnlist(ctx, user: discord.User):
    if str(user.id) in warns and warns[str(user.id)]:
        warn_list = "\n".join([f"**Raison :** {entry['reason']} - **Date :** {entry['date']}" for entry in warns[str(user.id)]])
        
        embed = discord.Embed(title=f"Warns de {user}", description=warn_list, color=discord.Color.red())
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"{user.mention} n'a pas de warns.")


##########################################
#----------------------------------------#
##########################################


conn = sqlite3.connect('levels.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS levels
             (user_id INTEGER PRIMARY KEY, exp INTEGER, level INTEGER)''')
conn.commit()

experience_cooldowns = {}

level_role_ids = {
    1: 1044994259666878544,
    5: 1044994137419694112,
    10: 1044991800710021180, 
    15: 1044991545717305364, 
    20: 1044991385444556852, 
    25: 1044991089154728073, 
    30: 1044990738825494628, 
    35: 1044989955803455508, 
    40: 1044989707332882442, 
    45: 1044989571663937607, 
}



@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = message.author.id

    if user_id not in experience_cooldowns or experience_cooldowns[user_id] <= 0:
        add_experience(user_id, random.randint(6, 13))

        experience_cooldowns[user_id] = 60
    else:
        experience_cooldowns[user_id] -= 1

    await check_level(message.author, message.channel)

    await bot.process_commands(message)

@tasks.loop(seconds=60)
async def update_leaderboard():
    leaderboard_channel_id = 123456789012345678
    leaderboard_channel = bot.get_channel(leaderboard_channel_id)
    
    if leaderboard_channel:
        top_users = get_top_users(10)
        
        embed = discord.Embed(title="Classement des Niveaux", color=0x00ff00)
        for index, (user_id, level, exp) in enumerate(top_users, start=1):
            user = bot.get_user(user_id)
            if user:
                embed.add_field(name=f"{index}. {user.name}", value=f"Niveau {level} - Expérience {exp}", inline=False)
        
        await leaderboard_channel.send(embed=embed)

async def check_level(user, channel):
    user_id = user.id
    current_exp, current_level = get_user_data(user_id)

    next_level_exp = current_level * 2 + (current_level**3) + current_level * 102

    while current_exp >= next_level_exp:
        update_user_data(user_id, current_exp - next_level_exp, current_level + 1)

        if current_level + 1 in level_role_ids:
            role_id = level_role_ids[current_level + 1]
            role = discord.utils.get(user.guild.roles, id=role_id)
            if role and role not in user.roles:
                embed = discord.Embed(title="Nouveau Rôle Obtenu!", description=f"{user.mention} a obtenu le rôle {role.name}!", color=0x00ff00)
                await channel.send(embed=embed)

                await user.add_roles(role)

        current_exp, current_level = get_user_data(user_id)
        next_level_exp = current_level * 2 + (current_level**3) + current_level * 102

def add_experience(user_id, exp):
    current_exp, current_level = get_user_data(user_id)
    new_exp = current_exp + exp
    update_user_data(user_id, new_exp, current_level)

def get_user_data(user_id):
    c.execute('SELECT exp, level FROM levels WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if result:
        return result
    else:
        c.execute('INSERT INTO levels (user_id, exp, level) VALUES (?, 0, 1)', (user_id,))
        conn.commit()
        return (0, 1)

def update_user_data(user_id, exp, level):
    c.execute('UPDATE levels SET exp = ?, level = ? WHERE user_id = ?', (exp, level, user_id))
    conn.commit()

@bot.command()
async def level(ctx, member: discord.Member = None):
    member = member or ctx.author
    exp, level = get_user_data(member.id)
    
    next_level_exp = (level + 1) * 2 + ((level + 1)**3) + (level + 1) * 102

    progress = int((exp / next_level_exp) * 10)
    bar = "[{}{}]".format("=" * progress, " " * (10 - progress))

    current_role = None
    for role_level, role_id in level_role_ids.items():
        if level >= role_level:
            current_role = discord.utils.get(ctx.guild.roles, id=role_id)

    total_exp = sum([(lvl * 2 + (lvl**3) + lvl * 102) for lvl in range(level)]) + exp

    embed = discord.Embed(title=f"Niveau de {member.display_name}", description=f"{member.display_name} est au niveau {level} avec {exp} points d'expérience.", color=0x00ff00)
    embed.add_field(name="Niveau", value=level, inline=True)
    embed.add_field(name="XP", value=f"{exp} / {next_level_exp}", inline=True)
    embed.add_field(name="%", value=f"{progress * 10}%", inline=True)
    embed.add_field(name="XP Total", value=f"Expérience totale : {total_exp}", inline=True)
    if current_role:
        embed.add_field(name="Rôle Actuel", value=f"Rôle : {current_role.name}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def setlevel(ctx, member: discord.Member, value: str, amount: int):
    if value.lower() == "lv":
        update_user_data(member.id, amount * 2 + (amount**3) + amount * 102, amount)
        embed = discord.Embed(title="Niveau Modifié!", description=f"Le niveau de {member.display_name} a été défini sur {amount}.", color=0x00ff00)
        await ctx.send(embed=embed)
    elif value.lower() == "xp":
        update_user_data(member.id, amount, 1)
        embed = discord.Embed(title="Expérience Modifiée!", description=f"L'expérience de {member.display_name} a été définie sur {amount}.", color=0x00ff00)
        await ctx.send(embed=embed)
    else:
        await ctx.send("Utilisation incorrecte. Veuillez spécifier 'lv' ou 'xp'.")

@bot.command()
async def leaderboard(ctx):
    top_users = get_top_users(10)
    
    embed = discord.Embed(title="Classement des Niveaux", color=0x00ff00)
    for index, (user_id, level, exp) in enumerate(top_users, start=1):
        user = bot.get_user(user_id)
        if user:
            embed.add_field(name=f"{index}. {user.name}", value=f"Niveau {level} - Expérience {exp}", inline=False)
    
    await ctx.send(embed=embed)

def get_top_users(limit):
    c.execute('SELECT user_id, level, exp FROM levels ORDER BY level DESC, exp DESC LIMIT ?', (limit,))
    return c.fetchall()





##########################################
#----------------------------------------#
##########################################


bot.run(token)
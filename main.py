import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta
import asyncio
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# botsetup ( ˘▽˘)っ♨
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# (ノಠ益ಠ)ノ彡┻━┻ the stupid variables
team_a = []
team_b = []
confirmed_users = set()
sub_queue = []
scrim_mode = False
scrim_time = None
reminder_time = timedelta(minutes=15)
announcement_channel_id = None
team_names = {'team_a': 'Team A', 'team_b': 'Team B'}
leaders = {}
round_winners = {"team_a": 0, "team_b": 0}
current_round = 0
match_results = []  # To store match results

class SetupView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Setup Scrim", style=discord.ButtonStyle.primary, custom_id="setup_scrim")
    async def setup_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Setup button clicked. Please follow further instructions.')

    @discord.ui.button(label="Set Match Time", style=discord.ButtonStyle.primary, custom_id="set_match_time")
    async def set_match_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please use the command `!settime YYYY-MM-DD HH:MM` to set the match time.")

    @discord.ui.button(label="Set Announcement Channel", style=discord.ButtonStyle.primary, custom_id="set_announcement_channel")
    async def set_announcement_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please use the command `!setchannel #channel_name` to set the announcement channel.")

    @discord.ui.button(label="Set Match Format", style=discord.ButtonStyle.primary, custom_id="set_match_format")
    async def set_match_format(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Please use the command `!setformat <best_of_3|best_of_5>` to set the match format.")

class JoinButton(Button):
    def __init__(self, user_id: str):
        super().__init__(label="Join Queue", style=discord.ButtonStyle.success, custom_id=f"join_{user_id}")

    async def callback(self, interaction: discord.Interaction):
        user_id = int(self.custom_id.split('_')[1])
        if interaction.user.id != user_id:
            await interaction.response.send_message("You cannot use this button to join the queue.")
            return

        if interaction.user.id in team_a or interaction.user.id in team_b:
            await interaction.response.send_message("You are already in a team.")
            return

        if 'Sub' not in [role.name for role in interaction.user.roles]:
            await interaction.response.send_message("You are not listed as a team member or a substitute. Please contact an admin to be added.")
            return

        button = JoinButton(user_id=str(interaction.user.id))
        view = View()
        view.add_item(button)
        await interaction.response.send_message(f'{interaction.user.mention}, you have joined the queue.', view=view)

@bot.command()
@commands.has_role('Admin')
async def setup(ctx):
    view = SetupView()
    await ctx.send('Click the button below to set up the scrim match.', view=view)

@bot.command()
@commands.has_role('Admin')
async def teamname(ctx, team: str, *, new_name: str):
    if team == 'team_a':
        team_names['team_a'] = new_name
    elif team == 'team_b':
        team_names['team_b'] = new_name
    else:
        await ctx.send('Invalid team name. Use "team_a" or "team_b".')
        return
    await ctx.send(f'The name of {team} has been changed to "{new_name}".')

@bot.command()
@commands.has_role('Admin')
async def endmatch(ctx):
    global team_a, team_b, scrim_mode, round_winners, current_round, confirmed_users, match_results
    team_a.clear()
    team_b.clear()
    scrim_mode = False
    round_winners = {"team_a": 0, "team_b": 0}
    current_round = 0
    confirmed_users.clear()
    match_results = []
    await ctx.send('All players have been removed from the queue and the match has been ended.')

@bot.command()
@commands.has_role('Admin')
async def remove(ctx, member: discord.Member):
    global team_a, team_b, confirmed_users
    if member.id in team_a:
        team_a.remove(member.id)
        await ctx.send(f'{member.mention} has been removed from {team_names["team_a"]}.')
    elif member.id in team_b:
        team_b.remove(member.id)
        await ctx.send(f'{member.mention} has been removed from {team_names["team_b"]}.')
    else:
        await ctx.send(f'{member.mention} is not in any team.')
    confirmed_users.discard(member.id)

@bot.command()
@commands.has_role('Admin')
async def setreminder(ctx, time: int):
    global reminder_time
    if time not in [15, 30, 45]:
        await ctx.send('Invalid reminder time. Choose 15, 30, or 45 minutes.')
        return
    reminder_time = timedelta(minutes=time)
    await ctx.send(f'Reminder time has been set to {time} minutes before the match.')

@bot.command()
async def joinqueue(ctx):
    if ctx.author.id in team_a or ctx.author.id in team_b:
        await ctx.send("You are already in a team.")
        return
    if 'Sub' not in [role.name for role in ctx.author.roles]:
        await ctx.send("You are not listed as a team member or a substitute. Please contact an admin to be added.")
        return
    button = JoinButton(user_id=str(ctx.author.id))
    view = View()
    view.add_item(button)
    await ctx.send(f'{ctx.author.mention}, click the button below to join the queue.', view=view)

@bot.command()
async def leavequeue(ctx):
    if ctx.author.id in team_a:
        team_a.remove(ctx.author.id)
        await ctx.send(f'{ctx.author.mention} has left {team_names["team_a"]}.')
        if scrim_mode:
            await ctx.send(f'{ctx.author.mention} has left the match. A substitution is needed or the match may continue without this player.')
    elif ctx.author.id in team_b:
        team_b.remove(ctx.author.id)
        await ctx.send(f'{ctx.author.mention} has left {team_names["team_b"]}.')
        if scrim_mode:
            await ctx.send(f'{ctx.author.mention} has left the match. A substitution is needed or the match may continue without this player.')
    else:
        await ctx.send('You are not in any team.')

@bot.command()
async def joinsubqueue(ctx):
    if 'Sub' not in [role.name for role in ctx.author.roles]:
        await ctx.send('You do not have the Sub role.')
        return
    if ctx.author.id in sub_queue:
        await ctx.send('You are already in the substitute queue.')
        return
    sub_queue.append(ctx.author.id)
    await ctx.send(f'{ctx.author.mention} has joined the substitute queue.')

@bot.command()
@commands.has_role('Leader')
async def approve(ctx, member: discord.Member):
    if member.id not in sub_queue:
        await ctx.send(f'{member.mention} is not in the substitute queue.')
        return

    view = View()
    approve_button = Button(label="Approve", style=discord.ButtonStyle.success, custom_id=f"approve_{member.id}")
    deny_button = Button(label="Deny", style=discord.ButtonStyle.danger, custom_id=f"deny_{member.id}")
    view.add_item(approve_button)
    view.add_item(deny_button)

    async def approve_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You do not have permission to use this button.")
            return

        if member.id in team_a or member.id in team_b:
            await interaction.response.send_message(f'{member.mention} is already in a team.')
            return

        if 'Sub' not in [role.name for role in member.roles]:
            await interaction.response.send_message(f'{member.mention} is not listed as a substitute.')
            return

        team = 'team_a' if len(team_a) <= len(team_b) else 'team_b'
        if team == 'team_a':
            team_a.append(member.id)
            await ctx.send(f'{member.mention} has been added to {team_names["team_a"]}.')
        else:
            team_b.append(member.id)
            await ctx.send(f'{member.mention} has been added to {team_names["team_b"]}.')

        sub_queue.remove(member.id)
        await interaction.response.send_message(f'{member.mention} has been approved and added to the team.')

    async def deny_callback(interaction: discord.Interaction):
        if interaction.user.id != ctx.author.id:
            await interaction.response.send_message("You do not have permission to use this button.")
            return

        sub_queue.remove(member.id)
        await interaction.response.send_message(f'{member.mention} has been denied and removed from the substitute queue.')

    approve_button.callback = approve_callback
    deny_button.callback = deny_callback

    await ctx.send(f'{ctx.author.mention}, please choose whether to approve or deny {member.mention}.', view=view)

@bot.command()
@commands.has_role('Admin')
async def scrim(ctx):
    global scrim_mode, announcement_channel_id, scrim_time
    if not announcement_channel_id:
        await ctx.send('Announcement channel is not set. Please use `!setup` to set it up.')
        return
    if not scrim_time:
        await ctx.send('Match time is not set. Please use `!settime YYYY-MM-DD HH:MM` to set the match time.')
        return
    scrim_mode = True
    announcement_channel = bot.get_channel(announcement_channel_id)
    embed = discord.Embed(title="Scrim Match Started", color=discord.Color.green())
    embed.add_field(name="Teams", value=f"{team_names['team_a']} vs {team_names['team_b']}", inline=False)
    embed.add_field(name="Match Time", value=scrim_time.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
    await announcement_channel.send(embed=embed)

@bot.command()
@commands.has_role('Leader')
async def report(ctx, result: str):
    global current_round, round_winners, match_results
    if not scrim_mode:
        await ctx.send('No active match to report.')
        return
    if result not in ['team_a', 'team_b']:
        await ctx.send('Invalid result. Use "team_a" or "team_b".')
        return
    round_winners[result] += 1
    current_round += 1
    match_results.append({
        'round': current_round,
        'winner': result,
        'score': f'Team A {round_winners["team_a"]} - Team B {round_winners["team_b"]}',
        'players': {
            'team_a': [bot.get_user(uid) for uid in team_a],
            'team_b': [bot.get_user(uid) for uid in team_b]
        }
    })
    announcement_channel = bot.get_channel(announcement_channel_id)
    embed = discord.Embed(title=f"Round {current_round} Result", color=discord.Color.blue())
    embed.add_field(name="Winner", value=f"{team_names[result]}", inline=False)
    embed.add_field(name="Score", value=f"Team A {round_winners['team_a']} - Team B {round_winners['team_b']}", inline=False)
    embed.add_field(name="Team A Players", value=", ".join([bot.get_user(uid).name for uid in team_a]), inline=False)
    embed.add_field(name="Team B Players", value=", ".join([bot.get_user(uid).name for uid in team_b]), inline=False)
    await announcement_channel.send(embed=embed)

@bot.command()
async def scrimlist(ctx):
    if not scrim_mode:
        await ctx.send('No active scrim match.')
        return
    team_a_members = [bot.get_user(uid) for uid in team_a]
    team_b_members = [bot.get_user(uid) for uid in team_b]
    embed = discord.Embed(title="Current Scrim Teams", color=discord.Color.orange())
    embed.add_field(name="Team A", value=", ".join([member.name for member in team_a_members if member]), inline=False)
    embed.add_field(name="Team B", value=", ".join([member.name for member in team_b_members if member]), inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def socials(ctx):
    await ctx.send('Creator’s social media handles:\n'
                   'Twitter: [twitter.com/creator](https://twitter.com/creator)\n'
                   'YouTube: [youtube.com/creator](https://youtube.com/creator)\n'
                   'Instagram: [instagram.com/creator](https://instagram.com/creator)')

@bot.command()
async def bot_help(ctx):
    help_message = (
        "**Scrim Bot Commands**\n\n"
        "**!setup** - Set up the scrim match with team names, match time, announcement channel, and match format.\n"
        "**!teamname <team> <new_name>** - Rename the team. Replace `<team>` with `team_a` or `team_b`.\n"
        "**!endmatch** - End the current match and clear teams.\n"
        "**!remove <@member>** - Remove a member from their current team.\n"
        "**!setreminder <15|30|45>** - Set the reminder time for the match in minutes.\n"
        "**!joinqueue** - Join the team queue. Only available for team members or substitutes.\n"
        "**!leavequeue** - Leave the queue. Removes you from your current team.\n"
        "**!joinsubqueue** - Join the substitute queue. Only available for users with the 'Sub' role.\n"
        "**!approve <@member>** - Approve a substitute to join a team.\n"
        "**!scrim** - Announce the start of the scrim match in the set announcement channel.\n"
        "**!report <team_a|team_b>** - Report the result of the current round.\n"
        "**!scrimlist** - Display the list of members in each team.\n"
        "**!socials** - Display creator's social media handles.\n"
        "**!help** - Show this help message.\n"
    )
    await ctx.send(help_message)

@bot.command()
@commands.has_role('Admin')
async def setchannel(ctx, channel: discord.TextChannel):
    global announcement_channel_id
    announcement_channel_id = channel.id
    await ctx.send(f'Announcement channel has been set to {channel.mention}.')

bot.run(DISCORD_TOKEN)

import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
from datetime import datetime, timedelta
import asyncio

# botsetup ( ˘▽˘)っ♨
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# (ノಠ益ಠ)ノ彡┻━┻ the stupid vairables
team_a = []
team_b = []
leaders = {}  # Team Leaders is stored
subs = []
confirmed_users = set()  # Set of Discord IDs who confirmed their participation
scrim_mode = False
team_names = {"team_a": "Team A", "team_b": "Team B"}
announcement_channel_id = None
scrim_time = None
match_format = None
current_round = 0
round_winners = {"team_a": 0, "team_b": 0}
sub_queue = []  # Sub Queue
reminder_time = timedelta(minutes=15)  # Reminder DM timere - default 15 minutes before the match

# Discord bot SetupView for the initial setup
class SetupView(View):
    def __init__(self):
        super().__init__()

    @discord.ui.button(label="Setup Scrim", style=discord.ButtonStyle.primary, custom_id="setup_scrim")
    async def setup_scrim(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Your setup logic here
        await interaction.response.send_message('Setup button clicked. Please follow further instructions.')

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

@tasks.loop(seconds=60.0)
async def check_match_time_reminder():
    if scrim_time:
        now = datetime.utcnow()
        time_diff = scrim_time - now
        if reminder_time <= time_diff <= reminder_time + timedelta(minutes=1):  # Reminder
            players_to_notify = confirmed_users.union(leaders.keys())
            for player_id in players_to_notify:
                user = bot.get_user(player_id)
                if user:
                    await user.send(f"Reminder: The scrim match will start in {reminder_time.seconds // 60} minutes at <t:{int(scrim_time.timestamp())}:f>!")
        elif time_diff <= timedelta(seconds=60) and time_diff > timedelta(seconds=0):  # Reminder when time is near
            players_to_notify = confirmed_users.union(leaders.keys())
            for player_id in players_to_notify:
                user = bot.get_user(player_id)
                if user:
                    await user.send(f"Reminder: The scrim match is starting in less than a minute!")

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
    global team_a, team_b, scrim_mode, round_winners, current_round, confirmed_users

    # Clear the team lists and reset match status
    team_a.clear()
    team_b.clear()
    scrim_mode = False
    round_winners = {"team_a": 0, "team_b": 0}
    current_round = 0
    confirmed_users.clear()  # Clear confirmed users
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

    # Remove from confirmed users if they were confirmed
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

    # Prompt for confirmation with emoji reactions
    message = await ctx.send(f'{member.mention}, confirm or deny the substitution by reacting with ✅ or 🚫.')
    await message.add_reaction('✅')
    await message.add_reaction('🚫')

    def check(reaction, user):
        return user == member and reaction.message.id == message.id and str(reaction.emoji) in ['✅', '🚫']

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
        if str(reaction.emoji) == '✅':
            if len(team_a) <= len(team_b):
                team_a.append(member.id)
                await ctx.send(f'{member.mention} has been added to {team_names["team_a"]}.')
            else:
                team_b.append(member.id)
                await ctx.send(f'{member.mention} has been added to {team_names["team_b"]}.')
            sub_queue.remove(member.id)
            confirmed_users.add(member.id)  # Mark as confirmed
        else:
            await ctx.send(f'{member.mention} has declined the substitution.')
    except asyncio.TimeoutError:
        await ctx.send('You took too long to respond.')

@bot.command()
@commands.has_role('Leader')
async def scrim(ctx):
    global scrim_mode, scrim_time, announcement_channel_id

    if scrim_mode:
        await ctx.send('A scrim match is already active.')
        return

    scrim_time = datetime.utcnow() + timedelta(minutes=15)  # Example time setup; should be set as per actual requirement
    scrim_mode = True
    announcement_channel = bot.get_channel(announcement_channel_id)
    if announcement_channel:
        await announcement_channel.send(f"The scrim match between {team_names['team_a']} and {team_names['team_b']} is starting soon!")
    await ctx.send('The scrim match has been announced.')

@bot.command()
@commands.has_role('Leader')
async def report(ctx, result: str):
    global current_round, round_winners

    if not scrim_mode:
        await ctx.send('No active match to report.')
        return

    if result not in ['team_a', 'team_b']:
        await ctx.send('Invalid result. Use "team_a" or "team_b".')
        return

    round_winners[result] += 1
    current_round += 1
    await ctx.send(f'Round {current_round} result: {result} wins. Current score: Team A {round_winners["team_a"]} - Team B {round_winners["team_b"]}')

@bot.command()
async def scrimlist(ctx):
    if not scrim_mode:
        await ctx.send('No active scrim match.')
        return

    embed = discord.Embed(title="Scrim Teams")
    embed.add_field(name=f"{team_names['team_a']}", value=', '.join(f"<@{user_id}>" for user_id in team_a) if team_a else "No players", inline=False)
    embed.add_field(name=f"{team_names['team_b']}", value=', '.join(f"<@{user_id}>" for user_id in team_b) if team_b else "No players", inline=False)
    await ctx.send(embed=embed)

@bot.command()
async def socials(ctx):
    await ctx.send("Check out my socials: Twitter: @XXXXX | Twitch: twitch.tv/XXXX")

@bot.command()
async def help(ctx):
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
        "**!override** - Override team presence requirements for starting the match.\n"
        "**!report <team_a|team_b>** - Report the result of the current round.\n"
        "**!scrimlist** - Display the list of members in each team.\n"
        "**!socials** - Display creator's social media handles.\n"
        "**!help** - Show this help message.\n"
    )
    await ctx.send(help_message)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    check_match_time_reminder.start()  # Start the reminder task

# Run the bot with the token
bot.run('BOT_TOKEN')

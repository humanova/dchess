# 2020 Emir Erbasan (humanova)
# MIT License, see LICENSE for more details
import discord
import requests
from utils import confparser, permissions, default
from discord.ext import tasks, commands
from io import BytesIO
import time
from operator import itemgetter
from tabulate import tabulate

API_URL = "https://bruh.uno/dchess/api"
end_status = {
    'mate' : 'Mate',
    'outoftime' : 'Out of time',
    'draw' : 'Draw',
    'resign' : 'Resign',
    'stalemate' : 'Stalemate'
}

class DChess(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = confparser.get("config.json")
        self.games = []

        self.chess_task_loop.start()

    def cog_unload(self):
        self.chess_task_loop.cancel()

    def get_destination(self, no_pm: bool = False):
        if no_pm:
            return self.context.channel
        else:
            return self.context.author

    def parse_clock_setting(self, clock:str):
        try:
            s = clock.split("+")
            minutes = int(s[0])
            increment = round(int(s[1]))
            if minutes == 0: return None
            return {"minutes" : minutes, "increment": increment}
        except:
            return None

    async def send_create_match_request(self, host: discord.Member, guest: discord.Member, guild: discord.Guild,
                                        clock:dict=None):
        content = {"user_id": host.id,
                   "user_nick": str(host),
                   "opponent_id": guest.id,
                   "opponent_nick": str(guest),
                   "guild_id": guild.id}
        if clock:
            content.update(clock_minutes = clock['minutes'])
            content.update(clock_increment = clock['increment'])
        try:
            r = requests.post(f"{API_URL}/create_match", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    async def send_update_match_request(self, match_id: str, result: str, white_id :str, black_id: str):
        content = {"match_id": match_id,
                   "match_result": result,
                   "white_id": white_id,
                   "black_id": black_id}
        try:
            r = requests.post(f"{API_URL}/update_match", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    async def send_update_match_end_request(self, match_id: str):
        content = {"match_id": match_id}
        try:
            r = requests.post(f"{API_URL}/update_match_end", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    async def send_get_match_request(self, match_id: str):
        content = { "match_id": match_id}
        try:
            r = requests.post(f"{API_URL}/get_match", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    async def send_get_player_request(self, player_id, guild_id=None):
        content = {"player_id": player_id}
        if guild_id:
            content.update(guild_id=guild_id)
        try:
            r = requests.post(f"{API_URL}/get_player", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    async def send_get_guild_request(self, guild_id):
        content = { "guild_id": guild_id}
        try:
            r = requests.post(f"{API_URL}/get_guild", timeout=4.0, json=content)
            response = r.json()
            return response
        except Exception as e:
            print(e)

    # returns png obj
    async def send_get_match_preview_request(self, match_id: str, move):
        try:
            r = requests.get(f"{API_URL}/get_match_preview/{match_id}/{move}.png", timeout=4.0)
            return BytesIO(r.content)
        except Exception as e:
            print(e)

    async def send_error_embed(self, ctx, message, fields=None):
        if fields is None: fields = []
        try:
            embed = discord.Embed(title=" ", description=message, color=0xFF0000)
            embed.set_author(name="dChess", icon_url=self.bot.user.avatar_url)
            for f in fields:
                embed.add_field(name=f['name'], value=f['value'])
            await ctx.send(embed=embed)
        except discord.Forbidden:
            pass

    async def cancel_game(self, game:dict):
        try:
            self.games.remove(game)
            await self.send_error_embed(ctx=game["msg"].channel,
                                        message=f"Match has been canceled. (<@{game['host'].id}> v <@{game['guest'].id}>)")
            await game["msg"].delete()
        except (discord.Forbidden, discord.NotFound):
            pass
        except Exception as e:
            print(f"error while canceling game : {e}")

    async def send_game_invite_embed(self, ctx, member: discord.Member, match_data, is_dm:bool=False, show_clock:bool=False):
        match = match_data
        match_id = match["db_match"]["id"]
        match_url = f"https://lichess.org/{match_id}"
        match_type = None
        match_clock = None

        embed = discord.Embed(title=":chess_pawn: Game Invite", color=0x00ffff)
        embed.add_field(name="Host", value=f"<@{ctx.author.id}>", inline=True)
        embed.set_footer(text="Specify your color by reacting to this message after match started.")

        if show_clock:
            match_type = match['match']['challenge']['speed']
            match_clock = match['match']['challenge']['timeControl']['show']
            embed.add_field(name="Type", value=f"{match_type} ({match_clock})", inline=True)
        embed.add_field(name="Guild", value=f"{ctx.guild.name}", inline=False)

        if is_dm:
            embed.add_field(name="URL", value=f"{match_url}", inline=False)
            try:
                await member.send(embed=embed)
                await ctx.author.send(embed=embed)
                return True
            except discord.Forbidden:
                await self.send_error_embed(ctx=ctx, message="Couldn't send private message.",
                                            fields=[{'name': 'Help', 'value': 'Check your privacy settings.'}])
                return False
        else:
            embed.add_field(name="URL", value=f"Sent as DM.", inline=False)
            msg = await ctx.send(embed=embed)
            return msg

    async def get_player_stat_embed(self, player:discord.Member, guild:discord.Guild):
        pl = await self.send_get_player_request(player.id, guild.id)
        if pl['success']:
            embed = discord.Embed(title="Stats", color=0x00ffff)
            embed.add_field(name="Player", value=f"<@{player.id}>", inline=True)
            embed.add_field(name="Guild Elo", value=f"{int(pl['guild_player']['elo'])}", inline=True)
            embed.add_field(name="Matches", value=f"{pl['player']['matches']}", inline=False)
            embed.add_field(name="Wins", value=f"{pl['player']['wins']}", inline=True)
            embed.add_field(name="Draws", value=f"{pl['player']['draws']}", inline=True)
            embed.add_field(name="Losses", value=f"{pl['player']['loses']}", inline=True)
            if pl['player']['last_match_id'] != '':
                embed.add_field(name="Last match", value=f"https://lichess.org/{pl['player']['last_match_id']}",
                                inline=False)
            return embed
        else:
            return None

    @tasks.loop(seconds=1)
    async def chess_task_loop(self):
        if len(self.games) > 0:
            for game in self.games:
                # bad exception handling but yeah
                try:
                    game_data = await self.send_get_match_request(game["match_id"])
                    if not game["white_data"] and game['white_id']:
                        game["white_data"] = await self.send_get_player_request(player_id=game["white_id"],
                                                                                guild_id=game["guild_id"])
                    if not game["black_data"] and game['black_id']:
                        game["black_data"] = await self.send_get_player_request(player_id=game["black_id"],
                                                                                guild_id=game["guild_id"])
                    if game_data["success"] == False:
                        if time.time() - game["timestamp"] > 180:
                            await self.cancel_game(game)

                    if game_data["success"]:
                        status = game_data["match"]["status"]
                        moves = game_data["match"]["moves"]
                        match_type = game["match_type"]
                        match_clock = game["match_clock"]
                        move_count = len(moves.split(" "))
                        game["moves"] = moves

                        preview_url = f"{API_URL}/get_match_preview/{game['match_id']}/{move_count}"
                        white_player = f"<@{game['white_id']}> ({int(game['white_data']['guild_player']['elo'])})" if game['white_id'] else "Unknown"
                        black_player = f"<@{game['black_id']}> ({int(game['black_data']['guild_player']['elo'])})" if game['black_id'] else "Unknown"

                        embed = discord.Embed(title=f":chess_pawn: {game['host'].name} vs {game['guest'].name}",
                                              color=0x00ffff)
                        embed.add_field(name="⚪White", value=white_player, inline=True)
                        embed.add_field(name="⚫Black", value=black_player, inline=True)
                        if match_type:
                            embed.add_field(name="Type", value=f"{match_type} ({match_clock})", inline=True)
                        if status == "started":
                            # update embed msg every 3 moves
                            if move_count > game["move_count"] and move_count % 3 == 0:
                                game['last_move_timestamp'] = time.time()
                                embed.add_field(name="Status", value="Ongoing", inline=False)
                                embed.add_field(name="URL", value=game["match_url"], inline=True)
                                embed.add_field(name="Moves", value=moves, inline=False)
                                embed.set_image(url=preview_url)
                                try:
                                    await game["msg"].edit(embed=embed)
                                except (discord.NotFound, discord.Forbidden):
                                    await self.cancel_game(game)

                            elif move_count < 10 and time.time() - game["last_move_timestamp"] > 300:
                                await self.cancel_game(game)
                            elif move_count < 50 and time.time() - game["last_move_timestamp"] > 2000:
                                await self.cancel_game(game)

                        elif status in end_status:
                            m_data = await self.send_update_match_end_request(match_id=game["match_id"])

                            embed.add_field(name="Status", value=end_status[status], inline=False)
                            if not status == "draw" and not status == "stalemate":
                                winner = game_data["match"]["winner"]
                                winner_player = f"<@{game[f'{winner}_id']}>" if game[f'{winner}_id'] else winner
                                embed.add_field(name="Winner", value=winner_player, inline=True)
                            embed.add_field(name="URL", value=game["match_url"], inline=False)
                            embed.add_field(name="Moves", value=moves, inline=True)
                            embed.set_image(url=f"{API_URL}/get_match_preview/{game['match_id']}/last")
                            try:
                                await game["msg"].edit(embed=embed)
                            except (discord.NotFound, discord.Forbidden):
                                await self.cancel_game(game)

                            self.games.remove(game)
                        game["move_count"] = move_count
                except Exception as e:
                    print(f"Error in chess task loop : {e}")


    @commands.command()
    @commands.guild_only()
    async def chess(self, ctx, member: discord.Member, clock_setting:str=None):
        ''' Creates a match and sends an invite to mentioned user
            You can pass clock setting as a parameter
            Usage:
                    - !chess @user
                    - !chess @user 2+1
        '''
        if ctx.author == member:
            await self.send_error_embed(ctx, message="You can not invite yourself.")
            return
        elif ctx.author in [g['host'] for g in self.games]:
            await self.send_error_embed(ctx, message="You can not create more than one match at a time.",
                                        fields=[{'name': 'Help', 'value': "To cancel previous game : `!ccancel`"}])
            return

        match = await self.send_create_match_request(host=ctx.author, guest=member, guild=ctx.guild,
                                                     clock=self.parse_clock_setting(clock_setting))
        try:
            if match['success']:
                dm_success = await self.send_game_invite_embed(ctx, member=member, match_data=match, is_dm=True)
                if not dm_success:
                    return
                msg = await self.send_game_invite_embed(ctx, member=member, match_data=match, is_dm=False)
                await msg.add_reaction('⚪')
                await msg.add_reaction('⚫')

                match_id = match["db_match"]["id"]
                match_url = f"https://lichess.org/{match_id}"
                match_type = None
                match_clock = None
                timetamp = time.time()
                match_type = match['match']['challenge']['speed']
                match_clock = match['match']['challenge']['timeControl']['show']

                self.games.append({"msg": msg,
                                   "match_id": match_id,
                                   "match_url": match_url,
                                   "match_type": match_type,
                                   "match_clock": match_clock,
                                   "guild_id": ctx.guild.id,
                                   "host": ctx.author,
                                   "guest": member,
                                   "white_data": None,
                                   "black_data": None,
                                   "timestamp": timetamp,
                                   "last_move_timestamp": timetamp,
                                   "move_count": 1, # lichess starts counting from 1 lol (1,1,2)
                                   "moves": None,
                                   "white_id": None,
                                   "black_id": None,})
        except Exception as e:
            print(f"error while creating match : {e}")

    @commands.command()
    @commands.guild_only()
    async def cstats(self, ctx, arg=None):
        """ Sends player/guild stats
            Usage:
                - !cstats
                - !cstats @player
                - !cstats guild
        """
        if not arg:
            embed = await self.get_player_stat_embed(ctx.author, ctx.guild)
            if embed:
                await ctx.send(embed=embed)
            else:
                await self.send_error_embed(ctx, message="Couldn't find mentioned player.")
        elif arg:
            if ctx.message.mentions:
                for m in ctx.message.mentions:
                    embed = await self.get_player_stat_embed(m, ctx.guild)
                    if embed:
                        await ctx.send(embed=embed)
                    else:
                        await self.send_error_embed(ctx, message="Couldn't find mentioned player.")
            elif arg == "guild":
                g = await self.send_get_guild_request(ctx.guild.id)
                if g['success'] and len(g['guild']) > 0:
                    players = g['guild']
                    players = sorted(players, key=itemgetter('elo'), reverse=True)

                    top_players = []
                    for pl in players[:20]:
                        pl_nick = str(ctx.guild.get_member(int(pl['player_id'])))
                        if '```' in pl_nick: continue # gencoya gelsin :)
                        top_players.append([pl_nick, int(pl['elo'])])

                    table_str = tabulate(top_players, headers=["Player", "Guild elo"])
                    await ctx.send(f'```{table_str}```')
                else:
                    await self.send_error_embed(ctx, message="Couldn't find guild record.")

    @commands.command()
    @commands.guild_only()
    async def ccancel(self, ctx):
        """ Cancels created match
            Notes: If match has started, at most 6 moves must've been played.
        """
        for g in self.games:
            if g['host'] == ctx.author:
                if g['move_count'] <= 6:
                    await self.cancel_game(g)
                    return
                else:
                    await self.send_error_embed(ctx,
                                                message="At most 6 moves must've been played to cancel the match.")
                    return
        await self.send_error_embed(ctx, message="You don't have any ongoing matches.")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        game = [g for g in self.games if message.id == g['msg'].id]
        if game:
            await self.cancel_game(game[0])

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        for g in self.games:
            if user.id == g["host"].id or user.id == g["guest"].id:
                if reaction.message.id == g["msg"].id:
                    if user.id == g["host"].id:
                        if reaction.emoji == "⚪":
                            g["white_id"] = user.id
                        elif reaction.emoji == '⚫':
                            g["black_id"] = user.id
                    else:
                        if reaction.emoji == "⚪":
                            g["white_id"] = user.id
                        elif reaction.emoji == '⚫':
                            g["black_id"] = user.id

                    if g["white_id"] is not None and g["black_id"] is not None:
                        if not g["white_id"] == g["black_id"]:
                            match = await self.send_update_match_request(match_id=g["match_id"], result="unfinished",
                                                                         white_id=g["white_id"], black_id=g["black_id"])
                            #if match["success"]:
                            #    print("successfully updated match")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        for g in self.games:
            if user.id == g["host"].id or user.id == g["guest"].id:
                if reaction.message.id == g["msg"].id:
                    if user.id == g["host"].id:
                        if reaction.emoji == "⚪":
                            g["white_id"] = None
                        elif reaction.emoji == '⚫':
                            g["black_id"] = None
                    else:
                        if reaction.emoji == "⚪":
                            g["white_id"] = None
                        elif reaction.emoji == '⚫':
                            g["black_id"] = None

def setup(bot):
    bot.add_cog(DChess(bot))
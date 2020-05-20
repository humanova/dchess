# 2019 Emir Erbasan (humanova)
# MIT License, see LICENSE for more details

import discord
from utils import confparser, default
from discord.ext import commands
import psutil
from datetime import datetime
import os

class Info(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.config = confparser.get("config.json")
        self.process = psutil.Process(os.getpid())

    @commands.command(aliases=['developer'])
    async def dev(self, ctx):
        """ Sends developer info """
        embed = discord.Embed(title=" ", color=0x75df00)
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        embed.add_field(name="Developer", value=f"<@{self.config.owners[0]}>", inline=False)
        embed.add_field(name="GitHub", value="https://github.com/humanova", inline=False)

        await ctx.send(embed=embed)

    @commands.command()
    async def support(self, ctx):
        """ Sends support server invite """
        embed = discord.Embed(title=" ", description="**[Invite](https://discord.gg/N5c2JVK)**", color=0x75df00)
        embed.set_author(name="dChess Support", icon_url=self.bot.user.avatar_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['stats'])
    async def info(self, ctx):
        """ Sends bot information  """
        ram_usage = self.process.memory_full_info().rss / 1024 ** 2
        embed_color = discord.Embed.Empty
        if hasattr(ctx, 'guild') and ctx.guild is not None:
            embed_color = ctx.me.top_role.colour

        user_count = len(self.bot.users)

        embed = discord.Embed(colour=embed_color)
        embed.set_thumbnail(url=ctx.bot.user.avatar_url)
        embed.add_field(name="Last boot", value=default.timeago(datetime.now() - self.bot.boot_time), inline=False)
        embed.add_field(name="Servers", value=f"{len(ctx.bot.guilds)}", inline=False)
        embed.add_field(name="Users", value=f"{user_count}", inline=False)
        embed.add_field(
            name=f"Dev",
            value=f"{str(self.bot.get_user(self.config.owners[0]))}",
            inline=True)
        embed.add_field(name="RAM usage", value=f"{ram_usage:.2f} MB", inline=True)

        await ctx.send(content=f"**{ctx.bot.user}** | **{self.config.version}**", embed=embed)

def setup(bot):
    bot.add_cog(Info(bot))
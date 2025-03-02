from __future__ import annotations
from ast import alias
import bisect
import logging
import re
from typing import TYPE_CHECKING, Dict

import discord
from discord.ext import commands, tasks
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

import consts
import models

if TYPE_CHECKING:
    from bot import LXVBot

# TODO dev


logger = logging.getLogger(__name__)

class Level(commands.GroupCog, group_name="level"):
    def __init__(self, bot: LXVBot) -> None:
        self.bot = bot
        self.guild = None
        self.mod_ids = set()
        self.user_mods = set()
        self.role_assigns = []
        self.role_level_ids = []

    def is_mod(self, member: discord.Member, include_bot_owner: bool = True) -> bool:
        if member.bot:
            return False
        if member.id in self.user_mods:
            return True
        allowed = False
        if (include_bot_owner and self.bot.owner.id == member.id) or member.guild_permissions.administrator:
            allowed = True
            self.user_mods.add(member.id)
        else:
            for r in member.roles:
                if r.id in self.mod_ids:
                    allowed = True
                    self.user_mods.add(member.id)
                    break
        return allowed

    def mod_only(self, ctx, include_bot_owner: bool = True) -> bool:
        return self.is_mod(ctx.author, include_bot_owner)
    
    async def cog_check(self, ctx: commands.Context):
        return ctx.guild is not None and ctx.guild.id == consts.GUILD_ID
    
    async def cog_load(self):
        if self.guild is None:
            self.guild = self.bot.get_guild(consts.GUILD_ID) or await self.bot.fetch_guild(consts.GUILD_ID)

        await self.get_setting()
        self.refresh_cache.start()

    async def get_setting(self):
        async_session = async_sessionmaker(self.bot.engine, expire_on_commit=False)
        async with async_session() as session:
            mods = await session.execute(select(models.Mod.id))
            self.mod_ids = {row[0] for row in mods}

            self.role_assigns = []
            self.role_level_ids = []
            role_assigns = await session.execute(select(models.RoleAssign))
            for row in role_assigns.scalars():
                bisect.insort(self.role_assigns, (row.level, row.role_id))
                self.role_level_ids.append(row.role_id)

    @tasks.loop(minutes=1)
    async def refresh_cache(self):
        self.user_mods = set()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since is not None and after.premium_since is None:
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message): 
        if message.guild is None:
            return
        if message.author.id == consts.LEVEL_BOT_ID and message.channel.id == consts.LEVEL_UP_CHANNEL_ID and message.mentions:
            user = message.mentions[0]
            if not isinstance(user, discord.Member):
                return
            match = re.search(r"advanced to level (\d+)!", message.content)
            if match:
                level = int(match.group(1))
                idx = bisect.bisect_right(self.role_assigns, (level, 99999999999999999999)) - 1
                if idx >= 0:
                    role_id = self.role_assigns[idx][1]
                    removed = []
                    assign = True
                    for role in user.roles:
                        if role.id == role_id:
                            assign = False
                        else:
                            idx = bisect.bisect_left(self.role_level_ids, role.id)
                            if idx < len(self.role_level_ids) and self.role_level_ids[idx] == role.id:
                                removed.append(role)
                    if assign:
                        await user.add_roles(discord.Object(role_id))
                    if removed:
                        await user.remove_roles(*removed)
            return
        if message.author.bot:
            return

    @commands.hybrid_command(name="levelrole", aliases=["lr"])    
    async def level_role(self, ctx: commands.Context):
        if not self.mod_only(ctx):
            return ctx.reply("You are not allowed to use this command", ephemeral=True)
        embed = discord.Embed(title="Level roles", color=discord.Colour.random())
        for level, role_id in self.role_assigns:
            embed.add_field(name=f"Level {level}", value=f"<@&{role_id}>", inline=False)
        
        await ctx.reply(embed=embed)
        
    @commands.hybrid_command(name="setlevelrole", aliases=["slr"])
    async def set_level_role(self, ctx: commands.Context, role: discord.Role, level: int):
        if not self.mod_only(ctx):
            return ctx.reply("You are not allowed to use this command", ephemeral=True)
        if level < -1:
            return ctx.reply("Invalid level", mention_author=False)
        
        async_session = async_sessionmaker(self.bot.engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                if level == -1:
                    # Delete role with id
                    await session.execute(delete(models.RoleAssign).where(models.RoleAssign.role_id == role.id))
                else:
                    cursor = await session.execute(select(models.RoleAssign).where(models.RoleAssign.role_id == role.id))
                    cur_role = cursor.scalar_one_or_none()
                    if cur_role is None:
                        cur_role = models.RoleAssign(role_id=role.id, level=level)
                        session.add(cur_role)
                    else:
                        cur_role.level = level
        if level == -1:
            await ctx.reply(f"Removed role {role.mention}", ephemeral=True)
        else:
            await ctx.reply(f"Set role {role.mention} to level {level}", ephemeral=True)
        await self.get_setting()

async def setup(bot: LXVBot):
    await bot.add_cog(Level(bot))
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Optional

import discord
from discord.ext import commands, tasks
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import async_sessionmaker

import check
import consts
import models
from utils.view_util import ConfirmEmbed

if TYPE_CHECKING:
    from bot import LXVBot

logger = logging.getLogger(__name__)


class Role(commands.GroupCog, group_name="customrole"):
    def __init__(self, bot: LXVBot):
        self.bot = bot
        self._custom_role_cache: Dict[int, int] = {}

    def cog_check(self, ctx: commands.Context):
        return ctx.guild is not None and ctx.guild.id == consts.GUILD_ID

    async def cog_load(self):
        self.refresh_cache.start()

    @tasks.loop(seconds=60)
    async def refresh_cache(self):
        self._custom_role_cache = {}

    async def retrieve_custom_role_id(self, member_id: int) -> Optional[int]:
        if member_id in self._custom_role_cache:
            return self._custom_role_cache[member_id]
        
        async_session = async_sessionmaker(self.bot.engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == member_id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    self._custom_role_cache[member_id] = cur_role.role_id
                    return cur_role.role_id
                
        return None

    @commands.command(name="createassignrole", aliases=["car"])
    @check.is_mod()
    async def create_role(self, ctx: commands.Context, user: discord.User, above_role: Optional[discord.Role] = None, *, name: str):
        """
        Create and assign custom role from user, set above_role to reposition its role
        """
        if ctx.guild is None:
            return
        
        async_session = async_sessionmaker(self.bot.engine)
        async with async_session() as session:
            async with session.begin():
                role = await ctx.guild.create_role(name=name, reason=f"Creation custom role by {ctx.author.name} ({ctx.author.id})")

                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == user.id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    return await ctx.reply("User already has a custom role", delete_after=5)

                session.add(models.CustomRole(user_id=user.id, role_id=role.id))

        await role.edit(position=above_role.position if above_role is not None else 0)

    @commands.command("removeassignrole", aliases=["rar"])
    @check.is_mod()
    async def remove_role(self, ctx: commands.Context, user: discord.User, delete_role: bool = False):
        """
        Remove custom role from user, optionally delete the role
        """
        if ctx.guild is None:
            return

        role_id = await self.retrieve_custom_role_id(user.id)
        if role_id is None:
            return await ctx.reply("User does not have a custom role", delete_after=5)
        
        role = ctx.guild.get_role(role_id) or await ctx.guild.fetch_role(role_id)
        async_session = async_sessionmaker(self.bot.engine)
        async with async_session() as session:
            async with session.begin():
                await session.execute(delete(models.CustomRole).where(models.CustomRole.user_id == user.id))

                if delete_role:
                    await role.delete(reason=f"Deletion custom role by {ctx.author.name} ({ctx.author.id})")

        await ctx.reply(f"{'Deleted' if delete_role else 'Removed'} role {role.mention} from user {user.mention}", mention_author=False)

    @commands.command(name="assignrole", aliases=["ar"])
    @check.is_mod()
    async def assign_role(self, ctx: commands.Context, role: discord.Role, user: discord.User):
        async_session = async_sessionmaker(self.bot.engine, expire_on_commit=False)
        async with async_session() as session:
            async with session.begin():
                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == user.id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    if cur_role.role_id != role.id:
                        confirm_embed = discord.Embed(
                            title="Confirm custom role change",
                            description=f"User {user.mention} already has a custom role <@&{cur_role.role_id}>\n"
                            f"Are you sure you want to change it to <@&{role.id}>?",
                        )
                        confirm = ConfirmEmbed(ctx.author.id, confirm_embed)
                        await confirm.send(ctx)
                        await confirm.wait()
                        if not confirm.value:
                            return
                        cur_role.role_id = role.id
                    else:
                        await ctx.reply(f"User **{user.name}** already has role **{role.name}**")
                        return
                else:    
                    cur_role = models.CustomRole(user_id=user.id, role_id=role.id)

                session.add(cur_role)

        self._custom_role_cache[user.id] = role.id

        await ctx.reply(f"Set role {role.mention} to user {user.mention}", mention_author=False)
        
        if self.refresh_cache.is_running():
            self.refresh_cache.restart()

    @commands.hybrid_command(name="setrolename", aliases=["srn"])
    async def set_role_name(self, ctx: commands.Context, *, name: str):
        if ctx.guild is None:
            return
        if len(name) > 32:
            return await ctx.reply("Role name must be less than 32 characters", ephemeral=True)
        role_id = await self.retrieve_custom_role_id(ctx.author.id)
        if role_id is None:
            return await ctx.reply("You do not have a custom role", ephemeral=True)
        role = ctx.guild.get_role(role_id) or await ctx.guild.fetch_role(role_id)
        await role.edit(name=name)
        await ctx.reply(f"Set role name to {role.name}", mention_author=False)

    @commands.hybrid_command(name="setrolecolour", aliases=["setrolecolor", "src"])
    async def set_role_colour(self, ctx: commands.Context, colour: discord.Colour):
        if ctx.guild is None:
            return
        role_id = await self.retrieve_custom_role_id(ctx.author.id)
        if role_id is None:
            return await ctx.reply("You do not have a custom role", ephemeral=True)
        role = ctx.guild.get_role(role_id) or await ctx.guild.fetch_role(role_id)
        await role.edit(colour=colour)
        await ctx.reply(f"Set role colour to {role.colour}", mention_author=False)

async def setup(bot: LXVBot):
    await bot.add_cog(Role(bot))

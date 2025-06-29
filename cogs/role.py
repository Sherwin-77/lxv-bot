from __future__ import annotations
from io import BytesIO
import logging
from typing import TYPE_CHECKING, Dict, Optional

import discord
from discord.ext import commands, tasks
import discord.http
from sqlalchemy import JSON, bindparam, func, select, delete, text

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
        self.report_roles.start()

    @tasks.loop(seconds=60)
    async def refresh_cache(self):
        self._custom_role_cache = {}

    @tasks.loop(hours=12)
    async def report_roles(self):
        guild = self.bot.get_guild(consts.GUILD_ID)
        ch = guild.get_channel(765818685922213948)  # type: ignore
        if ch is None:
            return await self.bot.send_owner(f"Your lxv channel is missing. Previously channel id {765818685922213948}")
        async with self.bot.async_session() as session:
            cursor = await session.execute(select(func.count(models.CustomRole.user_id)))
            count = cursor.scalar()

        async with self.bot.engine.connect() as conn:
            await conn.execute(
                text("INSERT INTO health_reports (data, created_at) VALUES (:data, NOW())")
                .bindparams(
                    bindparam("data", value={"total_custom_roles": count}, type_=JSON),
                )
            )
            await conn.execute(
                text("DELETE FROM health_reports WHERE created_at < NOW() - INTERVAL '7 DAY'")
            )
            await conn.commit()

        await ch.send(f"Total custom roles: {count}")  # type: ignore

    @report_roles.before_loop
    async def before_report_roles(self):
        await self.bot.wait_until_ready()

    async def retrieve_custom_role_id(self, member_id: int) -> Optional[int]:
        if member_id in self._custom_role_cache:
            return self._custom_role_cache[member_id]

        async with self.bot.async_session() as session:
            async with session.begin():
                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == member_id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    self._custom_role_cache[member_id] = cur_role.role_id
                    return cur_role.role_id

        return None

    @commands.command(name="createrole", aliases=["cr"])
    @check.is_mod()
    async def create_role(self, ctx: commands.Context, member: discord.Member, *, name: str):
        """
        Create and assign custom role from user, set above_role to reposition its role
        """
        if ctx.guild is None:
            return

        async with self.bot.async_session() as session:
            async with session.begin():
                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == member.id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    return await ctx.reply("User already has a custom role", delete_after=5)

                divider = ctx.guild.get_role(consts.CUSTOM_ROLE_DIVIDER_ID) or await ctx.guild.fetch_role(
                    consts.CUSTOM_ROLE_DIVIDER_ID
                )
                role = await ctx.guild.create_role(
                    name=name, reason=f"Creation custom role by {ctx.author.name} ({ctx.author.id})"
                )

                session.add(models.CustomRole(user_id=member.id, role_id=role.id))

                await role.edit(position=divider.position - 1)
                await member.add_roles(role)

        await ctx.reply(
            f"Created & assigned role {role.mention} for user {member.mention}",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.command("removerole", aliases=["rr"])
    @check.is_mod()
    async def remove_role(self, ctx: commands.Context, member: discord.Member, delete_role: bool = False, bypass_error: bool = False):
        """
        Remove custom role from user, optionally delete the role
        """
        if ctx.guild is None:
            return

        role_id = await self.retrieve_custom_role_id(member.id)
        if role_id is None:
            return await ctx.reply("User does not have a custom role", delete_after=5)

        role = ctx.guild.get_role(role_id) 
        if not bypass_error and role is None:
            role = await ctx.guild.fetch_role(role_id)
        async with self.bot.async_session() as session:
            async with session.begin():
                await session.execute(delete(models.CustomRole).where(models.CustomRole.user_id == member.id))
                if role:
                    await member.remove_roles(role) 

                if delete_role and role is not None:
                    await role.delete(reason=f"Deletion custom role by {ctx.author.name} ({ctx.author.id})")

        await ctx.reply(
            f"{'Deleted' if delete_role else 'Removed'} role @{role.name if role else 'Unknown Role'} from user {member.mention}",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @commands.command(name="assignrole", aliases=["ar"])
    @check.is_mod()
    async def assign_role(self, ctx: commands.Context, role: discord.Role, member: discord.Member):
        async with self.bot.async_session() as session:
            async with session.begin():
                cursor = await session.execute(select(models.CustomRole).where(models.CustomRole.user_id == member.id))
                cur_role = cursor.scalar_one_or_none()
                if cur_role is not None:
                    if cur_role.role_id != role.id:
                        confirm_embed = discord.Embed(
                            title="Confirm custom role change",
                            description=f"User {member.mention} already has a custom role <@&{cur_role.role_id}>\n"
                            f"Are you sure you want to change it to <@&{role.id}>?",
                        )
                        confirm = ConfirmEmbed(ctx.author.id, confirm_embed)
                        await confirm.send(ctx)
                        await confirm.wait()
                        if not confirm.value:
                            return
                        cur_role.role_id = role.id
                    else:
                        await ctx.reply(f"User **{member.name}** already has role **{role.name}**")
                        return
                else:
                    cur_role = models.CustomRole(user_id=member.id, role_id=role.id)

                session.add(cur_role)
                await member.add_roles(role)

        self._custom_role_cache[member.id] = role.id

        await ctx.reply(
            f"Set role {role.mention} to user {member.mention}",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )

        if self.refresh_cache.is_running():
            self.refresh_cache.restart()

    @commands.hybrid_command(name="name")
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

    @commands.hybrid_command(name="color", aliases=["colour"])
    async def set_role_colour(self, ctx: commands.Context, colour: discord.Colour, secondary_colour: Optional[str] = None):
        """
        Set role colour

        The following formats are accepted:

        - ``0x<hex>``
        - ``#<hex>``
        - ``0x#<hex>``
        - ``rgb(<number>, <number>, <number>)``

        Like CSS, ``<number>`` can be either 0-255 or 0-100% and ``<hex>`` can be
        either a 6 digit hex number or a 3 digit hex shortcut (e.g. #FFF).
        """
        if ctx.guild is None:
            return
        role_id = await self.retrieve_custom_role_id(ctx.author.id)
        if role_id is None:
            return await ctx.reply("You do not have a custom role", ephemeral=True)
        if secondary_colour is None:
            role = ctx.guild.get_role(role_id) or await ctx.guild.fetch_role(role_id)
            await role.edit(colour=colour)
            await ctx.reply(f"Set role colour to {role.colour}", mention_author=False)
        else:
            second_colour: discord.Colour = discord.Colour.from_str(secondary_colour)
            # TODO: Clean up after doc update: https://github.com/discord/discord-api-docs/pull/7549
            url = f"/guilds/{ctx.guild.id}/roles/{role_id}"
            await self.bot.http.request(discord.http.Route("PATCH", url), json={"colors": {"primary_color": colour.value, "secondary_color": second_colour.value}})
            await ctx.reply(f"Set role colour to {colour} - {second_colour}", mention_author=False)

    @set_role_colour.error
    async def set_role_colour_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.reply(f"Failed to set role colour: {error}", mention_author=False)

    @commands.hybrid_command(name="icon")
    async def set_role_icon(
        self,
        ctx: commands.Context,
        attachment: Optional[discord.Attachment] = None,
        emoji_or_unicode_or_reset: Optional[str] = None,
    ):
        """
        Set role icon. Either upload file or send emoji (file uploaded will be prioritized if both exists)

        Example Usage:
        /icon <emoji> or /icon <file> (or call icon with uploaded file if not using slash command)
        """
        if ctx.guild is None:
            return
        await ctx.defer()
        role_id = await self.retrieve_custom_role_id(ctx.author.id)
        if role_id is None:
            return await ctx.reply("You do not have a custom role", ephemeral=True)
        try:
            role = ctx.guild.get_role(role_id) or await ctx.guild.fetch_role(role_id)

            if attachment is not None:
                if attachment.content_type not in {"image/png", "image/jpg", "image/jpeg"}:
                    return await ctx.reply("Only PNG and JPEG images are supported", ephemeral=True)
                with BytesIO() as fp:
                    await attachment.save(fp)
                    await role.edit(display_icon=fp.getvalue())
            elif emoji_or_unicode_or_reset is not None:
                # Typing discord.Emoji is not supported. See: https://github.com/discord/discord-api-docs/discussions/3330
                # Using partial emoji require you to fetch full emoji before saving. See: https://github.com/Rapptz/discord.py/issues/8148
                partial_emoji = discord.PartialEmoji.from_str(emoji_or_unicode_or_reset)
                if partial_emoji.is_custom_emoji() and partial_emoji.id is not None:
                    async with self.bot.session.get(partial_emoji.url) as resp:
                        if resp.status != 200:
                            return await ctx.reply("Invalid emoji", ephemeral=True)
                        with BytesIO() as fp:
                            # Start stream in chunk
                            async for chunk in resp.content.iter_chunked(1024 * 1024):
                                fp.write(chunk)
                            fp.seek(0)
                            await role.edit(display_icon=fp.getvalue())
                elif emoji_or_unicode_or_reset.lower() == "reset":
                    await role.edit(display_icon=None)
                    await ctx.reply("Successfully reset role icon", mention_author=False)
                    return
                else:
                    await role.edit(display_icon=emoji_or_unicode_or_reset)
            else:
                # Invoke help command
                await ctx.send_help(ctx.command)
                return
        except (discord.errors.NotFound, discord.errors.HTTPException) as e:
            return await ctx.reply(f"Failed to set role icon: `{e}`", ephemeral=True)
        await ctx.reply("Successfully set role icon", mention_author=False)


async def setup(bot: LXVBot):
    await bot.add_cog(Role(bot))

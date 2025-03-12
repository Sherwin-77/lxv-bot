import asyncio
import logging
from os import getenv
from dotenv import load_dotenv

import discord
from discord.ext import commands
from sqlalchemy import delete, text

from bot import LXVBot
import check
import consts
import models

logger = logging.getLogger(__name__)

def main():
    load_dotenv()

    token = getenv("BOT_TOKEN")
    if token is None:
        raise ValueError("BOT_TOKEN is not set")

    discord.utils.setup_logging()

    bot = LXVBot()

    @bot.event
    async def on_ready():
        print(f"{bot.user.name if bot.user is not None else 'Bot'} is ready")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def sql(ctx: commands.Context, *, query):
        if bot.engine is None:
            return await ctx.reply("Psql disabled", mention_author=False)
        async with ctx.typing():
            async with bot.engine.begin() as conn:
                cursor = await conn.execute(text(query))
                value = cursor.scalars().all()
        await ctx.send(embed=discord.Embed(title="Result", description=value, color=discord.Colour.random()))

    @bot.command(hidden=True)
    @commands.is_owner()
    async def dm(ctx, user: discord.User, *, text="Test"):
        channel = await user.create_dm()
        await channel.send(text)
        await ctx.message.add_reaction('👍')

    @dm.error
    async def dm_error(ctx, error):
        await ctx.reply(f"Failed to dm: `{error}`\n" f"`{type(error)}`")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def switch(ctx: commands.Context, command: bot.get_command):  # type: ignore
        """
        Disable command-
        """
        if command == ctx.command:
            return await ctx.send("You can't disable this")
        if not command.enabled:
            command.enabled = True
            return await ctx.send("Switch to enabled")
        command.enabled = False
        return await ctx.send("Switch to disabled")

    @bot.command(hidden=True)
    @commands.is_owner()
    async def send(ctx, channel: discord.TextChannel, *, text="Test"):
        await channel.send(text)
        await ctx.message.add_reaction('👍')

    @send.error
    async def send_error(ctx, error):
        await ctx.reply(f"Failed to send: `{error}`\n" f"`{type(error)}`")

    @bot.command(name="setmod", aliases=["sm"])
    @check.is_mod()
    async def set_mod(ctx: commands.Context, role: discord.Role, remove: bool = False):
        if ctx.guild is None or ctx.guild.id != consts.GUILD_ID:
            return await ctx.reply("This command can only be used in the main server")

        if remove:
            async with bot.async_session() as session:
                async with session.begin():
                    await session.execute(delete(models.Mod).where(models.Mod.id == role.id))
            await ctx.reply(f"Removed role **{role.name}** from mods", mention_author=False)
        else:
            async with bot.async_session() as session:
                async with session.begin():
                    session.add(models.Mod(id=role.id))
            await ctx.reply(f"Set role **{role.name}** to mod", mention_author=False)

    @bot.event
    async def on_member_update(before: discord.Member, after: discord.Member):
        if after.guild.id != consts.GUILD_ID:
            return
        if before.premium_since is not None and after.premium_since is None and after.guild.id and consts.TRACK_CHANNEL_ID is not None:
            channel = bot.get_channel(consts.TRACK_CHANNEL_ID) or await bot.fetch_channel(consts.TRACK_CHANNEL_ID)
            await channel.send(f"**{after.name}** ({after.id}) lost their booster role")  # type: ignore

    @bot.event
    async def on_command_error(ctx: commands.Context, error):
        if isinstance(error, commands.errors.CommandNotFound) or hasattr(ctx.command, "on_error"):
            return
        if isinstance(error, commands.errors.DisabledCommand):
            return await ctx.reply(
                "This command is disabled or under maintenance <:speechlessOwO:793026526911135744>", mention_author=False
            )
        if isinstance(error, commands.errors.CheckFailure):
            return await ctx.reply("You are not allowed to use this command", mention_author=False)
        if isinstance(error, commands.errors.CommandOnCooldown):
            return await ctx.reply(
                f"{error} <a:Asheepupout:1345524571448807524>", mention_author=False, delete_after=error.retry_after
            )
        if (
            isinstance(error, commands.errors.NotOwner)
            or isinstance(error, discord.errors.Forbidden)
            or isinstance(error, commands.errors.BadArgument)
            or isinstance(error, commands.errors.MissingRequiredArgument)
        ):
            return await ctx.reply(str(error), mention_author=False)
        if isinstance(error, commands.errors.UserNotFound):
            return await ctx.reply("User not found", mention_author=False)
        
        logger.error("Uncaught error in command %s", ctx.command, exc_info=error)
        await bot.send_error_to_owner(error, ctx.channel, ctx.command)  # type: ignore
        if ctx.interaction is not None and ctx.interaction.response.is_done():
            return
        
        await ctx.reply("Something went wrong, please try again. If this keeps happening, contact staff", delete_after=5, ephemeral=True, mention_author=False)

    asyncio.run(bot.start(token))


if __name__ == "__main__":
    main()

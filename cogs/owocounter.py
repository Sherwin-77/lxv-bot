from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
import datetime
import logging
from typing import TYPE_CHECKING, Optional, Tuple
import zoneinfo

import discord
from discord.ext import commands, menus
from sqlalchemy import delete, func, literal_column, select, union_all, update

from enums.owo_command import OwOCommand
import models
import utils
from utils.cache import LRUCache
from utils.paginators import QueryEmbedSource, SimplePages
from utils.view_util import ConfirmEmbed

if TYPE_CHECKING:
    from bot import LXVBot


GLOBAL_LOCK_ID = -1

logger = logging.getLogger(__name__)


class OwoCounter(commands.GroupCog):
    def __init__(self, bot: LXVBot):
        self.bot = bot
        self.cooldown_config = self.bot.config.cooldown
        self.cooldowns: dict[str, Tuple[datetime.datetime, asyncio.Task]] = {}
        self.remind_cds: dict[int, asyncio.Task] = {}
        self.lock = set()
        self._cd = commands.CooldownMapping.from_cooldown(rate=1.0, per=3.0, type=commands.BucketType.user)

        self.owo_stat_ids = LRUCache()

    def cog_check(self, ctx: commands.Context):  # type: ignore
        if ctx.guild is None or ctx.guild.id != self.bot.config.guild_id:
            return False
        if ctx.invoked_with is not None and ctx.invoked_with == "help":
            return True
        bucket = self._cd.get_bucket(ctx.message)
        if bucket is None:
            return
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, commands.BucketType.user)
        return True

    # region Commands
    def get_command(
        self, content: str, interaction: Optional[discord.MessageInteraction] = None
    ) -> Optional[Tuple[OwOCommand, list[str]]]:
        # NOTE: Might be deprecated in future
        if interaction is not None:
            args = [interaction.name]
        else:
            content = content.lower()
            if content.startswith(self.bot.config.owo_prefix):
                args = list(filter(lambda s: s.strip(), content.removeprefix(self.bot.config.owo_prefix).split()))
            elif content.startswith("owo"):
                args = list(filter(lambda s: s.strip(), content.removeprefix("owo").split()))
            else:
                # Not a command, check if there is owo in message
                if "owo" in content or "uwu" in content:
                    return OwOCommand.POINT, []
                return None

        command = args[0] if args else "owo"
        args = args[1:] if len(args) > 1 else []
        if command in {"h", "hunt", "catch"}:
            return OwOCommand.HUNT, args
        elif command in {"b", "battle", "fight"}:
            return OwOCommand.BATTLE, args
        elif command == "pray":
            return OwOCommand.PRAY, args
        elif command == "curse":
            return OwOCommand.CURSE, args
        elif command == "owo":
            return OwOCommand.POINT, args
        else:
            return None

    @asynccontextmanager
    async def get_lock(self, locks: dict[int, asyncio.Lock], key_id: int):
        # Check global lock
        if GLOBAL_LOCK_ID in locks:
            logger.debug("Global lock exists, waiting")
            try:
                await locks[GLOBAL_LOCK_ID].acquire()
            finally:
                locks[GLOBAL_LOCK_ID].release()

        logger.debug("Acquiring lock for %s", key_id)
        try:
            if key_id not in locks:
                locks[key_id] = asyncio.Lock()
            async with locks[key_id]:
                yield
        finally:
            if key_id in locks and not locks[key_id].locked():
                del locks[key_id]

    async def remove_cd(self, key: str, start_time: datetime.datetime, cd: float):
        await discord.utils.sleep_until(start_time + datetime.timedelta(seconds=cd))
        if key in self.cooldowns and self.cooldowns[key][0] == start_time:  # Check if datetime is equal
            del self.cooldowns[key]

    # region Cooldown
    async def cooldown_check(self, command: OwOCommand, message: discord.Message) -> bool:
        key = f"cd_{command}_{message.author.id}"
        if key in self.lock:
            return False

        self.lock.add(key)
        try:
            now = discord.utils.snowflake_time(message.id)
            if command == OwOCommand.POINT:
                last = await self.bot.redis.get(key)
                if last is None:
                    last = datetime.datetime(2020, 1, 1, tzinfo=zoneinfo.ZoneInfo("UTC"))
                else:
                    last = datetime.datetime.fromisoformat(last)

                diff = (now - last).total_seconds()
                if diff < self.cooldown_config.owo:
                    # Future cooldown
                    if diff > -self.cooldown_config.max_owo_penalty:
                        new_time = last + datetime.timedelta(seconds=self.cooldown_config.owo_penalty)
                        await self.bot.redis.set(
                            key, new_time.isoformat(), exat=new_time + datetime.timedelta(seconds=self.cooldown_config.owo)
                        )
                    return False

                await self.bot.redis.set(
                    key, now.isoformat(), exat=now + datetime.timedelta(seconds=self.cooldown_config.owo)
                )
            else:
                match command:
                    case OwOCommand.HUNT:
                        cd = self.cooldown_config.hunt
                    case OwOCommand.BATTLE:
                        cd = self.cooldown_config.battle
                    case OwOCommand.PRAY:
                        cd = self.cooldown_config.pray_curse
                    case OwOCommand.CURSE:
                        cd = self.cooldown_config.pray_curse
                    case _:
                        raise ValueError(f"Unknown command {command}")

                if key in self.cooldowns and (now - self.cooldowns[key][0]).total_seconds() < cd:
                    return False

                self.cooldowns[key] = (now, self.bot.loop.create_task(self.remove_cd(key, now, cd)))
        except Exception as e:
            logger.error(f"Error while checking cooldown for {command}", exc_info=e)
            await self.bot.send_error_to_owner(e, message.channel, command.value)  # type: ignore
            return False
        finally:
            self.lock.remove(key)

        return True

    # region Counter
    async def process_stat(
        self, message: discord.Message, command: OwOCommand, args: list[str], *, as_member: Optional[discord.Member] = None
    ):
        now = discord.utils.snowflake_time(message.id)
        now_id = self.bot.get_day_id(now)
        key = f"{message.author.id}_{now_id}"
        member: discord.Member = as_member or message.author  # type: ignore
        logger.debug("Processing stat for %s", key)

        async with self.bot.lasync_session() as session:
            async with session.begin():
                stat_id = self.owo_stat_ids.get(key)
                if stat_id is None:
                    cursor = await session.execute(
                        select(models.OwOStat).where(models.OwOStat.user_id == member.id).where(models.OwOStat.day == now_id)
                    )
                    stat = cursor.scalar_one_or_none()
                    if stat is None:
                        stat = models.OwOStat(
                            day=now_id,
                            user_id=member.id,
                            owo_count=0,
                            hunt_count=0,
                            battle_count=0,
                            pray_count=0,
                            curse_count=0,
                        )
                        session.add(stat)
                        await session.flush()

                    stat_id = stat.id

                update_stmt = update(models.OwOStat).where(models.OwOStat.id == stat_id)
                match command:
                    case OwOCommand.POINT:
                        update_stmt = update_stmt.values(owo_count=models.OwOStat.owo_count + 1)
                    case OwOCommand.HUNT:
                        update_stmt = update_stmt.values(hunt_count=models.OwOStat.hunt_count + 1)
                    case OwOCommand.BATTLE:
                        update_stmt = update_stmt.values(battle_count=models.OwOStat.battle_count + 1)
                    case OwOCommand.PRAY:
                        update_stmt = update_stmt.values(pray_count=models.OwOStat.pray_count + 1)
                    case OwOCommand.CURSE:
                        update_stmt = update_stmt.values(curse_count=models.OwOStat.curse_count + 1)
                    case _:
                        raise ValueError(f"Unknown stat command {command}")
                await session.execute(update_stmt)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild is None or message.guild.id != self.bot.config.guild_id:
            return

        if message.author.id == self.bot.config.owo_id:
            if "You have been banned for" in message.content and "https://discord.com/invite/owobot" in message.content:
                log_channel: discord.TextChannel = message.guild.get_channel(self.bot.config.log_channel_id) or await message.guild.fetch_channel(self.bot.config.log_channel_id)  # type: ignore
                embed = discord.Embed(title="OwO Ban", description=message.content)
                embed.add_field(name="Jump", value=f"[Go to message]({message.jump_url})")
                await log_channel.send(embed=embed)
            if message._interaction is None:
                return

        if message.author.bot and (message._interaction is None or message.author.id != self.bot.config.owo_id):
            return

        # From user, check if we need to count stat
        cmd = self.get_command(message.content, message._interaction)
        if cmd is not None:
            command, args = cmd
            if message.author.bot and message._interaction is not None:
                message.author = message._interaction.user  # Inject author from interaction
            if not await self.cooldown_check(command, message):
                return

            await self.process_stat(message, command, args)

    @commands.command(name="oworeset")
    @commands.is_owner()
    async def reset_stat(self, ctx: commands.Context, member: discord.Member):
        """
        Reset OwO statistics for a member
        """
        ce = discord.Embed(
            title="OwO Reset",
            description=f"Are you sure you want to reset OwO statistics for {member.mention}?",
            colour=discord.Colour.red(),
        )
        ce.set_footer(text=str(member.id))
        confirm = ConfirmEmbed(ctx.author.id, ce)
        await confirm.send(ctx)
        await confirm.wait()
        if not confirm.value:
            return

        async with self.bot.lasync_session() as session:
            async with session.begin():
                await session.execute(delete(models.OwOStat).where(models.OwOStat.user_id == member.id))

                await ctx.reply(
                    embed=discord.Embed(
                        title="OwO Reset",
                        color=discord.Color.green(),
                        description=f"Successfully reset OwO statistics for {member.mention}",
                    )
                )

    @commands.hybrid_command(name="stat", aliases=["s"])
    async def stat(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """View OwO statistics for yourself or another member"""
        user: discord.Member = member or ctx.author  # type: ignore
        now = discord.utils.snowflake_time(ctx.message.id)
        now_id = self.bot.get_day_id(now)

        # Calculate day IDs for different periods
        yesterday_id = now_id - 1
        week_start_id = self.bot.get_day_id(now - datetime.timedelta(days=now.weekday() + 1))
        prev_week_end_id = week_start_id - 1
        prev_week_start_id = week_start_id - 7
        month_start_id = self.bot.get_day_id(now.replace(day=1))
        prev_month_end_id = month_start_id - 1
        prev_month_start_id = self.bot.get_day_id(utils.date.add_months(now.replace(day=1), -1))
        year_start_id = self.bot.get_day_id(now.replace(month=1, day=1))

        async with self.bot.lasync_session() as session:
            async with session.begin():
                # Query for today's stats (single record)
                today_query = select(models.OwOStat).where(models.OwOStat.user_id == user.id, models.OwOStat.day == now_id)
                today_result = await session.execute(today_query)
                today_stat = today_result.scalar_one_or_none()
                if today_stat is None:
                    today_stat = models.OwOStat(
                        day=now_id,
                        user_id=user.id,
                        owo_count=0,
                        hunt_count=0,
                        battle_count=0,
                        pray_count=0,
                        curse_count=0,
                    )

                # Query for yesterday's stats
                yesterday_query = select(models.OwOStat).where(
                    models.OwOStat.user_id == user.id, models.OwOStat.day == yesterday_id
                )
                yesterday_result = await session.execute(yesterday_query)
                yesterday_stat = yesterday_result.scalar_one_or_none()
                if yesterday_stat is None:
                    yesterday_stat = models.OwOStat(
                        day=yesterday_id,
                        user_id=user.id,
                        owo_count=0,
                        hunt_count=0,
                        battle_count=0,
                        pray_count=0,
                        curse_count=0,
                    )

                all_time_query = select(
                    func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                    func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                    func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                    func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                    func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                ).where(models.OwOStat.user_id == user.id)
                all_time = await session.execute(all_time_query)
                all_time_stat = all_time.one_or_none()
                if all_time_stat is None:
                    all_time_stat = models.OwOStat(
                        day=0,
                        user_id=user.id,
                        owo_count=0,
                        hunt_count=0,
                        battle_count=0,
                        pray_count=0,
                        curse_count=0,
                    )

                # -------------------------------- Aggregates -------------------------------- #
                period_queries = []

                # Current week aggregation
                week_query = (
                    select(
                        literal_column("'week'").label("period"),
                        func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                        func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                        func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                        func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                        func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                    )
                    .where(models.OwOStat.user_id == user.id, models.OwOStat.day.between(week_start_id, now_id))
                    .group_by("period")
                )
                period_queries.append(week_query)

                # Previous week aggregation
                prev_week_query = (
                    select(
                        literal_column("'prev_week'").label("period"),
                        func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                        func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                        func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                        func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                        func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                    )
                    .where(
                        models.OwOStat.user_id == user.id,
                        models.OwOStat.day.between(prev_week_start_id, prev_week_end_id),
                    )
                    .group_by("period")
                )
                period_queries.append(prev_week_query)

                # Add similar queries for month and year stats
                # Month query
                month_query = (
                    select(
                        literal_column("'month'").label("period"),
                        func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                        func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                        func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                        func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                        func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                    )
                    .where(models.OwOStat.user_id == user.id, models.OwOStat.day.between(month_start_id, now_id))
                    .group_by("period")
                )
                period_queries.append(month_query)

                # Previous month query
                prev_month_query = (
                    select(
                        literal_column("'prev_month'").label("period"),
                        func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                        func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                        func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                        func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                        func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                    )
                    .where(
                        models.OwOStat.user_id == user.id,
                        models.OwOStat.day.between(prev_month_start_id, prev_month_end_id),
                    )
                    .group_by("period")
                )
                period_queries.append(prev_month_query)

                # Year query
                year_query = (
                    select(
                        literal_column("'year'").label("period"),
                        func.coalesce(func.sum(models.OwOStat.owo_count), 0).label("owo_count"),
                        func.coalesce(func.sum(models.OwOStat.hunt_count), 0).label("hunt_count"),
                        func.coalesce(func.sum(models.OwOStat.battle_count), 0).label("battle_count"),
                        func.coalesce(func.sum(models.OwOStat.pray_count), 0).label("pray_count"),
                        func.coalesce(func.sum(models.OwOStat.curse_count), 0).label("curse_count"),
                    )
                    .where(models.OwOStat.user_id == user.id, models.OwOStat.day.between(year_start_id, now_id))
                    .group_by("period")
                )
                period_queries.append(year_query)

                # Use SQLAlchemy's union() to combine all queries
                combined_query = union_all(*period_queries)

                # Execute the combined query
                period_result = await session.execute(combined_query)
                period_stats = {row.period: row for row in period_result}

        embed = discord.Embed(title="OwO Statistics", colour=discord.Colour.random())
        all_time_text = (
            f"OwO: **{all_time_stat.owo_count}**\n"
            f"Hunt: **{all_time_stat.hunt_count}**\n"
            f"Battle: **{all_time_stat.battle_count}**\n"
            f"Pray: **{all_time_stat.pray_count}**\n"
            f"Curse: **{all_time_stat.curse_count}**"
        )
        embed.add_field(name="All Time", value=all_time_text, inline=True)

        today_text = (
            f"OwO: **{today_stat.owo_count}**\n"
            f"Hunt: **{today_stat.hunt_count}**\n"
            f"Battle: **{today_stat.battle_count}**\n"
            f"Pray: **{today_stat.pray_count}**\n"
            f"Curse: **{today_stat.curse_count}**"
        )
        embed.add_field(name="Today", value=today_text, inline=True)

        # Add yesterday's stats
        yesterday_text = (
            f"OwO: **{yesterday_stat.owo_count}**\n"
            f"Hunt: **{yesterday_stat.hunt_count}**\n"
            f"Battle: **{yesterday_stat.battle_count}**\n"
            f"Pray: **{yesterday_stat.pray_count}**\n"
            f"Curse: **{yesterday_stat.curse_count}**"
        )
        embed.add_field(name="Yesterday", value=yesterday_text, inline=True)

        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # Add period stats
        for period_name, period_data in period_stats.items():
            if period_data:
                period_text = (
                    f"OwO: **{period_data.owo_count}**\n"
                    f"Hunt: **{period_data.hunt_count}**\n"
                    f"Battle: **{period_data.battle_count}**\n"
                    f"Pray: **{period_data.pray_count}**\n"
                    f"Curse: **{period_data.curse_count}**"
                )
                embed.add_field(name=(' '.join(period_name.split('_')).title()), value=period_text, inline=True)

        embed.set_author(name=user.display_name, icon_url=user.display_avatar)
        await ctx.reply(embed=embed, mention_author=False)

    @commands.hybrid_command(name="top", aliases=["t", "lb"])
    async def top(self, ctx: commands.Context, period: Optional[str] = None):
        """View the OwO points leaderboard"""
        await self._show_top(ctx, OwOCommand.POINT, period)

    @commands.hybrid_command(name="tophunt", aliases=["htop", "ht", "hlb", "hunttop"])
    async def htop(self, ctx: commands.Context, period: Optional[str] = None):
        """View the Hunt leaderboard"""
        await self._show_top(ctx, OwOCommand.HUNT, period)

    @commands.hybrid_command(name="topbattle", aliases=["btop", "bt", "blb", "battletop"])
    async def btop(self, ctx: commands.Context, period: Optional[str] = None):
        """View the Battle leaderboard"""
        await self._show_top(ctx, OwOCommand.BATTLE, period)

    @commands.hybrid_command(name="toppray", aliases=["ptop", "pt", "plb", "praytop"])
    async def ptop(self, ctx: commands.Context, period: Optional[str] = None):
        """View the Pray leaderboard"""
        await self._show_top(ctx, OwOCommand.PRAY, period)

    @commands.hybrid_command(name="topcurse", aliases=["ctop", "ct", "clb", "cursetop"])
    async def ctop(self, ctx: commands.Context, period: Optional[str] = None):
        """View the Curse leaderboard"""
        await self._show_top(ctx, OwOCommand.CURSE, period)

    async def format_lb(self, stat_field: str, top_type: str):
        guild_id = self.bot.config.guild_id
        guild = self.bot.get_guild(guild_id) or await self.bot.fetch_guild(guild_id)

        def formatter(source: menus.ListPageSource, menu: menus.MenuPages, page):
            res = []
            for index, row in enumerate(page):
                member_id = row.user_id
                member = guild.get_member(member_id)
                if member is None:
                    output = f"<@{member_id}> - **{getattr(row, f'{stat_field}_count')}** {top_type}(s)"
                else:
                    output = f"{member.name} - **{getattr(row, f'{stat_field}_count')}** {top_type}(s) ||{member.mention}||"
                res.append(f"**{index + 1 + (menu.current_page * 10)}.** {output}")

            return "\n".join(res)

        return formatter

    async def _show_top(self, ctx: commands.Context, stat_type: OwOCommand, period: Optional[str] = None):
        q = select(models.OwOStat.user_id).group_by(models.OwOStat.user_id)

        top_type = None

        if stat_type == OwOCommand.POINT:
            field = models.OwOStat.owo_count
            top_type = "OwO"
            stat_field = "owo"
        elif stat_type == OwOCommand.HUNT:
            field = models.OwOStat.hunt_count
            top_type = "Hunt"
            stat_field = "hunt"
        elif stat_type == OwOCommand.BATTLE:
            field = models.OwOStat.battle_count
            top_type = "Battle"
            stat_field = "battle"
        elif stat_type == OwOCommand.PRAY:
            field = models.OwOStat.pray_count
            top_type = "Pray"
            stat_field = "pray"
        elif stat_type == OwOCommand.CURSE:
            field = models.OwOStat.curse_count
            top_type = "Curse"
            stat_field = "curse"
        else:
            field = models.OwOStat.owo_count
            top_type = "OwO"
            stat_field = "owo"

        q = q.add_columns(func.sum(field).label(f"{stat_field}_count"))

        now = discord.utils.snowflake_time(ctx.message.id)
        now_id = self.bot.get_day_id(now)

        top_period = None
        if period is None:
            period = "alltime"
        period = period.lower()

        if period in {"d", "day", "daily"}:
            q = q.where(models.OwOStat.day == now_id)
            top_period = "Daily"
        elif period in {"y", "yesterday"}:
            q = q.where(models.OwOStat.day == now_id - 1)
            top_period = "Yesterday"
        elif period in {"w", "week", "weekly"}:
            week_start_id = self.bot.get_day_id(now - datetime.timedelta(days=now.weekday() + 1))
            q = q.where(models.OwOStat.day.between(week_start_id, now_id))
            top_period = "Weekly"
        elif period in {"m", "month", "monthly"}:
            month_start_id = self.bot.get_day_id(now.replace(day=1))
            q = q.where(models.OwOStat.day.between(month_start_id, now_id))
            top_period = "Monthly"
        elif period in {"year", "yearly"}:
            year_start_id = self.bot.get_day_id(now.replace(month=1, day=1))
            q = q.where(models.OwOStat.day.between(year_start_id, now_id))
            top_period = "Yearly"
        elif period != "alltime":
            # Try to parse the period as a date
            segment = period.split("|")
            try:
                start_date = datetime.datetime.strptime(segment[0], "%d-%m-%Y").replace(
                    tzinfo=zoneinfo.ZoneInfo("US/Pacific")
                )
                if len(segment) > 1:
                    end_date = datetime.datetime.strptime(segment[1], "%d-%m-%Y").replace(
                        tzinfo=zoneinfo.ZoneInfo("US/Pacific")
                    )
                    top_period = f"{discord.utils.format_dt(start_date, 'D')} - {discord.utils.format_dt(end_date, 'D')}"
                else:
                    end_date = start_date
                    top_period = discord.utils.format_dt(start_date, 'D')

                start_id = self.bot.get_day_id(start_date)
                end_id = self.bot.get_day_id(end_date)

                q = q.where(models.OwOStat.day.between(start_id, end_id))
            except ValueError:
                await ctx.reply(
                    embed=discord.Embed(
                        title="Error",
                        description="Invalid period. Available periods: `d`, `w`, `m`, `y`, `alltime` or `start_date|end_date` (dd-mm-yyyy)",
                        color=discord.Color.red(),
                    )
                )
                return

        else:
            # No period specified, default to all time
            q = q.select_from(models.OwOStat)
            top_period = "All Time"

        async with self.bot.lasync_session() as session:
            total_q = await session.execute(q.with_only_columns(func.sum(field)).group_by(None))
            total = total_q.scalar_one_or_none() or 0

        embed = discord.Embed(title=f"Top {top_period} {top_type}", color=discord.Color.random())
        embed.add_field(name="Total", value=f"**{total}** {top_type}(s)")
        source = QueryEmbedSource(
            q,
            func.sum(field).desc(),
            self.bot.lasync_session,
            await self.format_lb(stat_field, top_type),
            embed,
        )
        page = SimplePages(source)
        await page.start(ctx)

    @commands.command(hidden=True)
    async def _ocd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        user: discord.Member = member or ctx.author  # type: ignore
        key = f"cd_{OwOCommand.POINT}_{user.id}"
        val = await self.bot.redis.get(key)
        if val is None:
            await ctx.send("Safe")
            return

        now = discord.utils.snowflake_time(ctx.message.id)
        last = datetime.datetime.fromisoformat(val)
        diff = (now - last).total_seconds()

        await ctx.send(f"{discord.utils.format_dt(last, 'R')} ({diff}s{' ⚠️' if diff < 0 else ''})")


async def setup(bot: LXVBot):
    await bot.add_cog(OwoCounter(bot))

from glob import glob
from io import BytesIO
import logging
from os import getenv
from os.path import relpath
from time import time_ns
from traceback import format_exception
from typing import Any, Optional, Union

import discord
from discord.ext import commands
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from utils import SimplePages, EmbedSource

DEV = "dev"
PRODUCTION = "production"


logger = logging.getLogger(__name__)

class NewHelpCommand(commands.MinimalHelpCommand):
    def __init__(self, **options):
        super().__init__(**options)
        self.no_category = "Other Command"

    # TODO: Add send_bot_help overriding

    async def send_pages(self):
        if len(self.paginator.pages) < 2:
            destination = self.get_destination()
            await destination.send(
                embed=discord.Embed(title="Help", description=self.paginator.pages[0], color=discord.Colour.random())
            )
        else:
            ctx = self.context
            menu = SimplePages(source=EmbedSource(self.paginator.pages, 1, "Help", lambda pg: pg))
            await menu.start(ctx)

class LXVBot(commands.Bot):
    owner: discord.User

    disabled_app_command = {}

    def __init__(self):
        allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)

        intents = discord.Intents.all()
        intents.presences = False

        super().__init__(
            case_insensitive=True,
            command_prefix=commands.when_mentioned_or("lxv"),  # type: ignore
            description="Your LXV Bot",
            intents=intents,
            allowed_mentions=allowed_mentions,
            status=discord.Status.idle,
            activity=discord.Game(name="lxvhelp"),
        )

        db_url = getenv("DB_URL", None)
        if db_url is None:
            raise ValueError("DB_URL is not set")

        self.bot_mode = getenv("ENV", PRODUCTION)
        self.help_command = NewHelpCommand()
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()
        self.launch_timestamp = time_ns() // 1000000000
        self.xp_cooldowns = set()
        self.engine = create_async_engine(db_url, echo=self.is_dev)

    @property
    def is_dev(self) -> bool:
        return self.bot_mode == DEV
    
    async def is_owner(self, user: discord.User):
        if user.id == 436376194166816770:
            return True
        
        return await super().is_owner(user)
    
    async def get_prefix(self, message: discord.Message, /):
        """|coro|

        Retrieves the prefix the bot is listening to
        with the message as a context.

        .. versionchanged:: 2.0

            ``message`` parameter is now positional-only.

        Parameters
        -----------
        message: :class:`discord.Message`
            The message context to get the prefix of.

        Returns
        --------
        Union[List[:class:`str`], :class:`str`]
            A list of prefixes or a single prefix that the bot is
            listening for.
        """
        if self.is_dev:
            return ["test!"]
        return await super().get_prefix(message)

    async def setup_hook(self) -> None:
        if self.is_dev:
            logger.warning("Bot is running in dev mode. Consider using production mode later")

        # Load cogs
        for file in glob(r"cogs/*.py"):
            module_name = relpath(file).replace("\\", '.').replace('/', '.')[:-3]
            await self.load_extension(module_name)
        await self.load_extension("jishaku")
        logger.info("Module loaded")

        self.owner = self.get_user(436376194166816770) or await self.fetch_user(436376194166816770)
        logger.info("Application info loaded")

    async def close(self) -> None:
        await self.engine.dispose()
        return await super().close()
    
    async def get_db_ping(self) -> Optional[int]:
        if self.engine is None:
            return None
        t0 = time_ns()
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        t1 = time_ns()
        return (t1 - t0) // 10000000
    
    async def send_owner(self, message=None, **kwargs) -> None:
        channel = await self.owner.create_dm()
        await channel.send(message, **kwargs)
    
    async def send_error_to_owner(
        self, error: Exception, channel: Union[discord.TextChannel, discord.Thread], command: Optional[Union[commands.Command[Any, ..., Any], str]]
    ) -> None:
        channel_name = getattr(channel, "name", "Unknown")
        output = ''.join(format_exception(type(error), error, error.__traceback__))
        if len(output) > 1500:
            buffer = BytesIO(output.encode("utf-8"))
            file = discord.File(buffer, filename="log.txt")
            await self.send_owner(
                f"Uncaught error in channel <#{channel.id}> #{channel_name} ({channel.id})\n command `{command}`",
                file=file,
            )
        else:
            custom_embed = discord.Embed(
                description=f"Uncaught error in channel <#{channel.id}> #{channel_name} ({channel.id})\n"
                f"command {command}\n"
                f"```py\n{output}\n```",
                color=discord.Colour.red(),
            )
            await self.send_owner(embed=custom_embed)

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        return await super().on_message(message)

    
def slash_is_enabled():
    def wrapper(interaction: discord.Interaction):
        if interaction.command is None:
            return False
        return interaction.command.qualified_name not in LXVBot.disabled_app_command

    return discord.app_commands.check(wrapper)

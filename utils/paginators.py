import discord
from discord.ext import menus, commands
from sqlalchemy import func, Select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from typing import Callable, Optional, TypeVar, Any

_T = TypeVar("_T", bound=Any)


class SimplePages(discord.ui.View, menus.MenuPages):
    """Pagination with ui button"""

    ctx: commands.Context
    message: discord.Message

    def __init__(self, source: menus.PageSource, *, delete_message_after=True):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = delete_message_after
        self.button = discord.ui.Button(disabled=True, label=str(self.current_page + 1))

    async def start(self, ctx, *, channel=None, wait=False):
        self.add_item(self.button)
        await self._source._prepare_once()
        self.ctx = ctx
        self.message = await self.send_initial_message(ctx, ctx.channel)

    async def _get_kwargs_from_page(self, page):
        value = await super()._get_kwargs_from_page(page)
        if value is None:
            return value
        if "view" not in value:
            value.update({"view": self})
        return value

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author

    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.blurple)
    async def skip_to_first(self, interaction, _):
        await self.show_page(0)
        self.button.label = '1'
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='◀', style=discord.ButtonStyle.blurple)
    async def back_page(self, interaction, _):
        await self.show_checked_page(self.current_page - 1)
        self.button.label = str(self.current_page + 1)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='⏹', style=discord.ButtonStyle.blurple)
    async def stop_page(self, interaction, _):
        for child in self.children:
            child.disabled = True  # type: ignore
        self.stop()
        if self.delete_message_after:
            await self.message.delete()
        else:
            await self.show_current_page()
            await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='▶', style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction, _):
        await self.show_checked_page(self.current_page + 1)
        self.button.label = str(self.current_page + 1)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.blurple)
    async def skip_to_last(self, interaction, _):
        await self.show_page(self._source.get_max_pages() - 1)  # type: ignore
        self.button.label = str(self.current_page + 1)
        await interaction.response.edit_message(view=self)


# https://github.com/Rapptz/discord-ext-menus#pagination
class EmbedSource(menus.ListPageSource):
    def __init__(
        self, entries, embed: Optional[discord.Embed] = None, format_caller: Optional[Callable] = None, *, per_page=10
    ):
        super().__init__(entries, per_page=per_page)
        if embed is None:
            embed = discord.Embed(color=discord.Colour.random())
        self.embed = embed
        self.format_caller = format_caller

    async def format_page(self, menu: menus.MenuPages, page):
        offset = menu.current_page * self.per_page  # type: ignore
        if self.format_caller is None:
            self.embed.description = '\n'.join(f"{i+1}. {v}" for i, v in enumerate(page, start=offset))
        else:
            self.embed.description = self.format_caller(self, menu, page)
        self.embed.set_footer(text=f"Page {menu.current_page+1}/{self.get_max_pages()}")
        return self.embed


class QueryEmbedSource(EmbedSource):
    def __init__(
        self,
        query: Select[_T],
        order_by,
        async_session: async_sessionmaker[AsyncSession],
        format_caller: Callable,
        embed: discord.Embed | None = None,
        *,
        per_page=10,
    ):
        super().__init__([], embed, format_caller, per_page=per_page)
        self.query = query.order_by(order_by)
        self.async_session = async_session

    async def prepare(self):
        async with self.async_session() as session:
            cursor = await session.execute(self.query.with_only_columns(func.count()))
            counts = cursor.scalar_one()
            self._max_pages = counts // self.per_page + (counts % self.per_page != 0)

    async def get_page(self, page_number):
        async with self.async_session() as session:
            cursor = await session.execute(self.query.limit(self.per_page).offset(page_number * self.per_page))
            return cursor.scalars().all()

    async def format_page(self, menu: menus.MenuPages, page):
        if self.format_caller is None:
            self.embed.description = '\n'.join(f"{i+1}. {v.id}" for i, v in enumerate(page))
        else:
            self.embed.description = self.format_caller(self, menu, page)
        self.embed.set_footer(text=f"Page {menu.current_page+1}/{self.get_max_pages()}")
        return self.embed

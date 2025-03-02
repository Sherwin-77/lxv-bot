import discord
from discord.ext import menus, commands

from typing import Callable


class SimplePages(discord.ui.View, menus.MenuPages):
    """Pagination with ui button"""
    ctx: commands.Context
    message: discord.Message
    def __init__(self, source: menus.PageSource, *, delete_message_after=True):
        super().__init__(timeout=60)
        self._source = source
        self.current_page = 0
        self.delete_message_after = delete_message_after
        self.button = discord.ui.Button(disabled=True, label=str(self.current_page))

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
        await self.show_checked_page(self.current_page-1)
        self.button.label = str(self.current_page+1)
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
        await self.show_checked_page(self.current_page+1)
        self.button.label = str(self.current_page+1)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.blurple)
    async def skip_to_last(self, interaction, _):
        await self.show_page(self._source.get_max_pages()-1)  # type: ignore
        self.button.label = str(self.current_page+1)
        await interaction.response.edit_message(view=self)


# https://github.com/Rapptz/discord-ext-menus#pagination
class EmbedSource(menus.ListPageSource):
    def __init__(self, entries, per_page=4, title="Title", format_caller: Callable = None):  # type: ignore
        super().__init__(entries, per_page=per_page)
        self.title = title
        self.format_caller = format_caller

    async def format_page(self, menu: menus.Menu, page):
        offset = menu.current_page * self.per_page  # type: ignore
        embed = discord.Embed(color=discord.Colour.random())
        embed.description = '\n'.join(f"{i+1}. {v}" for i, v in enumerate(page, start=offset))
        if self.title is not None:
            embed.title = self.title
        if self.format_caller is not None:
            embed.description = self.format_caller(page)
        return embed

class DataEmbedSource(EmbedSource):
    def format_page(self, menu: menus.Menu, page):
        offset = menu.current_page * self.per_page
        embed = discord.Embed(color=discord.Colour.random())
        if self.title is not None:
            embed.title = self.title
        if self.format_caller is not None:
            embed.description = '\n'.join(self.format_caller(i, v) for i, v in enumerate(page, start=offset))
        else:
            embed.description = '\n'.join(f"{i+1}. {v}" for i, v in enumerate(page, start=offset))
        return embed

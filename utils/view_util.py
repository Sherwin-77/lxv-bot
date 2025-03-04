import discord
from discord.ext import commands

from typing import List


class BaseView(discord.ui.View):
    """
    Base view for every implement
    """

    def __init__(self):
        super().__init__()
        self.value = None
        self.user = None

    async def on_timeout(self) -> None:
        for child in self.children:
            if child.view is None:
                continue
            child.view.stop()
        self.stop()


class NumberButton(discord.ui.Button):
    def __init__(self, number):
        super().__init__()
        self.number = number

    async def callback(self, interaction: discord.Interaction):
        assert self.view is not None


class ConfirmEmbed(BaseView):
    def __init__(
        self, userid: int, embed: discord.Embed = discord.Embed(title="Confirmation!", description="Are you sure?")
    ):
        super().__init__()
        self.userid = userid
        self.embed = embed

    @discord.ui.button(emoji='✅', style=discord.ButtonStyle.green)  # type: ignore
    async def confirm(self, interaction: discord.Interaction, _: discord.Button):
        if interaction.user.id != self.userid:
            return await interaction.response.send_message(content="You are not allowed to use this >:(", ephemeral=True)
        self.value = True
        await interaction.response.edit_message(content="Success", view=None, embed=None)
        self.stop()

    @discord.ui.button(emoji='❎', style=discord.ButtonStyle.red)  # type: ignore
    async def cancel(self, interaction: discord.Interaction, _: discord.Button):
        if interaction.user.id != self.userid:
            return await interaction.response.send_message(content="You are not allowed to use this >:(", ephemeral=True)
        self.value = False
        await interaction.response.edit_message(content="Operation cancelled", view=None, embed=None)
        self.stop()

    async def send(self, ctx: commands.Context):
        await ctx.send(view=self, embed=self.embed)


class Dropdown(discord.ui.Select):
    def __init__(self, text: str, select_list: List[discord.SelectOption]):
        super().__init__(placeholder=text, min_values=1, max_values=1, options=select_list)

    async def callback(self, interaction: discord.Interaction):
        raise NotImplementedError

from discord.ext import commands

def is_mod():
    def predicate(ctx: commands.Context):
        return ctx.bot.mod_only(ctx)
    return commands.check(predicate)
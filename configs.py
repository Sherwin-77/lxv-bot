from __future__ import annotations

from dataclasses import dataclass

from dataclass_wizard import JSONPyWizard


@dataclass
class Cooldown:
    owo: float
    owo_penalty: float
    max_owo_penalty: float
    hunt: float
    battle: float
    pray_curse: float


@dataclass
class Config(JSONPyWizard):
    class _(JSONPyWizard.Meta):
        v1 = True

    owo_prefix: str
    owo_id: int
    guild_id: int
    cooldown: Cooldown

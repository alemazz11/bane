"""Mutator Strategies"""

from enum import Enum


class MutationType(Enum):
    REPHRASE       = "rephrase"
    OBFUSCATE      = "obfuscate"
    ESCALATE       = "escalate"
    SOFTEN         = "soften"
    REFRAME        = "reframe"
    FRAGMENT       = "fragment"
    WRAP           = "wrap"
    LANGUAGE_SWITCH = "lang_switch"
    CROSSOVER      = "crossover"
    ANTI_DEFENSE   = "anti_defense"
    CHAIN          = "chain"
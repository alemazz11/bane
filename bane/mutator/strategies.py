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

    CONTEXT_MANIPULATION = "context_manipulation"
    DIRECT_INJECTION     = "direct_injection"
    ENCODING_ATTACKS     = "encoding_attacks"
    EXTRACTION_ATTACKS   = "extraction_attacks"
    FEW_SHOT_PRIMING     = "few_shot_priming"
    INDIRECT_INJECTION   = "indirect_injection"
    LINGUISTIC_CONFUSION = "linguistic_confusion"
    LOGIC_TRAPS          = "logic_traps"
    MULTI_TURN           = "multi_turn"
    OUTPUT_CONSTRAINTS   = "output_constraints"
    PAYLOAD_SPLITTING    = "payload_splitting"
    ROLE_HIJACKING       = "role_hijacking"
    TASK_HIJACKING       = "task_hijacking"
    DELIMITER_ATTACKS    = "delimiter_attacks"
    JAILBREAK_VARIANTS   = "jailbreak_variants"
    CONTEXT_PADDING      = "context_padding"
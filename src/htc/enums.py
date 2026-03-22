from enum import Enum, auto


class Phase(Enum):
    START = "start"
    ACTION = "action"
    END = "end"


class CombatStep(Enum):
    LAYER = "layer"
    ATTACK = "attack"
    DEFEND = "defend"
    REACTION = "reaction"
    DAMAGE = "damage"
    RESOLUTION = "resolution"
    CLOSE = "close"


class Zone(Enum):
    HAND = "hand"
    DECK = "deck"
    ARSENAL = "arsenal"
    PITCH = "pitch"
    GRAVEYARD = "graveyard"
    BANISHED = "banished"
    SOUL = "soul"
    HERO = "hero"
    HEAD = "head"
    CHEST = "chest"
    ARMS = "arms"
    LEGS = "legs"
    WEAPON_1 = "weapon_1"
    WEAPON_2 = "weapon_2"
    STACK = "stack"
    COMBAT_CHAIN = "combat_chain"
    PERMANENT = "permanent"
    REMOVED = "removed"


class Color(Enum):
    RED = "Red"
    YELLOW = "Yellow"
    BLUE = "Blue"


# --- Card classification enums ---
# These map directly to the FaB Cube "Types" field, separated into
# the three categories from the comprehensive rules.

class CardType(Enum):
    """Primary card types (rules 2.15)."""
    ACTION = "Action"
    ATTACK_REACTION = "Attack Reaction"
    BLOCK = "Block"
    COMPANION = "Companion"
    DEFENSE_REACTION = "Defense Reaction"
    DEMI_HERO = "Demi-Hero"
    EQUIPMENT = "Equipment"
    HERO = "Hero"
    INSTANT = "Instant"
    MACRO = "Macro"
    MENTOR = "Mentor"
    RESOURCE = "Resource"
    TOKEN = "Token"
    WEAPON = "Weapon"
    EVENT = "Event"


class SubType(Enum):
    """Subtypes — functional and non-functional (rules 2.10)."""
    # Functional
    ONE_HAND = "1H"
    TWO_HAND = "2H"
    AFFLICTION = "Affliction"
    ALLY = "Ally"
    ARROW = "Arrow"
    ASH = "Ash"
    ATTACK = "Attack"
    AURA = "Aura"
    CONSTRUCT = "Construct"
    FIGMENT = "Figment"
    INVOCATION = "Invocation"
    ITEM = "Item"
    LANDMARK = "Landmark"
    OFF_HAND = "Off-Hand"
    QUIVER = "Quiver"
    # Non-functional (weapon/equipment subtypes and creature types)
    ANGEL = "Angel"
    ARMS = "Arms"
    AXE = "Axe"
    BASE = "Base"
    BOOK = "Book"
    BOW = "Bow"
    BRUSH = "Brush"
    CANNON = "Cannon"
    CHEST = "Chest"
    CHI = "Chi"
    CLAW = "Claw"
    CLUB = "Club"
    COG = "Cog"
    DAGGER = "Dagger"
    DEMON = "Demon"
    DRAGON = "Dragon"
    EVO = "Evo"
    FIDDLE = "Fiddle"
    FLAIL = "Flail"
    GEM = "Gem"
    GUN = "Gun"
    HAMMER = "Hammer"
    HEAD = "Head"
    LEGS = "Legs"
    LUTE = "Lute"
    MERCENARY = "Mercenary"
    ORB = "Orb"
    PISTOL = "Pistol"
    PIT_FIGHTER = "Pit-Fighter"
    POLEARM = "Polearm"
    ROCK = "Rock"
    SCEPTER = "Scepter"
    SCROLL = "Scroll"
    SCYTHE = "Scythe"
    SHURIKEN = "Shuriken"
    SONG = "Song"
    STAFF = "Staff"
    SWORD = "Sword"
    TRAP = "Trap"
    WRENCH = "Wrench"
    YOUNG = "Young"


class SuperType(Enum):
    """Supertypes — class and talent (rules 2.11)."""
    # Classes
    ADJUDICATOR = "Adjudicator"
    ASSASSIN = "Assassin"
    BARD = "Bard"
    BRUTE = "Brute"
    GUARDIAN = "Guardian"
    ILLUSIONIST = "Illusionist"
    MECHANOLOGIST = "Mechanologist"
    MERCHANT = "Merchant"
    NECROMANCER = "Necromancer"
    NINJA = "Ninja"
    PIRATE = "Pirate"
    RANGER = "Ranger"
    RUNEBLADE = "Runeblade"
    SHAPESHIFTER = "Shapeshifter"
    THIEF = "Thief"
    WARRIOR = "Warrior"
    WIZARD = "Wizard"
    # Talents
    CHAOS = "Chaos"
    DRACONIC = "Draconic"
    EARTH = "Earth"
    ELEMENTAL = "Elemental"
    ICE = "Ice"
    LIGHT = "Light"
    LIGHTNING = "Lightning"
    MYSTIC = "Mystic"
    REVERED = "Revered"
    REVILED = "Reviled"
    ROYAL = "Royal"
    SHADOW = "Shadow"
    # Generic (no supertypes)
    GENERIC = "Generic"


class Keyword(Enum):
    """Ability keywords (rules 8.3+)."""
    AMBUSH = "Ambush"
    AMP = "Amp"
    ARCANE_BARRIER = "Arcane Barrier"
    ARCANE_SHELTER = "Arcane Shelter"
    ATTACK = "Attack"
    AWAKEN = "Awaken"
    BATTLEWORN = "Battleworn"
    BEAT_CHEST = "Beat Chest"
    BLADE_BREAK = "Blade Break"
    BLOOD_DEBT = "Blood Debt"
    BOOST = "Boost"
    CHANNEL = "Channel"
    CHARGE = "Charge"
    CLASH = "Clash"
    CLOAKED = "Cloaked"
    COMBO = "Combo"
    CONTRACT = "Contract"
    CRANK = "Crank"
    CRUSH = "Crush"
    DECOMPOSE = "Decompose"
    DOMINATE = "Dominate"
    EPHEMERAL = "Ephemeral"
    ESSENCE = "Essence"
    EVO_UPGRADE = "Evo Upgrade"
    FREEZE = "Freeze"
    FUSION = "Fusion"
    GALVANIZE = "Galvanize"
    GO_AGAIN = "Go again"
    GO_FISH = "Go Fish"
    GUARDWELL = "Guardwell"
    HEAVE = "Heave"
    HEAVY = "Heavy"
    INTIMIDATE = "Intimidate"
    LEGENDARY = "Legendary"
    MARK = "Mark"
    MATERIAL = "Material"
    MELD = "Meld"
    MIRAGE = "Mirage"
    MODULAR = "Modular"
    NEGATE = "Negate"
    OPT = "Opt"
    OVERPOWER = "Overpower"
    PAIRS = "Pairs"
    PERCHED = "Perched"
    PHANTASM = "Phantasm"
    PIERCING = "Piercing"
    PROTECT = "Protect"
    QUELL = "Quell"
    RELOAD = "Reload"
    REPRISE = "Reprise"
    RETRIEVE = "Retrieve"
    RUNE_GATE = "Rune Gate"
    RUPTURE = "Rupture"
    SCRAP = "Scrap"
    SOLFLARE = "Solflare"
    SPECIALIZATION = "Specialization"
    SPECTRA = "Spectra"
    SPELLVOID = "Spellvoid"
    STEAL = "Steal"
    STEALTH = "Stealth"
    SURGE = "Surge"
    SUSPENSE = "Suspense"
    TEMPER = "Temper"
    THE_CROWD_BOOS = "The Crowd Boos"
    THE_CROWD_CHEERS = "The Crowd Cheers"
    TOWER = "Tower"
    TRANSCEND = "Transcend"
    TRANSFORM = "Transform"
    UNFREEZE = "Unfreeze"
    UNITY = "Unity"
    UNIVERSAL = "Universal"
    UNLIMITED = "Unlimited"
    WAGER = "Wager"
    WARD = "Ward"
    WATERY_GRAVE = "Watery Grave"


class EquipmentSlot(Enum):
    HEAD = "head"
    CHEST = "chest"
    ARMS = "arms"
    LEGS = "legs"


class LayerKind(Enum):
    CARD = "card"
    ACTIVATED = "activated"
    TRIGGERED = "triggered"


class DecisionType(Enum):
    PLAY_OR_PASS = "play_or_pass"
    CHOOSE_ATTACK_TARGET = "attack_target"
    CHOOSE_DEFENDERS = "defenders"
    CHOOSE_CARDS_TO_PITCH = "pitch"
    CHOOSE_ARSENAL_CARD = "arsenal"
    PLAY_REACTION_OR_PASS = "reaction"
    CHOOSE_TARGET = "choose_target"
    CHOOSE_MODE = "choose_mode"
    ORDER_TRIGGERED = "order_triggers"
    OPTIONAL_ABILITY = "optional_ability"
    ORDER_PITCH_TO_DECK = "pitch_order"


class ActionType(Enum):
    PLAY_CARD = "play_card"
    ACTIVATE_ABILITY = "activate_ability"
    DEFEND_WITH = "defend_with"
    PASS = "pass"
    ARSENAL = "arsenal"


# Lookup tables for parsing the CSV "Types" field into the right enum category.
_CARD_TYPE_VALUES = {e.value for e in CardType}
_SUB_TYPE_VALUES = {e.value for e in SubType}
_SUPER_TYPE_VALUES = {e.value for e in SuperType}


def classify_type_string(type_str: str) -> tuple[
    set[CardType], set[SubType], set[SuperType]
]:
    """Parse a comma-separated types string from FaB Cube into the three categories."""
    card_types: set[CardType] = set()
    sub_types: set[SubType] = set()
    super_types: set[SuperType] = set()
    for raw in type_str.split(","):
        t = raw.strip()
        if not t:
            continue
        if t in _CARD_TYPE_VALUES:
            card_types.add(CardType(t))
        elif t in _SUB_TYPE_VALUES:
            sub_types.add(SubType(t))
        elif t in _SUPER_TYPE_VALUES:
            super_types.add(SuperType(t))
        # else: skip unknown types (e.g. "Placeholder Card", "Puffin", "Scurv")
    return card_types, sub_types, super_types

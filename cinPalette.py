# cinPalette.py
# import * from here just to ensure values are consistent
from dataclasses import dataclass
# todo: import these values from a configuration file, though ig this kind of is the configuration file

esc = "\033"
clearFormatting = f"{esc}[0m"
clrEsc = f"{clearFormatting}{esc}"

defaultColor = f"{esc}[37m" #[38:5:182m" # white
labelColor = f"{esc}[36m" #[38:5:170m" # cyan
errorColor = f"{clrEsc}[91m" # red
miscColor = f"{clrEsc}[37m" # gray
highlightedColor = f"{esc}[36m" #[38:5:39m" # cyan
debugColor = f"{clrEsc}[92m" # green
fiveLines = "\n\n\n\n\n"
indent = "  "




@dataclass(slots=True, frozen=True)
class BoxParams:
    box_color: str = highlightedColor
    box_indentation: int = 1
    indentation: int = 1
    width: int = 40
    text_color: str = defaultColor
    alt_first_border: bool = False

# ─────────────────────────────────────────────────────────────
# Core window layouts
# ─────────────────────────────────────────────────────────────

LARGE_WINDOW_BORDER = BoxParams(
    box_color=highlightedColor,
    box_indentation=4,
    indentation=2,
    width=124
)

LARGE_WINDOW = BoxParams(
    box_color=highlightedColor,
    box_indentation=4,
    indentation=2,
    width=120
)

LARGE_WINDOW_HEADER = BoxParams(
    box_color=highlightedColor,
    box_indentation=4,
    indentation=1,
    width=121,
    alt_first_border=True
)

# ─────────────────────────────────────────────────────────────
# Status & counters
# ─────────────────────────────────────────────────────────────

LOAD_STATUS = BoxParams(
    box_color=highlightedColor,
    box_indentation=4,
    indentation=1,
    width=120
)

# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────

ERROR_BOX = BoxParams(
    box_color=highlightedColor,
    box_indentation=4,
    indentation=3,
    width=120,
    text_color=errorColor
)

# ─────────────────────────────────────────────────────────────
# Headers
# ─────────────────────────────────────────────────────────────

HEADER_BOX = BoxParams(
    box_color=debugColor,
    box_indentation=27,
    indentation=0,
    width=30
)

HEADER_BOX_BORDER = BoxParams(
    box_color=debugColor,
    box_indentation=27,
    indentation=0,
    width=34
)
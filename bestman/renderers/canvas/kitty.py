"""Kitty graphics protocol helper.

Supporting terminals: Ghostty, Kitty, iTerm2, WezTerm.
"""

import base64
import os
import sys


def kitty_available() -> bool:
    """Check whether the current terminal supports Kitty graphics protocol.

    Detects Ghostty, Kitty, iTerm2, WezTerm via environment variables.
    """
    term_program = os.environ.get("TERM_PROGRAM", "")
    if term_program in ("ghostty", "Kitty", "iTerm.app", "WezTerm"):
        return True
    if "KITTY_WINDOW_ID" in os.environ:
        return True
    if os.environ.get("TERM", "") == "xterm-kitty":
        return True
    return False


def kitty_display(png_bytes: bytes, cols: int = 90, rows: int = 24):
    """Display a PNG in the terminal via the Kitty graphics protocol.

    Args:
        png_bytes: Raw PNG image data.
        cols: Terminal columns the image should occupy.
        rows: Terminal rows the image should occupy.
    """
    b64 = base64.b64encode(png_bytes).decode()
    chunk_size = 4096
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    ctrl = f"\033_Ga=T,f=100,c={cols},r={rows}"
    if len(chunks) == 1:
        sys.stdout.write(f"{ctrl};{chunks[0]}\033\\")
    else:
        sys.stdout.write(f"{ctrl},m=1;{chunks[0]}\033\\")
        for c in chunks[1:-1]:
            sys.stdout.write(f"\033_Gm=1;{c}\033\\")
        sys.stdout.write(f"\033_Gm=0;{chunks[-1]}\033\\")
    sys.stdout.flush()

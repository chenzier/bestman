"""Pure Python PNG byte generation.

No external dependencies — builds a PNG from a pixel callback
``(x, y) -> (R, G, B, A)`` using raw `zlib` + `struct`.
"""

import struct
import zlib


def make_png(width: int, height: int, pixel_fn) -> bytes:
    """Generate a raw PNG from a pixel callback.

    Args:
        width: Image width in pixels.
        height: Image height in pixels.
        pixel_fn: Callable ``(x, y) → (R, G, B, A)``.

    Returns:
        PNG file as bytes.
    """
    pixels = bytearray()
    for y in range(height):
        pixels.append(0)  # filter none
        for x in range(width):
            r, g, b, a = pixel_fn(x, y)
            pixels.append(r)
            pixels.append(g)
            pixels.append(b)
            pixels.append(a)

    raw = bytes(pixels)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)

    def _chunk(ctype, data):
        c = ctype + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return sig + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b"")

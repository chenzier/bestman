"""ASCII / Rich markup renderer — pure terminal text output.

Consumes the render data dict from ``MapEngine.build_render_data()``
and produces a Rich-markup string.  This is the portable fallback
renderer that works in every terminal.
"""

from bestman.renderers.base import BaseRenderer


class AsciiRenderer(BaseRenderer):
    """Render the voyage map as Rich markup text."""

    def is_available(self) -> bool:
        """Always available — no external dependencies needed."""
        return True

    def render_map(self, data: dict, theme, vessel_def=None) -> str:
        """Render the map grid as a Rich markup string.

        Args:
            data: dict from ``MapEngine.build_render_data()`` with
                  ``grid``, ``sway_offset``, ``today_advance``, etc.
            theme: Theme instance (unused in ASCII; kept for interface).
            vessel_def: VesselDef or None (unused in ASCII).

        Returns:
            str: Rich markup string with styled grid cells, one line per row.
        """
        grid = data["grid"]
        lines = []
        for row in grid:
            parts = []
            for cell in row:
                status = cell["status"]
                char = cell["terrain_char"]
                color = cell.get("terrain_color", "blue")

                if cell["has_finish"]:
                    style = "bold green"
                elif cell["has_ship"]:
                    style = "bold yellow"
                elif cell["has_milestone"] and status in ("preview", "explored"):
                    style = "bold magenta"
                elif status == "fog":
                    style = "dim blue"
                elif cell.get("is_today_trail"):
                    fade = cell.get("trail_fade", 0)
                    today_color = cell.get("today_color", "bright_red")
                    if fade == 0:
                        style = f"bold {today_color}"
                    elif fade == 1:
                        style = f"bold {color}"
                    else:
                        style = color
                elif status == "wake":
                    style = f"bold {color}"
                elif status == "preview":
                    style = "blue"
                else:  # explored (distant)
                    style = f"dim {color}"

                parts.append(f"[{style}]{char}[/]")
            lines.append("".join(parts))

        return "\n".join(lines)

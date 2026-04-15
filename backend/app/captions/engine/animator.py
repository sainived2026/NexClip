"""
NexRenderer Engine — Animator Module
Calculates per-frame interpolations for pop scales, fades, and color shifts.
"""

from typing import Tuple, List
import math

def ease_out_back(t: float) -> float:
    """Overshoot easing for popping effects."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * math.pow(t - 1, 3) + c1 * math.pow(t - 1, 2)

def ease_out_quint(t: float) -> float:
    return 1 - math.pow(1 - t, 5)

def parse_color(c: str) -> Tuple[int, int, int, int]:
    """Parse rgba(r,g,b,a) or #RRGGBBAA or #RRGGBB to RGBA tuple."""
    if c.startswith("rgba"):
        c = c.replace("rgba(", "").replace(")", "").replace(" ", "")
        r, g, b, a = c.split(",")
        return int(r), int(g), int(b), int(float(a) * 255)
    elif c.startswith("#"):
        c = c.lstrip("#")
        if len(c) == 6:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
        elif len(c) == 8:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))
    return (0, 0, 0, 0)

def interpolate_color(c1: Tuple[int,int,int,int], c2: Tuple[int,int,int,int], factor: float) -> Tuple[int,int,int,int]:
    """Linearly interpolate between two RGBA colors."""
    factor = max(0.0, min(1.0, factor))
    return (
        int(c1[0] + (c2[0] - c1[0]) * factor),
        int(c1[1] + (c2[1] - c1[1]) * factor),
        int(c1[2] + (c2[2] - c1[2]) * factor),
        int(c1[3] + (c2[3] - c1[3]) * factor),
    )

class Animator:
    @staticmethod
    def get_state(current_ms: int, start_ms: int, end_ms: int, animation_type: str, base_scale: float, active_scale: float) -> dict:
        """Calculate the visual state of a word at a specific millisecond timestamp."""
        duration = end_ms - start_ms
        if duration <= 0:
            return {"scale": base_scale, "alpha": 255, "rotate": 0.0, "progress": 0.0}

        # Progress within the word's active window (0.0 to 1.0)
        progress = (current_ms - start_ms) / duration
        progress = max(0.0, min(1.0, progress))

        # How far into the word are we in milliseconds?
        local_ms = current_ms - start_ms

        scale = base_scale
        alpha = 255
        rotate = 0.0

        if local_ms < 0:
            # Not yet active
            return {"scale": base_scale, "alpha": 200, "rotate": 0.0, "progress": 0.0}

        if animation_type == "pop":
            # Pop scales up quickly using overshoot, then settles
            pop_duration = min(duration * 0.4, 200.0) # max 200ms pop
            if local_ms < pop_duration:
                t = local_ms / pop_duration
                scale = base_scale + (active_scale - base_scale) * ease_out_back(t)
            else:
                scale = active_scale
                
        elif animation_type == "red-burst":
            pop_duration = 150.0
            if local_ms < pop_duration:
                t = local_ms / pop_duration
                scale = base_scale + (active_scale - base_scale) * ease_out_back(t)
                rotate = -2.0 * ease_out_back(t)
            else:
                scale = active_scale
                rotate = -2.0

        elif animation_type == "fade-swap":
            fade_duration = 150.0
            if local_ms < fade_duration:
                t = local_ms / fade_duration
                scale = base_scale + (active_scale - base_scale) * ease_out_quint(t)
            else:
                scale = active_scale
                
        else:
            # basic snap
            scale = active_scale

        return {
            "scale": scale,
            "alpha": alpha,
            "rotate": rotate,
            "progress": progress
        }

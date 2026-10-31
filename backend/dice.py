import secrets

FACES = (4, 6, 8, 10, 12, 20, 100)


MODES = ("normal", "adv", "dis")


def roll(count: int = 1, faces: int = 20, modifier: int = 0, mode: str = "normal") -> dict:
    if faces not in FACES:
        raise ValueError(f"unsupported die d{faces}; supported: {FACES}")
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    if not -100 <= modifier <= 100:
        raise ValueError("modifier out of range")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    # Advantage/disadvantage (D&D 5e): roll twice on a d20, keep highest/lowest.
    if mode != "normal" and count == 1 and faces == 20:
        pair = [secrets.randbelow(faces) + 1, secrets.randbelow(faces) + 1]
        kept = max(pair) if mode == "adv" else min(pair)
        return {
            "dice": f"d{faces} ({'advantage' if mode == 'adv' else 'disadvantage'}){modifier:+d}"
            if modifier
            else f"d{faces} ({'advantage' if mode == 'adv' else 'disadvantage'})",
            "rolls": pair,
            "kept": kept,
            "mode": mode,
            "modifier": modifier,
            "total": kept + modifier,
        }
    rolls = [secrets.randbelow(faces) + 1 for _ in range(count)]
    total = sum(rolls) + modifier
    return {
        "dice": f"{count}d{faces}{modifier:+d}" if modifier else f"{count}d{faces}",
        "rolls": rolls,
        "mode": "normal",
        "modifier": modifier,
        "total": total,
    }


def ability_scores() -> list[int]:
    return [sum(sorted(secrets.randbelow(6) + 1 for _ in range(4))[1:]) for _ in range(6)]

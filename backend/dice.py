import secrets

FACES = (4, 6, 8, 10, 12, 20, 100)


def roll(count: int = 1, faces: int = 20, modifier: int = 0) -> dict:
    if faces not in FACES:
        raise ValueError(f"unsupported die d{faces}; supported: {FACES}")
    if not 1 <= count <= 100:
        raise ValueError("count must be between 1 and 100")
    if not -100 <= modifier <= 100:
        raise ValueError("modifier out of range")
    rolls = [secrets.randbelow(faces) + 1 for _ in range(count)]
    total = sum(rolls) + modifier
    return {
        "dice": f"{count}d{faces}{modifier:+d}" if modifier else f"{count}d{faces}",
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
    }


def ability_scores() -> list[int]:
    return [sum(sorted(secrets.randbelow(6) + 1 for _ in range(4))[1:]) for _ in range(6)]

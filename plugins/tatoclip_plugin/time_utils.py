
def timestamp_to_sec(timestamp):
    parts = list(map(int, timestamp.split(':')))
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        raise ValueError("Invalid timestamp format")
    return h * 3600 + m * 60 + s

def format_seconds(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}")
        parts.append(f"{minutes:02d}")
    else:
        if minutes > 0:
            parts.append(f"{minutes}")
    parts.append(f"{seconds:02d}")

    return ":".join(parts)
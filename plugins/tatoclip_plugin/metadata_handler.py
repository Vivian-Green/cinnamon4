from plugins.tatoclip_plugin import ensure_clip_file_and_load


def get_effective_index(data, raw_index):
    """Convert raw index to effective index considering offsets"""
    if not data or not isinstance(data, list) or len(data) == 0:
        return raw_index

    metadata = data[0]
    offsets = metadata.get("offsets", {})

    # Convert offsets to sorted list of (effective_threshold, shift)
    offset_points = []
    for k, v in offsets.items():
        try:
            offset_points.append((int(k), int(v)))
        except (ValueError, TypeError):
            continue

    # Sort by effective threshold
    offset_points.sort(key=lambda x: x[0])

    # Calculate how many videos are skipped before this raw index
    total_skipped = 0
    for effective_threshold, shift in offset_points:
        # The raw index where this offset starts applying
        raw_threshold = effective_threshold + total_skipped
        if raw_index >= raw_threshold:
            total_skipped += shift
        else:
            break

    return raw_index - total_skipped


def get_raw_index(data, effective_index):
    """Convert effective index to raw index considering offsets"""
    if not data or not isinstance(data, list) or len(data) == 0:
        return effective_index

    metadata = data[0]
    offsets = metadata.get("offsets", {})

    # Handle negative effective indices (skipped videos)
    if effective_index < 0:
        # Build list of all skipped raw indices
        skipped_indices = []
        current_raw = 1
        current_effective = 1

        # Convert offsets to sorted list and process
        offset_points = []
        for k, v in offsets.items():
            try:
                offset_points.append((int(k), int(v)))
            except (ValueError, TypeError):
                continue
        offset_points.sort(key=lambda x: x[0])

        for effective_threshold, shift in offset_points:
            # Add all videos up to this threshold
            while current_effective < effective_threshold:
                current_raw += 1
                current_effective += 1

            # Skip the specified number of videos
            for i in range(shift):
                skipped_indices.append(current_raw + i)

            current_raw += shift

        # Return the corresponding skipped index for negative effective
        idx = -effective_index - 1
        return skipped_indices[idx] if idx < len(skipped_indices) else None

    # For positive effective indices, calculate the corresponding raw index
    offset_points = []
    for k, v in offsets.items():
        try:
            offset_points.append((int(k), int(v)))
        except (ValueError, TypeError):
            continue
    offset_points.sort(key=lambda x: x[0])

    raw_index = effective_index
    total_shift = 0

    for effective_threshold, shift in offset_points:
        if effective_index >= effective_threshold:
            total_shift += shift
        else:
            break

    return effective_index + total_shift


def resolve_alias_to_effective_index(data, alias) -> (int, bool):
    if not data or len(data) < 1:
        try:
            return int(alias), False  # Fallback to direct index if no metadata
        except ValueError:
            return None, False

    metadata = data[0]
    aliases = metadata.get("aliases", {})

    # Find index by alias
    for index, al in aliases.items():
        if al == alias:
            return int(index), True

    # Try to parse as direct index
    try:
        return int(alias), False
    except ValueError:
        return None, False


def update_offset(data, part_number, offset_value):
    if not data or len(data) < 1:
        return data

    metadata = data[0]
    if "offsets" not in metadata:
        metadata["offsets"] = {}

    if offset_value is None:
        metadata["offsets"].pop(part_number, None)
    else:
        metadata["offsets"][part_number] = offset_value

    return data


def update_alias(data, index, alias):
    if not data or len(data) < 1:
        return data

    metadata = data[0]
    if "aliases" not in metadata:
        metadata["aliases"] = {}

    if alias is None:
        metadata["aliases"].pop(index, None)
    else:
        metadata["aliases"][index] = alias

    return data


async def show_metadata(message, filepath):
    data = await ensure_clip_file_and_load(message, filepath)
    if data is None:
        return

    metadata = data[0]

    # Categorize metadata fields
    main_fields = {
        'name': metadata.get("name", "name not set"),
        'prefix': metadata.get("prefix", "prefix not set"),
        'url': metadata.get("url", "url not set"),
        'version': metadata.get("version", "version not set")
    }

    structural_fields = {
        'offsets': metadata.get("offsets", {}),
        'aliases': metadata.get("aliases", {})
    }

    response = ["```\nMetadata:"]

    # Main fields section
    response.append("\nMain Configuration:")
    for key, value in main_fields.items():
        response.append(f"  {key}: {repr(str(value))}")

    # Offsets section
    if structural_fields['offsets']:
        response.append("\nOffsets:")
        for part, offset in sorted(structural_fields['offsets'].items()):
            response.append(f"  Part {part}: +{offset}")
    else:
        response.append("\nNo offsets configured")

    # Aliases section
    if structural_fields['aliases']:
        response.append("\nAliases:")
        for index, alias in sorted(structural_fields['aliases'].items()):
            response.append(f"  Index {index}: '{alias}'")
    else:
        response.append("\nNo aliases configured")

    response.append("```")
    await message.channel.send("\n".join(response))
from plugins.tatoclip_plugin import ensure_clip_file_and_load

def get_effective_index(data, requested_index):
    if not data or len(data) < 1:
        return requested_index

    metadata = data[0]
    offsets = metadata.get("offsets", {})

    # Find the largest offset key <= requested_index
    max_offset_key = -1
    offset_value = 0
    for k, v in offsets.items():
        try:
            int_key = int(k)
            if int_key <= requested_index and int_key > max_offset_key:
                max_offset_key = int_key
                offset_value = v
        except (ValueError, TypeError):
            continue

    if max_offset_key != -1:
        return requested_index - offset_value
    return requested_index

def get_raw_index(data, effective_index):
    if not data or len(data) < 1:
        return effective_index

    metadata = data[0]
    offsets = metadata.get("offsets", {})

    # Find all keys where (key - offset) <= effective_index
    candidate_offsets = {}
    for k, v in offsets.items():
        try:
            int_key = int(k)
            if int_key <= effective_index:
                candidate_offsets[int_key] = v
        except (ValueError, TypeError):
            continue

    # From candidates, find the largest key
    if candidate_offsets:
        max_key = max(candidate_offsets.keys())
        return effective_index + candidate_offsets[max_key]
    return effective_index

def resolve_alias_to_effective_index(data, alias) -> (int, bool):
    if not data or len(data) < 1:
        try:
            return int(alias), False  # Fallback to direct index if no metadata
        except ValueError:
            return -1, False

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
        return -1, False


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
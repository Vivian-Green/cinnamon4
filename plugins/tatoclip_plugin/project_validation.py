
def convert_v0_to_v1(data: dict) -> list:
    """Convert version 0 project format to version 1"""
    if not isinstance(data, dict) or len(data) == 0:
        return data  # Not v0 format

    is_v0, msg = validate_project_file_v0(data)
    if not is_v0:
        print(msg)
        return data # invalid v0 format?

    new_data = []
    for url, videos in data.items():
        if not videos:
            continue

        # Extract metadata
        metadata = videos[0]
        metadata["url"] = url
        metadata["version"] = 1

        # Ensure name exists
        if "name" not in metadata:
            metadata["name"] = url.split('=')[-1][:20]  # Generate default name

        new_data.append(metadata)
        new_data.extend(videos[1:])

    return new_data

def validate_project_file(data):
    is_up_to_date, msg = validate_project_file_v1(data)
    if not is_up_to_date:
        is_v0, msg2 = validate_project_file_v0(data)
        if is_v0:
            msg = f"{msg}... actually, this is a valid v0 file..."
    return is_up_to_date, msg

def validate_project_file_v1(data):
    """Validate both old and new project file structures"""
    # Version 1 structure (list-based)
    if isinstance(data, list):
        if len(data) == 0:
            return True, "Empty file is valid for initialization"

        # Validate metadata (first element)
        metadata = data[0]
        if not isinstance(metadata, dict):
            return False, "First element must be metadata dictionary"

        required_keys = {"prefix", "name", "url", "version"}
        if not required_keys.issubset(metadata.keys()):
            return False, "Metadata missing required keys: prefix, name, url, version"

        if metadata["version"] != 1:
            return False, f"Unsupported version: {metadata['version']}"

        # Validate clip entries
        for i, entry in enumerate(data[1:], start=1):
            if not isinstance(entry, dict):
                return False, f"Entry {i} must be a dictionary"

            for timestamp, duration in entry.items():
                if not isinstance(duration, int) or duration < 0:
                    return False, f"Duration for timestamp {timestamp} must be positive integer"

        return True, "Valid version 1 structure"

    return False, "Root element must be list"

def validate_project_file_v0(data):
    """Validate the structure of a project/targets JSON file."""
    if not isinstance(data, dict):
        return False, "Root element must be a dictionary"

    if len(data) == 0:
        return True, "Empty file is valid for initialization"

    # Check each URL entry in the file
    for url, videos in data.items():
        if not isinstance(videos, list):
            return False, f"Videos for URL {url} must be a list"

        if len(videos) == 0:
            continue

        # First item should be metadata
        if not isinstance(videos[0], dict) or "prefix" not in videos[0] or "name" not in videos[0]:
            return False, "First item must be metadata with 'prefix' and 'name' fields"

        # Subsequent items should be either empty dicts or clip dictionaries
        for i, video in enumerate(videos[1:], start=1):
            if not isinstance(video, dict):
                return False, f"Video entry {i} must be a dictionary"

            for timestamp, duration in video.items():
                if not isinstance(duration, int) or duration < 0:
                    return False, f"Duration for timestamp {timestamp} must be a positive integer"

    return True, "File structure is valid"
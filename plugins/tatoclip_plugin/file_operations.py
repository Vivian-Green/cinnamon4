import json
import os
import traceback

from cinLogging import printLabelWithInfo
from plugins.tatoclip_plugin.project_validation import validate_project_file, convert_v0_to_v1


# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[file loading]

def save_json_to_filepath(data, filepath, save_backup=False):
    if save_backup:
        try:
            # Read old data first
            with open(filepath, 'r') as file:
                old_data = json.load(file)
            # Write backup file
            with open(f"{filepath}_old", 'w') as file:
                json.dump(old_data, file, indent=4)
            # Write new data to original file
            with open(filepath, 'w') as file:
                json.dump(data, file, indent=4)
        except FileNotFoundError:
            # If file doesn't exist, just write the new data
            with open(filepath, 'w') as file:
                json.dump(data, file, indent=4)
    else:
        with open(filepath, 'w') as file:
            json.dump(data, file, indent=4)




def load_clip_file(filepath):
    try:

        if not filepath:
            return None

        with open(filepath, 'r') as file:
            data = json.load(file)

        # Convert v0 to v1 if needed
        if isinstance(data, dict):
            printLabelWithInfo("Converting v0 to v1", filepath)
            data = convert_v0_to_v1(data)
            # Save converted version
            save_json_to_filepath(data, filepath, True)

        # Validate after conversion
        valid, msg = validate_project_file(data)
        if not valid:
            print(f"Invalid project file: {msg}")
            return None

        return data
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from '{filepath}'")
        return None
    except Exception as e:
        print(f"Unexpected error loading clip file: {str(e)}")
        traceback.print_exc()
        return None


async def ensure_clip_file_and_load(message, filepath): # wrapper for load_clip_file
    data = load_clip_file(filepath)
    if data is None:
        await message.channel.send("Failed to load clip file.")
        return None

    valid, msg = validate_project_file(data)
    if not valid:
        await message.channel.send(f"Invalid file structure: {msg}")
        return None

    return data
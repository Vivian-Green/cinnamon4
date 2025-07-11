import os
import json
import difflib
import time
import subprocess
import traceback

from pytube import Playlist

import cinIO
from cinIO import loadCache
from cinLogging import printLabelWithInfo

clip_file_names = {}
lastVideoIndex = 1

get_links_memo = {}
trust_links_memo_timestamp = 0

# old:
# {
# "https://www.youtube.com/watch?v=rLw2ndAW9NE&list=PLenI3Kbdx0D19iGG1nElWVp0GpI-cUHMQ": [
#    {
#        "prefix": "Part ",
#        "name": "example",... [name optional]
#    },
#       {data},
#       {data},...
#   ]
# }
# new:
# [
#   {
#       "prefix": "Part ",
#       "version": 1,
#       "name": "example", [name required]
#       "url": "https://www.youtube.com...list=..."
#   },
#   {
#       "0:00": 5,
#       "1:23": 30,...
#   },
#   {data},
#   {data},
# ]

def get_default_cache():
    return {
        "targets.json_path": "",
        "tatoclip.py_path": "",
        "trust_cache_time_seconds": 3600
    }

# Variables
tatoclip_config = loadCache("tatoclip/tatoclip_config.json", get_default_cache())

targets_json_path = tatoclip_config["targets.json_path"]
tatoclip_py_path = tatoclip_config["tatoclip.py_path"]
trust_cache_time_seconds = tatoclip_config["trust_cache_time_seconds"]


def convert_v0_to_v1(data):
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


def get_links(url):  # todo: this is already in tatoclip's common.py and has just been accidentally reengineered lmao, use whichever is better for both
    global get_links_memo
    global trust_links_memo_timestamp
    global trust_cache_time_seconds

    # Use memoized result if valid
    if trust_links_memo_timestamp > time.time() and url in get_links_memo:
        result = get_links_memo[url]
        if result:
            return result
        print(f"Previously failed to get links for playlist {url}, using cached result of False")
        return False

    try:
        playlist = Playlist(url)
        links = list(playlist.video_urls)
        get_links_memo[url] = links
        trust_links_memo_timestamp = time.time() + trust_cache_time_seconds
        return links
    except Exception as e:
        print(f"Failed to get links for {url}: {str(e)}")
        get_links_memo[url] = False
        traceback.print_exc()
        return False


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


def load_clip_file(message):
    global clip_file_names
    try:
        filepath = clip_file_names[message.channel.name]
        with open(filepath, 'r') as file:
            data = json.load(file)

        # Convert v0 to v1 if needed
        if isinstance(data, dict):
            # todo: should prolly check if is valid v0? but eh?
            printLabelWithInfo("Converting v0 to v1", filepath)
            new_data = convert_v0_to_v1(data)
            # Save converted version
            with open(filepath, 'w') as file:
                json.dump(new_data, file, indent=4)
            with open(f"{filepath}_old", 'w') as file:
                json.dump(data, file, indent=4)

        # Validate after conversion
        valid, msg = validate_project_file(data)
        if not valid:
            print(f"Invalid project file: {msg}")
            return None

        return data
    except FileNotFoundError:
        print(f"Error: File '{clip_file_names[message.channel.name]}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON from '{clip_file_names[message.channel.name]}'")
        return None
    except Exception as e:
        print(f"Unexpected error loading clip file: {str(e)}")
        return None


async def set_clip_file(message, words =""):
    global clip_file_names
    global lastVideoIndex

    if words == "":
        words = (message.content.split())
    if len(words) < 2: # ---------------------------------------------------------------------------------- infer filename from channel name if not supplied --- #
        words = ["!>setclipfile", f"targets_{message.channel.name}.json".replace("-", "_")]

    filename = words[1]
    guild_id = message.guild.id
    cache_dir = os.path.join(".", "cache", "tatoclip", str(guild_id))
    cinIO.ensureDirs([cache_dir])
    filepath = os.path.join(cache_dir, filename)

    if os.path.exists(filepath):  # ---------------------------------------------------------------------------------------------- case file exists, use it --- #
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            valid, msg = validate_project_file(data)
            if not valid:# todo: from here
                if "valid v0 file" in msg:
                    await message.channel.send(f"Warning: project file using metadata v0.. updating...")
                    new_data = convert_v0_to_v1(data)
                    # Save converted version
                    with open(filepath, 'w') as file:
                        json.dump(new_data, file, indent=4)
                    with open(f"{filepath}_old", 'w') as file:
                        json.dump(data, file, indent=4)
                    data = new_data
                else:
                    await message.channel.send(f"Warning: Invalid project file structure: {msg}")
        except Exception as e:
            await message.channel.send(f"Error validating file: {str(e)}")
            return False

        clip_file_names[message.channel.name] = filepath
        await message.channel.send(f"Loading clip configuration from {filepath}.")
        return True

    # Search for a close match within the cache directory
    json_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    closest_match = difflib.get_close_matches(f"targets_{filename}", json_files, n=1, cutoff=0.90)

    if closest_match: # ------------------------------------------------------------------------------------------- case fuzzy match for file exists, use it --- #
        filename = closest_match[0]
        filepath = os.path.join(cache_dir, filename)

        # Validate the matched file
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            valid, msg = validate_project_file(data)
            if not valid:
                await message.channel.send(f"Warning: Invalid project file structure in matched file (might just be missing url): {msg}")
        except Exception as e:
            await message.channel.send(f"Error validating matched file: {str(e)}")
            return False

        clip_file_names[message.channel.name] = filepath
        await message.channel.send(f"Found a close match for the alias: {filename}")

        data = load_clip_file(message)
        if data:
            lastVideoIndex = len(data)
        return True

    # ------------------------------------------------------------------------------------------- case no matching file found, create new file --- #
    url = words[2] if len(words) > 2 else ""

    # Create version 1 structure
    if url:
        links = get_links(url)
        if links is False:
            await message.channel.send(f"Failed to fetch playlist for {url}")
            return False

        data = [
            {
                "prefix": "Part ",
                "version": 1,
                "name": filename.replace("targets_", "").replace(".json", ""),
                "url": url
            }
        ]
        # Add empty clip entries
        for _ in range(len(links)):
            data.append({})
        await message.channel.send(f"New clip configuration created for {url}.")
    else:
        data = [
            {
                "prefix": "Part ",
                "version": 1,
                "name": filename.replace("targets_", "").replace(".json", ""),
                "url": ""
            }
        ]
        await message.channel.send(f"New empty clip configuration created. Add a URL later with !>seturl.")

    # Save the new project file in the cache directory
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)

    clip_file_names[message.channel.name] = filepath
    await message.channel.send(f"Clip configuration saved to {filepath}.")
    return True


async def set_url(message):
    global clip_file_names

    if message.channel.name not in clip_file_names:
        await message.channel.send("No clip file configured. Use !>setclipfile first.")
        return False

    words = message.content.split()
    if len(words) < 2:
        await message.channel.send("Usage: !>seturl <playlist_url>")
        return False

    url = words[1]
    filepath = clip_file_names[message.channel.name]

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        links = get_links(url)
        if links is False:
            await message.channel.send(f"Failed to fetch playlist for {url}. Please check the URL and try again.")
            return False

        old_url = next(iter(data.keys())) if data else ""
        if old_url:
            clips = data[old_url]
            data = {url: clips}
        else:
            data = {url: [
                {"prefix": "Part ", "name": os.path.basename(filepath).replace("targets_", "").replace(".json", "")}]}
            for i in range(len(links)):
                data[url].append({})

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

        await message.channel.send(f"Playlist URL updated to {url}")
        return True

    except Exception as e:
        await message.channel.send(f"Error updating URL: {str(e)}")
        return False


clipping_mode = {}


async def clip_toggle(message):
    global clipping_mode

    channel_id = str(message.channel.id)
    clipping_mode[channel_id] = not clipping_mode.get(channel_id, False)
    status = "enabled" if clipping_mode[channel_id] else "disabled"
    await message.channel.send(f"Clipping mode {status}.")


async def render_clips(message):
    words = message.content.split()
    if message.channel.name not in clip_file_names and not await set_clip_file(message, ["!>setclipfile"]):
        return

    # Ensure valid clip configuration
    data = await ensure_clip_file_and_load(message)
    if data is None:
        return

    # Write data to targets JSON
    try:
        with open(targets_json_path, 'w') as file:
            json.dump(data, file, indent=4)

        targets_root = os.path.dirname(targets_json_path)
        origin = os.path.basename(clip_file_names[message.channel.name])
        backup_path = os.path.join(targets_root, origin)
        with open(backup_path, 'w') as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        await message.channel.send(f"Error writing to targets.json: {e}")
        return

    # Build command
    command = ['python3', tatoclip_py_path]
    arg1 = words[1] if len(words) > 1 else None
    arg2 = words[2] if len(words) > 2 else None
    message_errs = True and arg1

    try:
        arg1 = str(int(arg1)) if arg1 else "1"
    except Exception as e:
        arg1 = "1"
        if message_errs:
            await message.channel.send(f"Error on arg 1: {e}. Using default: 1")
    command.append(arg1)

    try:
        if arg2:
            arg2 = str(int(arg2) + 1)
        else:
            message_errs = False
            playlist_length = 999
            arg2 = str(playlist_length)
    except Exception as e:
        playlist_length = 999
        arg2 = str(playlist_length)
        if message_errs:
            await message.channel.send(f"Error on arg 2: {e}. Using default: {999}")
    command.append(arg2)

    try:
        script_directory = os.path.dirname(tatoclip_py_path)
        subprocess.Popen(
            command,
            cwd=script_directory,
            shell=True
        )
        await message.channel.send(f"trying `{' '.join(command)}` o7")
    except Exception as e:
        await message.channel.send(f"Error executing render command: {e}")


async def clip(message):
    words = message.content.lower().split()
    global clipping_mode
    global lastVideoIndex
    global clip_file_names

    # Handle clipping mode
    if len(words) >= 2 and (":" in words[0] or ";" in words[0]) and str(message.channel.id) in clipping_mode:
        words.insert(0, "clip")
    elif not ("clip" in words[0]):
        return

    if message.channel.name not in clip_file_names and not await set_clip_file(message, ["!>setclipfile"]):
        return

    if len(words) > 1 and "toggle" in words[1]:
        await clip_toggle(message)
        return

    data = await ensure_clip_file_and_load(message)
    if data is None:
        return

    metadata = data[0]
    videos = data[1:]

    # Handle multiple timestamp-duration pairs
    if len(words) >= 3 and (":" in words[1] or ";" in words[1]):
        try:
            index = int(words[1])
            index -= 1
            if index < 1:
                raise ValueError("Index must be greater than 0.")
            pairs = words[2:]
        except ValueError:
            index = lastVideoIndex
            pairs = words[1:]

        results = []
        for i in range(0, len(pairs), 2):
            if i + 1 >= len(pairs):
                break

            timestamp = pairs[i].replace(";", ":")
            try:
                duration = int(pairs[i + 1])
            except ValueError:
                results.append(f"Invalid duration: {pairs[i + 1]}")
                continue

            url = metadata.get("url")

            # Ensure videos list is long enough
            if index > len(videos):
                # Extend the list to include the index
                while len(videos) < index:
                    videos.append({})

            # Get video segment
            video_segment = videos[index]

            # Add/remove clip
            if duration == 0:
                if timestamp in video_segment:
                    video_segment.pop(timestamp)
                    removed = True
                    results.append(f"Clip deleted at {timestamp}")
                else:
                    results.append(f"No clip found at {timestamp}")
                    continue
            else:
                video_segment[timestamp] = duration
                removed = False
                results.append(f"Clip added at {timestamp}")

            lastVideoIndex = index

        new_data = [metadata] + videos

        # Save changes
        data = new_data
        with open(clip_file_names[message.channel.name], 'w') as file:
            json.dump(data, file, indent=4)

        await message.channel.send("\n".join(results))
        return

    # Single clip handling
    if len(words) < 3:
        await message.channel.send("Usage: [clip] [index] <timestamp> <duration>")
        return

    words[1] = words[1].replace(";", ":")
    if ":" in words[1]:
        timestamp = words[1]
        index = lastVideoIndex
    else:
        try:
            index = int(words[1]) - 1
            if index < 0:
                raise ValueError("Index must be greater than 0.")
            timestamp = words[2]
        except ValueError as e:
            await message.channel.send(f"Invalid index: {e}")
            return

    try:
        duration = int(words[-1])
    except ValueError:
        await message.channel.send("Duration must be an integer.")
        return

    metadata = data[0]
    videos = data[1:]
    url = metadata.get("url")

    # Ensure videos list is long enough
    if index >= len(videos):
        while len(videos) <= index:
            videos.append({})

    video_segment = videos[index]

    # Add/remove clip
    removed = False
    if duration == 0:
        if timestamp in video_segment:
            video_segment.pop(timestamp)
            removed = True
        else:
            await message.channel.send(f"No clip found at {timestamp}")
            return
    else:
        video_segment[timestamp] = duration

    new_data = [metadata] + videos
    # Save changes
    data = new_data
    with open(clip_file_names[message.channel.name], 'w') as file:
        json.dump(data, file, indent=4)

    lastVideoIndex = index

    # Get link if possible
    links = get_links(url)
    if links and index - 1 < len(links):
        link = links[index - 1]
        time_param = f"&t={timestamp_to_sec(timestamp)}"
    else:
        link = "Failed to get video link"
        time_param = ""

    if removed:
        await message.channel.send(f"Clip deleted at index {index+1} with timestamp {timestamp}")
    else:
        await message.channel.send(
            f"Clip added/updated at index {index+1} with timestamp {timestamp} and duration {duration}s.\n{link}{time_param}")


async def get_clips(message):
    words = message.content.split()
    global clip_file_names
    if len(words) < 2:
        await message.channel.send("Usage: !>getclips <index>")
        return

    try:
        index = int(words[1]) - 1
        if index < 0:
            raise ValueError("Index must be greater than 0.")
    except ValueError as e:
        await message.channel.send(f"Invalid index: {e}")
        return

    data = await ensure_clip_file_and_load(message)
    if data is None:
        return

    metadata = data[0]
    videos = data[1:]

    if index >= len(videos):
        await message.channel.send(f"Index {index+1} is out of bounds. Maximum index is {len(videos)}.")
        return

    clips = videos[index-1]
    if not isinstance(clips, dict):
        await message.channel.send(f"Unexpected format in the clip file at index {index+1}.")
        return

    # Format clips for display
    clips_str = "\n".join(
        [f"{timestamp}: {duration}s" for timestamp, duration in clips.items()])
    response = f"Clips for index {index+1}:\n{clips_str}"

    await message.channel.send(f"```{response}```")


async def get_all_clips(message):
    global clip_file_names

    data = await ensure_clip_file_and_load(message)
    if data is None:
        return

    metadata = data[0]
    videos = data[1:]
    url = metadata.get("url")

    links = get_links(url)

    if not videos:
        await message.channel.send("No clips found.")
        return

    blocks = []
    total_runtime = 0
    index = 0
    for clips in videos:
        index += 1
        if not isinstance(clips, dict):
            continue

        runtime = 0
        clip_lines = []

        # Add link if available
        if links and index - 1 < len(links):
            clip_lines.append(links[index - 1])
        else:
            clip_lines.append(f"Video {index} (link unavailable)")

        # Process clips
        for timestamp, duration in clips.items():
            seconds = timestamp_to_sec(timestamp) if ":" in timestamp else int(timestamp)
            clip_lines.append(f"    {timestamp}: {duration}s")
            runtime += duration

        total_runtime += runtime
        clip_block = f"Index {index} (runtime: {format_seconds(runtime)}):\n" + "\n".join(clip_lines)
        blocks.append(f"```{clip_block}```")

    # Send in chunks
    max_length = 1900
    current_block = ""
    for block in blocks:
        if len(current_block) + len(block) > max_length:
            await message.channel.send(current_block)
            current_block = ""
            time.sleep(1)
        current_block += block + "\n"

    if current_block:
        await message.channel.send(current_block)

    await message.channel.send(f"Total runtime: {format_seconds(total_runtime)}")


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


async def ensure_clip_file_and_load(message):
    if message.channel.name not in clip_file_names or not os.path.exists(clip_file_names[message.channel.name]):
        await message.channel.send("No clip configuration found. Use !>setclipfile to initialize.")
        return None

    data = load_clip_file(message)
    if data is None:
        await message.channel.send("Failed to load clip file.")
        return None

    valid, msg = validate_project_file(data)
    if not valid:
        await message.channel.send(f"Invalid file structure: {msg}")
        return None

    return data


# Binding functions
def bind_phrases():
    return {
        "*": clip
    }


def bind_commands():
    return {
        "setclipfile": set_clip_file,
        "clip": clip,
        "getclips": get_clips,
        "getallclips": get_all_clips,
        "renderclips": render_clips,
        "seturl": set_url,
    }


def bind_help():
    return {
        "setclipfile": "Initialize or configure clip settings. Usage:\n"
                       "`!>setclipfile [filename.json] [playlist_url]`\n\n"
                       "• Creates new config if file doesn't exist\n"
                       "• URL is optional\n"
                       "• Auto-matches similar filenames\n"
                       "• Defaults to `targets_[channelname].json`",
        "seturl": "Add/update playlist URL. Usage: `!>seturl <playlist_url>`",
        "clip": "Add/edit clips. Usage:\n"
                "`[clip] <index> <timestamp> <duration>`\n"
                "`[clip] <timestamp> <duration>` (uses last index)\n"
                "`clip toggle` - Toggle clipping mode\n"
                "Set duration=0 to delete clip",
        "getclips": "View clips for video. Usage: `!>getclips <index>`",
        "getallclips": "View all clips. Usage: `!>getallclips`",
        "renderclips": "Start rendering. Usage: `!>renderclips [start] [end]`"
    }
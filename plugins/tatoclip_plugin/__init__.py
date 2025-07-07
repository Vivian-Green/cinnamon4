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

# todo: update to use metadata version 1
# todo: handle cases where get_links( returns false
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

# todo: snake_case function namessssss

def getDefaultCache():
    return {
        "targets.json_path": "",
        "tatoclip.py_path": "",
        "trust_cache_time_seconds": 3600
    }

# Variables
tatoclip_config = loadCache("tatoclip/tatoclip_config.json", getDefaultCache())

targets_json_path = tatoclip_config["targets.json_path"]
tatoclip_py_path = tatoclip_config["tatoclip.py_path"]
trust_cache_time_seconds = tatoclip_config["trust_cache_time_seconds"]


def validate_project_file(data):
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

    if trust_links_memo_timestamp > time.time() and url in get_links_memo:
        return get_links_memo[url]

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
        with open(clip_file_names[message.channel.name], 'r') as file:
            data = json.load(file)
        return data
    except FileNotFoundError:
        print(f"Error: File '{clip_file_names[message.channel.name]}' not found.")
        return None
    except json.JSONDecodeError:
        print(
            f"Error: Failed to parse JSON from '{clip_file_names[message.channel.name]}'. The file might be corrupted or improperly formatted.")
        return None
    except Exception as e:
        print(f"Unexpected error occurred while accessing '{clip_file_names[message.channel.name]}': {str(e)}")
        return None


async def setclipfile(message, words = ""):
    global clip_file_names

    if words == "":
        words = (message.content.split())
    if len(words) < 2: # ---------------------------------------------------------------------------------- infer filename from channel name if not supplied --- #
        words = ["!>setclipfile", f"targets_{message.channel.name}.json".replace("-", "_")]

    filename = words[1]
    guild_id = message.guild.id
    cache_dir = os.path.join(".", "cache", "tatoclip", str(guild_id))
    cinIO.ensureDirs([cache_dir])
    filepath = os.path.join(cache_dir, filename)

    if os.path.exists(
            filepath):  # ------------------------------------------------------------------------------------------------ case file exists, use it --- #
        # Validate existing file
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            valid, msg = validate_project_file(data)
            if not valid:
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
        global lastVideoIndex
        lastVideoIndex = len(data)

        return True

    # ------------------------------------------------------------------------------------------- case no matching file found, create new file --- #
    # URL is now optional - create empty structure if not provided
    url = words[2] if len(words) > 2 else ""

    if url:
        try:
            print("yop?")
            links = get_links(url)
            data = {url: []}
            data[url].append({"prefix": "Part ", "name": filename.replace("targets_", "").replace(".json", "")})
            for i in range(len(links)):  # Pad to length of playlist
                data[url].append({})
            await message.channel.send(f"New clip configuration created for {url}.")
        except Exception as e:
            await message.channel.send(f"Error processing playlist URL: {str(e)}")
            return False
    else:
        # Create empty structure without URL
        data = {"": [{"prefix": "Part ", "name": filename.replace("targets_", "").replace(".json", "")}]}
        await message.channel.send(f"New empty clip configuration created. Add a URL later with !>seturl.")

    # Save the new configuration file in the cache directory
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)

    # Update the global clip_file_names dictionary with the channel name and filepath
    clip_file_names[message.channel.name] = filepath
    await message.channel.send(f"Clip configuration saved to {filepath}.")
    return True


async def seturl(message):
    """Command to add/update the playlist URL in an existing project file"""
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
        # Load existing data
        with open(filepath, 'r') as f:
            data = json.load(f)

        # Validate the URL
        print("yop2?")
        links = get_links(url)

        # If file has existing URL, keep the clips but update the URL
        old_url = next(iter(data.keys())) if data else ""
        if old_url:
            # Move existing clips under new URL
            clips = data[old_url]
            data = {url: clips}
        else:
            # Create new structure with URL
            data = {url: [
                {"prefix": "Part ", "name": os.path.basename(filepath).replace("targets_", "").replace(".json", "")}]}
            for i in range(len(links)):  # Pad to length of playlist
                data[url].append({})

        # Save updated file
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)

        await message.channel.send(f"Playlist URL updated to {url}")
        return True

    except Exception as e:
        await message.channel.send(f"Error updating URL: {str(e)}")
        return False



clipping_mode = {}


async def clipToggle(message):
    global clipping_mode

    channel_id = str(message.channel.id)
    clipping_mode[channel_id] = not clipping_mode.get(channel_id, False)
    status = "enabled" if clipping_mode[channel_id] else "disabled"
    await message.channel.send(f"Clipping mode {status}.")


async def renderClips(message):
    words = message.content.split()
    if message.channel.name not in clip_file_names and not await setclipfile(message, ["!>setclipfile"]): return

    await getAllClips(message)

    # Ensure valid clip configuration
    data = await ensureClipFileAndLoad(message)
    if data is None: return

    # Write data to the targets JSON file
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
        # Process arg1
        arg1 = str(int(arg1)) if arg1 else "1"
    except Exception as e:
        printLabelWithInfo("!>renderClips", f"Error on arg 1: {e}. Using default: 1")
        arg1 = "1"
        if message_errs:
            message.channel.send(f"Error on arg 1: {e}. Using default: 1")
    command.append(arg1)

    try:
        # Process arg2
        if arg2:
            arg2 = str(int(arg2) + 1)
        else:
            message_errs = False
            playlist_length = 999
            arg2 = str(playlist_length)  # Default to the playlist length
    except Exception as e:
        playlist_length = 999
        printLabelWithInfo("!>renderClips", f"Error on arg 2: {e}. Using default: {999}")
        arg2 = str(playlist_length)
        if message_errs:
            message.channel.send(f"Error on arg 2: {e}. Using default: {999}")
    command.append(arg2)

    try:
        # Open the new process in a separate window without waiting for it to finish
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

    # If in clipping mode and first word is a timestamp, prepend clip command
    if len(words) >= 2 and (":" in words[0] or ";" in words[0]) and str(message.channel.id) in clipping_mode:
        words.insert(0, "clip")
    elif not ("clip" in words[0]):
        return  # if not clip command, return

    if message.channel.name not in clip_file_names and not await setclipfile(message, ["!>setclipfile"]):
        return  # if no clip file set and !>setclipfile doesn't find one, return

    if len(words) > 1 and "toggle" in words[1]:
        await clipToggle(message)
        return # clip toggle toggled, return

    print("aAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")

    data = await ensureClipFileAndLoad(message)
    if data is None: return

    # Handle multiple timestamp-duration pairs
    if len(words) >= 3 and (":" in words[1] or ";" in words[1]):
        # Determine if first argument is index or timestamp
        try:
            index = int(words[1])
            if index < 1:
                raise ValueError("Index must be greater than 0.")
            pairs = words[2:]
        except ValueError:
            index = lastVideoIndex
            pairs = words[1:]

        # Process pairs two at a time (timestamp, duration)
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

            # Process the clip
            url = list(data.keys())[0]
            videos = data[url]
            print("yop3?")
            links = get_links(url) or [""] * 100

            removed = False
            if index > len(links):
                results.append(f"Index {index} is out of bounds. Maximum index is {len(videos)}.")
                continue
            elif index == len(videos) - 1 or index >= len(videos):
                videos.append({timestamp: duration})
            else:
                video_segment = videos[index]
                if isinstance(video_segment, dict):
                    video_segment[timestamp] = duration
                    if duration == 0:
                        video_segment.pop(timestamp)
                        removed = True
                else:
                    results.append(f"Unexpected format in the clip file at index {index}.")
                    continue

            lastVideoIndex = index
            print("yop4?")
            links = get_links(url)
            if links:
                link = links[index - 1]
            else:
                link = "failed to get link?"

            if removed:
                results.append(f"Clip deleted at {timestamp}")
            else:
                results.append(f"{timestamp}: {duration}s - {link}&t={timestamp_to_sec(timestamp)}")

        # Save changes
        data[url] = videos
        with open(clip_file_names[message.channel.name], 'w') as file:
            json.dump(data, file, indent=4)

        await message.channel.send("\n".join(results))
        return

    # Original single clip handling (unchanged)
    if len(words) < 3:
        await message.channel.send("Usage: [clip] [index] <timestamp> <duration>")
        return

    words[1] = words[1].replace(";", ":")
    if ":" in words[1]:
        timestamp = words[1]
        index = lastVideoIndex
    else:
        try:
            index = int(words[1])
            if index < 1:
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

    url = list(data.keys())[0]
    videos = data[url]
    print("yop5?")
    links = get_links(url) or [""] * 100

    removed = False
    if index > len(links):
        await message.channel.send(f"Index {index} is out of bounds. Maximum index is {len(videos)}.")
        return
    elif index == len(videos) - 1 or index >= len(videos):
        videos.append({timestamp: duration})
    else:
        video_segment = videos[index]
        if isinstance(video_segment, dict):
            video_segment[timestamp] = duration
            if duration == 0:
                video_segment.pop(timestamp)
                removed = True
        else:
            await message.channel.send(f"Unexpected format in the clip file at index {index}.")
            return

    data[url] = videos
    with open(clip_file_names[message.channel.name], 'w') as file:
        json.dump(data, file, indent=4)

    lastVideoIndex = index
    print("yop6?")
    links = get_links(url)
    if links:
        link = links[index - 1]
    else:
        print("get_links returned false?")
        link = "get_links returned false?"
    print("b")

    if removed:
        await message.channel.send(f"Clip deleted at index {index} with timestamp {timestamp}")
    else:
        await message.channel.send(
            f"Clip added/updated at index {index} with timestamp {timestamp} and duration {duration}s.\n{link}&t={timestamp_to_sec(timestamp)}")


async def getClips(message):
    words = message.content.split()
    global clip_file_names
    if len(words) < 2:
        await message.channel.send("Usage: !>getclips <index>")
        return

    try:
        index = int(words[1])
        if index < 1:
            raise ValueError("Index must be greater than 0.")
    except ValueError as e:
        await message.channel.send(f"Invalid index: {e}")
        return

    data = await ensureClipFileAndLoad(message)
    if data is None: return

    url = list(data.keys())[0]
    videos = data[url]

    if index > len(videos):
        await message.channel.send(f"Index {index} is out of bounds. Maximum index is {len(videos)}.")
        return

    clips = videos[index]
    if not isinstance(clips, dict):
        await message.channel.send(f"Unexpected format in the clip file at index {index}.")
        return

    print("yop8?")
    link = get_links(url)[index - 1]

    # Format the clips for display
    clips_str = "\n".join(
        [f"{link}&t={timestamp_to_sec(timestamp)}  {timestamp}: {duration}s" for timestamp, duration in clips.items()])
    response = f"```Clips for index {index}:```\n{clips_str}"

    await message.channel.send(response)


async def getAllClips(message):
    global clip_file_names

    data = await ensureClipFileAndLoad(message)
    if data is None: return

    url = list(data.keys())[0]
    videos = data[url]

    print("yop9?")
    links = get_links(url)

    if not videos:
        await message.channel.send("No clips found.")
        return

    lines = 0
    blocks = []
    total_runtime = 0
    for index, clips in enumerate(videos[1:], start=1):
        runtime = 0
        if index > len(links):  # todo tape: for some reason, first clip to last video in playlist is added to index+1, this patches that, forcing all OOB video clips to last video
            videos[len(links)].update(videos[index])
            videos.pop(index)
            index = len(links)
            data[url] = videos
            print(data)
            with open(clip_file_names[message.channel.name], 'w') as file:  # todo: tape machine broke?
                json.dump(data, file, indent=4)
        if isinstance(clips, dict):
            clip_lines = []
            clip_lines.append(links[index - 1])
            for timestamp, duration in clips.items():
                seconds = timestamp
                if ":" in timestamp:
                    seconds = timestamp_to_sec(timestamp)
                clip_lines.append(f"    {timestamp}: {duration}s")
                runtime += duration
                lines += 1

            clips_str = "\n".join(clip_lines)
            response = f"``` Clips for index {index} (runtime: {format_seconds(runtime)}): {clips_str}```"
            total_runtime += runtime

            if lines > 0:
                lines = 0
                blocks.append(response)
        else:
            await message.channel.send(f"Unexpected format in the clip file at index {index}.")

    length = 0
    max_length = 1900
    merged = ""
    for block in blocks:
        length += len(block)
        if length > max_length:
            await message.channel.send(merged)
            merged = ""
            length = len(block)
            time.sleep(1)
        merged += block

    await message.channel.send(merged + f"\ntotal runtime: {format_seconds(total_runtime)}")


def format_seconds(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60

    # Handle single-digit values by converting to string
    parts = []
    if hours > 0:
        parts.append(f"{hours}")
        parts.append(f"{minutes:02d}")
    else:
        if minutes > 0:
            parts.append(f"{minutes}")

    parts.append(f"{seconds:02d}")

    return ":".join(parts)


async def ensureClipFileAndLoad(message):
    if message.channel.name not in clip_file_names or not os.path.exists(clip_file_names[message.channel.name]):
        await message.channel.send("No clip configuration found. Use !>setclipfile to initialize.")
        return None

    data = load_clip_file(message)
    if data is None:
        await message.channel.send("Json says no?")
        return None

    valid, msg = validate_project_file(data)
    if valid:
        return data
    else:
        message.channel.send("failed to validate file: {msg}")
        return None

    return data


# Binding functions
def bind_phrases():
    return {
        "*": clip
    }

def bind_commands():
    return {
        "setclipfile": setclipfile,
        "clip": clip,
        "getclips": getClips,
        "getallclips": getAllClips,
        "renderclips": renderClips,
        "seturl": seturl,
    }

def bind_help():
    return {
        "setclipfile": "Initialize or configure clip settings. Usage:\n"
                       "`!>setclipfile [filename.json] [playlist_url]`\n\n"
                       "• Creates new config if file doesn't exist\n"
                       "• URL is optional - can be added later with !>seturl\n"
                       "• Auto-matches similar filenames\n"
                       "• Defaults to `targets_[channelname].json`\n\n"
                       "Example:\n"
                       "`!>setclipfile targets_tutorials.json` (create empty)\n"
                       "`!>setclipfile targets_lessons.json https://youtube.com/playlist?list=...`",

        "seturl": "Add or update the playlist URL in an existing project file.\n"
                  "Usage: `!>seturl <playlist_url>`\n\n"
                  "Example: `!>seturl https://youtube.com/playlist?list=...`",

        "clip": "Add/edit video clips. Usage:\n"
                "`[clip] <video index> <timestamp> <duration>` (sets video index)\n"
                "`[clip] <timestamp> <duration>` (uses previous video index)\n"
                "`clip toggle` - Toggle clipping mode (whether \"clip\" command is needed)\n\n"

                "- Timestamp format: `HH:MM:SS` or `MM:SS`\n"
                "- Set duration to 0 to delete a clip\n"
                "- autocorrects ; to :\n"
                "Examples:\n"
                "`clip 3 1:30 15` (index 3 at 1m30s for 15s)\n"
                "`2;45 10` (last index at 2m45s for 10s, with clipping mode enabled)\n"
                "`clip toggle` (enable/disable clipping mode)",

        "getclips": "View clips for specific video. Usage:\n"
                    "`!>getclips <index>`\n\n",

        "getallclips": "View all clips in playlist with total runtime calculation. Usage:\n"
                       "`!>getallclips`\n\n",

        "renderclips": "Start rendering process. Usage:\n"
                       "`!>renderclips [start_index] [end_index]`\n\n"
    }

import os
import json
import difflib
import time
import subprocess
from pytube import Playlist

import cinIO
from cinIO import loadCache
from cinLogging import printLabelWithInfo

clip_file_names = {}
lastVideoIndex = 0

get_links_memo = {}
trust_links_memo_timestamp = 0

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


def get_links(url):  # todo: this is already in tatoclip's common.py and has just been accidentally reengineered lmao, use whichever is better for both
    global get_links_memo
    global trust_links_memo_timestamp
    global trust_cache_time_seconds

    if trust_links_memo_timestamp > time.time() and url in get_links_memo:
        return get_links_memo[url]

    playlist = Playlist(url)
    links = list(playlist.video_urls)
    get_links_memo[url] = links
    trust_links_memo_timestamp = time.time() + trust_cache_time_seconds
    return links


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
    guild_id = message.guild.id  # Assuming `guild_id` is available from the message object # todo: assert outside of DM for this plugin?
    cache_dir = os.path.join(".", "cache", "tatoclip", str(guild_id))
    cinIO.ensureDirs([cache_dir])
    filepath = os.path.join(cache_dir, filename)

    if os.path.exists(filepath): # ------------------------------------------------------------------------------------------------ case file exists, use it --- #
        clip_file_names[message.channel.name] = filepath
        await message.channel.send(f"Loading clip configuration from {filepath}.")
        return True

    # Search for a close match within the cache directory
    json_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    closest_match = difflib.get_close_matches(f"targets_{filename}", json_files, n=1, cutoff=0.90)

    if closest_match: # ------------------------------------------------------------------------------------------- case fuzzy match for file exists, use it --- #
        filename = closest_match[0]
        filepath = os.path.join(cache_dir, filename)
        clip_file_names[message.channel.name] = filepath
        await message.channel.send(f"Found a close match for the alias: {filename}")
        return True

    # On 404, require URL to build the file
    if len(words) < 3: # ------------------------------------------------------------ case no matching file and no link provided, prompt req link; fail case --- #
        await message.channel.send(f"No match for {filename}. Usage: !>setclipfile <filename.json> <url>")
        return False

    # ------------------------------------------------------------------------------------------- case no matching file found, but link provided; build file --- #
    url = words[2]
    links = get_links(url)

    data = {url: []}
    data[url].append({"prefix": "Part ", "name": filename.replace("targets_", "").replace(".json", "")})
    for i in range(len(links)):  # Pad to length of playlist
        data[url].append({})

    await message.channel.send(f"New clip configuration created for {url}.")

    # Save the new configuration file in the cache directory
    with open(filepath, 'w') as file:
        json.dump(data, file, indent=4)

    # Update the global clip_file_names dictionary with the channel name and filepath
    await message.channel.send(f"Clip configuration saved to {filepath}.")
    return True



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
    words = message.content.split()
    global clipping_mode
    global lastVideoIndex
    global clip_file_names

    # If in clipping mode and first word is a timestamp, prepend clip command
    if len(words) == 2 and (":" in words[0] or ";" in words[0]) and str(message.channel.id) in clipping_mode:
        words.insert(0, "clip")
    elif not ("clip" in words[0]): return # if not clip command, return

    if message.channel.name not in clip_file_names and not await setclipfile(message, ["!>setclipfile"]):
        return # if no clip file set and !>setclipfile doesn't find one, return

    if len(words) > 1 and "toggle" in words[1]:
        await clipToggle(message)
        return # clip toggle toggled, return

    if len(words) < 3:
        await message.channel.send("Usage: [clip] [index] <timestamp> <duration>")
        return # missing an arg?

    data = await ensureClipFileAndLoad(message)
    if data is None: return

    #       check valid timestamp
    words[1] = words[1].replace(";", ":") # allow semicolon typo for timestamps
    if ":" in words[1]:
        timestamp = words[1]
        index = lastVideoIndex  # Use the last used index
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

    # actually clip

    url = list(data.keys())[0]
    links = list(Playlist(url))
    videos = data[url]

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

    if removed:
        await message.channel.send(f"Clip deleted at index {index} with timestamp {timestamp}")
    else:
        link = get_links(url)[index - 1]
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

    links = get_links(url)

    if not videos:
        await message.channel.send("No clips found.")
        return

    lines = 0
    blocks = []
    total_runtime = 0
    for index, clips in enumerate(videos[1:], start=1):
        runtime = 0
        if index > len(links):  # tape: for some reason, first clip to last video in playlist is added to index+1, this patches that, forcing all OOB video clips to last video
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
    }
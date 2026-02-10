import os
import difflib
import time
import subprocess
import traceback

#import discord
import cinAPI
from pytube import Playlist

import cinIO
from cinIO import loadCache
from plugins.tatoclip_plugin.file_operations import save_json_to_filepath, load_clip_file, ensure_clip_file_and_load
from plugins.tatoclip_plugin.metadata_handler import show_metadata, resolve_alias_to_effective_index, get_effective_index, \
    update_offset, update_alias, get_raw_index
from plugins.tatoclip_plugin.project_validation import validate_project_file
from plugins.tatoclip_plugin.time_utils import timestamp_to_sec, format_seconds

def get_default_cache():
    return {
        "targets.json_path": "",
        "tatoclip.py_path": "",
        "trust_cache_time_seconds": 3600
    }

# todo: once-over this and all sister files post refactor, lmao

lastVideoRawIndex = 1

get_links_memo = {}
trust_links_memo_timestamp = 0

tatoclip_config = loadCache("tatoclip/tatoclip_config.json", get_default_cache())

targets_json_path = tatoclip_config["targets.json_path"]
tatoclip_py_path = tatoclip_config["tatoclip.py_path"]
trust_cache_time_seconds = tatoclip_config["trust_cache_time_seconds"]

clipping_mode = {}
clip_file_names = {}

async def get_file_path_from_message(message: cinAPI.APIMessage):
    global clip_file_names
    if message.channel.name not in clip_file_names or not os.path.exists(clip_file_names[message.channel.name]):
        await message.channel.send("No clip configuration found. Use !>setclipfile to initialize.")
        return None
    return clip_file_names[message.channel.name]

async def check_with_err(condition: bool, warning: str, message: cinAPI.APIMessage = None):
    if condition: return True
    if message:
        await message.channel.send(warning)
    else:
        print(warning)
    return False

def get_links(url):  # todo: this is already in tatoclip's common.py and has just been accidentally reengineered lmao, use whichever is better for both
    global get_links_memo
    global trust_links_memo_timestamp
    global trust_cache_time_seconds

    # Use memoized result if valid
    if time.time() < trust_links_memo_timestamp and url in get_links_memo:
        result = get_links_memo[url]
        if result: return result

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


# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[discord commands]

async def clip_toggle(message: cinAPI.APIMessage):
    global clipping_mode

    channel_id = str(message.channel.id)
    clipping_mode[channel_id] = not clipping_mode.get(channel_id, False)
    status = "enabled" if clipping_mode[channel_id] else "disabled"
    await message.channel.send(f"Clipping mode {status}.")


async def clip(message: cinAPI.APIMessage):
    debug_clip_command = True
    if debug_clip_command: print(f"clip command received while debug_clip_command = True")

    words = message.content.lower().split()
    global clipping_mode, lastVideoRawIndex, clip_file_names

    # Handle clipping mode
    if len(words) >= 2 and (":" in words[0] or ";" in words[0]) and str(message.channel.id) in clipping_mode:
        words.insert(0, "clip")
    elif not ("clip" in words[0]):
        return

    if message.channel.name not in clip_file_names and not await set_clip_fileW(message, ["!>setclipfile"]): return

    if len(words) > 1 and "toggle" in words[1]:
        await clip_toggle(message)
        return

    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None: return

    # Determine raw_index and pairs_start position
    raw_index = None
    effective_index = None
    pairs_start = 1  # Default to assuming first word is timestamp

    # Try to parse as alias or index
    if len(words) >= 2:
        alias_or_index = words[1]
        effective_index, is_alias = resolve_alias_to_effective_index(data, alias_or_index)

        if is_alias or effective_index is not None:
            raw_index = effective_index if is_alias else get_raw_index(data, effective_index)
            pairs_start = 2

    # If not determined yet, use lastVideoIndex
    if raw_index is None:
        raw_index = lastVideoRawIndex
    else:
        lastVideoRawIndex = raw_index

    if effective_index is None:
        effective_index = get_effective_index(data, raw_index)

    # Check if this is a bulk clip command
    is_bulk = False
    if len(words) >= 3:
        timestamp_count = sum(1 for word in words[pairs_start:] if ":" in word or ";" in word)
        is_bulk = timestamp_count > 1 or (timestamp_count == 1 and len(words) > pairs_start + 2)

    if is_bulk:
        new_data, results = await handle_batch_clips(message, data, raw_index, pairs_start)
    else:
        # Single clip handling
        if not await check_with_err(len(words) >= pairs_start + 2, "Usage: [clip] [index] <timestamp> <duration>", message): return

        new_data, results = await handle_single_clip(message, data, raw_index, pairs_start)

    # save changes
    if new_data:
        save_json_to_filepath(new_data, clip_file_names[message.channel.name], False)

    results = f"For index {effective_index} (raw index {raw_index}): \n" + results

    if results:
        await message.channel.send(results)
    if debug_clip_command: print(f"end clip command while debug_clip_command = True")


def process_single_clip(data: list, raw_index: int, timestamp: str, duration: int) -> tuple:
    metadata = data[0]
    videos = data[1:]
    timestamp = timestamp.replace(";", ":")

    # Ensure videos list is long enough
    if raw_index > len(videos):
        while len(videos) < raw_index:
            videos.append({})

    result_msg = ""

    # Add/remove clip
    if duration == 0:
        if timestamp in videos[raw_index - 1]:
            videos[raw_index - 1].pop(timestamp)
            result_msg = f"Clip deleted at {timestamp}"
        else:
            return None, f"No clip found at {timestamp}"
    else:
        videos[raw_index - 1][timestamp] = duration
        result_msg = f"Clip added/updated at {timestamp} with duration {duration}s"

        # Add link if available
        url = metadata.get("url", "")
        links = get_links(url)
        if links and raw_index <= len(links):
            link = links[raw_index - 1]
            time_param = f"&t={timestamp_to_sec(timestamp)}"
            result_msg += f" `{link}{time_param}`"

    return [metadata] + videos, result_msg


async def handle_single_clip(message, data, raw_index, pairs_start) -> (list, str):
    words = message.content.lower().split()

    try:
        timestamp = words[pairs_start].replace(";", ":")
        duration = int(words[pairs_start + 1])
    except (ValueError, IndexError):
        return None, "Duration must be an integer."

    new_data, result_msg = process_single_clip(data, raw_index, timestamp, duration)
    result_msg = result_msg.replace("`", "")

    return new_data, result_msg

async def handle_batch_clips(message, data, raw_index, pairs_start) -> (list, str):
    words = message.content.lower().split()
    pairs = words[pairs_start:]
    results = []
    current_data = data

    for i in range(0, len(pairs), 2):
        if i + 1 >= len(pairs):
            break

        timestamp = pairs[i]
        try:
            duration = int(pairs[i + 1])
        except ValueError:
            results.append(f"Invalid duration: {pairs[i + 1]}")
            continue

        updated_data, result_msg = process_single_clip(current_data, raw_index, timestamp, duration)
        if updated_data is None:
            results.append(result_msg)
        else:
            current_data = updated_data
            results.append(result_msg)

    # Add video reference if available
    url = current_data[0].get("url")
    links = get_links(url)
    if links and raw_index <= len(links):
        results.append(f"\nVideo reference: {links[raw_index - 1]}")

    return current_data, "\n".join(results)

def format_part_info(data, raw_index):
    """Returns formatted string showing raw index, effective index, and alias"""
    raw_index = int(raw_index)
    if len(data) <= 1:  # No videos in data
        return f"Part {raw_index}"

    metadata = data[0]
    aliases = metadata.get("aliases", {})

    # Calculate effective index
    effective_index = get_effective_index(data, raw_index)

    info_parts = [
        f"Raw index: {raw_index}",
        f"Effective index: {effective_index}"
    ]

    # Add alias if exists
    alias = aliases.get(str(raw_index))
    if alias:
        info_parts.append(f"Alias: {alias}")

    return " | ".join(info_parts)

async def format_clips_for_video(data: list, raw_index: int) -> str:
    """Common helper for formatting clips for a single video"""
    if raw_index >= len(data[1:]):
        return None

    clips = data[1:][raw_index - 1]
    if not isinstance(clips, dict):
        return None

    part_info = format_part_info(data, raw_index)
    url = data[0].get("url")
    links = get_links(url)

    lines = [part_info]
    if links and raw_index <= len(links):
        lines.append(f"Video URL: {links[raw_index - 1]}")

    lines.extend(f"{timestamp}: {duration}s" for timestamp, duration in clips.items())
    return "\n".join(lines)

async def get_clips(message: cinAPI.APIMessage):
    words = message.content.split()
    global clip_file_names
    if not await check_with_err(len(words) >= 2, "Usage: !>getclips <index or alias>", message): return

    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None: return

    # Try to parse as alias first
    alias_or_index = words[1]
    effective_index, is_alias = resolve_alias_to_effective_index(data, alias_or_index)

    if effective_index is None:
        await message.channel.send(f"Invalid index or alias: {alias_or_index}")
        return

    print("\n\n\n\n\n\njjjjjj\n\n\n\n\n\n")

    # If not an alias, parse as effective index
    raw_index = effective_index if is_alias else get_raw_index(data, effective_index)

    formatted = await format_clips_for_video(data, raw_index)

    if not formatted:
        formatted = "No clips found for specified video"
        await message.channel.send(f"```{formatted}```")
        return

    metadata = data[0]
    videos = data[1:]
    if not await check_with_err(1 <= raw_index <= len(videos), f"Index {raw_index} is out of bounds. Maximum index is {len(videos)}.", message): return

    clips = videos[raw_index - 1]
    if not await check_with_err(isinstance(clips, dict), f"Unexpected format in the clip file at index {raw_index}.", message): return

    video_url = data[0].get("url")
    links = get_links(video_url)
    if links and raw_index <= len(links):
        await message.channel.send(f"```{formatted}```" + f" \n{links[raw_index-1]}")
        return

    # shouldn't be an accessible path?
    await message.channel.send(f"```{formatted}```\n -# playlist link OOB err. Good job. How??")





async def get_all_clips(message: cinAPI.APIMessage):
    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None:
        return

    metadata = data[0]
    videos = data[1:]
    url = metadata.get("url")
    links = get_links(url)

    if not await check_with_err(True and videos, "No clips found.", message): return

    blocks = []
    total_runtime = 0

    for raw_index, clips in enumerate(videos, start=1):
        if not isinstance(clips, dict): continue

        runtime = 0
        clip_lines = []

        # Add part info header
        part_info = format_part_info(data, raw_index)
        clip_lines.append(part_info)

        # Add link if available
        link_text = links[raw_index-1] if raw_index <= len(links) else "unavailable"
        clip_lines.append(f"Video URL: {link_text}")

        # Process clips
        for timestamp, duration in clips.items():
            clip_lines.append(f"    {timestamp}: {duration}s")
            runtime += duration

        total_runtime += runtime
        clip_block = f"Runtime: {format_seconds(runtime)}:\n" + "\n".join(clip_lines)
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

async def set_clip_file(message: cinAPI.APIMessage):
    return await set_clip_fileW(message, None)

async def set_clip_fileW(message: cinAPI.APIMessage, words = None):
    global clip_file_names
    global lastVideoRawIndex

    if words is None:
        words = (message.content.split())
    if len(words) < 2:  # ---------------------------------------------------------------------------------- infer filename from channel name if not supplied --- #
        words = ["!>setclipfile", f"targets_{message.channel.name}.json".replace("-", "_")]

    filename = words[1]
    guild_id = message.guild.id
    cache_dir = os.path.join(".", "cache", "tatoclip", str(guild_id))
    cinIO.ensureDirs([cache_dir])
    filepath = os.path.join(cache_dir, filename)

    if os.path.exists(filepath):  # ---------------------------------------------------------------------------------------------- case file exists, use it --- #
        clip_file_names[message.channel.name] = filepath

        data = load_clip_file(filepath)
        if data is None: return False

        valid, msg = validate_project_file(data)
        if not await check_with_err(valid, f"Warning: Invalid project file structure: {msg}", message): return False

        await message.channel.send(f"Loading clip configuration from {filepath}.")
        return True

    # Search for a close match within the cache directory
    json_files = [f for f in os.listdir(cache_dir) if f.endswith('.json')]
    closest_match = difflib.get_close_matches(f"targets_{filename}", json_files, n=1, cutoff=0.90)

    if closest_match:  # ------------------------------------------------------------------------------------------- case fuzzy match for file exists, use it --- #
        filename = closest_match[0]
        filepath = os.path.join(cache_dir, filename)

        clip_file_names[message.channel.name] = filepath
        data = load_clip_file(filepath)
        if data is None: return False

        valid, msg = validate_project_file(data)
        await check_with_err(valid, f"Warning: Invalid project file structure in matched file (might just be missing url): {msg}")

        await message.channel.send(f"Found a close match for the alias: {filename}")
        lastVideoRawIndex = len(data)
        return True

    # ------------------------------------------------------------------------------------------- case no matching file found, create new file --- #
    url = words[2] if len(words) > 2 else ""

    # Create v1 structure
    data = [
        {
            "prefix": "Part ",
            "version": 1,
            "name": filename.replace("targets_", "").replace(".json", ""),
            "url": ""
        }
    ]

    if url:
        links = get_links(url)
        if not await check_with_err(True and links, f"Failed to fetch playlist for {url}", message): return False

        data[0]["url"] = url

        # Add empty clip entries
        while len(data) < len(links) + 1:
            data.append({})
        await message.channel.send(f"New clip configuration created for {url}.")
    else:
        await message.channel.send(f"New empty clip configuration created. Add a URL later with !>seturl.")

    # Save the new project file in the cache directory
    save_json_to_filepath(data, filepath)

    clip_file_names[message.channel.name] = filepath
    await message.channel.send(f"Clip configuration saved to {filepath}.")
    return True


async def set_url(message: cinAPI.APIMessage):
    global clip_file_names

    if not await check_with_err(message.channel.name in clip_file_names,"No clip file configured. Use !>setclipfile first.", message):
        return False

    words = message.content.split()
    if not await check_with_err(len(words) == 2, "Usage: !>seturl <playlist_url>", message):
        return False

    url = words[1]
    filepath = clip_file_names[message.channel.name]

    try:
        links = get_links(url)
        if not await check_with_err(links,f"Failed to fetch playlist for {url}. Please check the URL and try again.", message):
            return False

        data = load_clip_file(filepath)
        data[0]["url"] = url

        # Add empty clip entries
        while len(data) < len(links) + 1:
            data.append({})

        save_json_to_filepath(data, filepath)

        await message.channel.send(f"Playlist URL updated to {url}")
        return True

    except Exception as e:
        await message.channel.send(f"Error updating URL: {str(e)}")
        return False


async def render_clips(message: cinAPI.APIMessage):
    words = message.content.split()
    if message.channel.name not in clip_file_names and not await set_clip_fileW(message, ["!>setclipfile"]):
        return

    # Ensure valid clip configuration
    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None: 
        return

    # Write data to targets JSON
    try:
        origin = os.path.basename(clip_file_names[message.channel.name])
        backup_path = os.path.join(os.path.dirname(targets_json_path), origin)
        save_json_to_filepath(data, backup_path, True)
    except Exception as e:
        await message.channel.send(f"Error writing backup: {e}")
        return

    # Generate build command
    build_script = "build_from.sh"
    command = [f"./{build_script}", origin]
    
    try:
        script_directory = os.path.dirname(tatoclip_py_path)
        full_command = f"cd '{script_directory}' && {' '.join(command)}"
        
        await message.channel.send(f"Run this command to build:\n```bash\n{full_command}\n```")
        
    except Exception as e:
        await message.channel.send(f"Error generating build command: {e}")





async def set_offset(message: cinAPI.APIMessage):
    global clip_file_names
    words = message.content.split()
    if not await check_with_err(len(words) == 3, "Usage: !>setoffset <part_number> <offset_value>", message): return

    try:
        part_number = int(words[1])
        offset_value = int(words[2])
    except ValueError:
        await message.channel.send("Both part_number and offset_value must be integers")
        return

    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None: return

    data = update_offset(data, part_number, offset_value)
    save_json_to_filepath(data, clip_file_names[message.channel.name], False)
    await message.channel.send(f"Offset for part {part_number} set to {offset_value}")


async def set_alias(message: cinAPI.APIMessage):
    global clip_file_names
    words = message.content.split()
    if not await check_with_err(len(words) >= 2, "Usage: !>setalias <index> <alias> (or none to remove)", message): return

    try:
        effective_index = int(words[1])
        alias = " ".join(words[2:]) if len(words) > 2 else None
    except ValueError:
        await message.channel.send("Index must be an integer")
        return

    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None: return

    raw_index = get_raw_index(data, effective_index)
    data = update_alias(data, raw_index, alias)
    save_json_to_filepath(data, clip_file_names[message.channel.name], False)

    if alias:
        await message.channel.send(f"Alias for index {effective_index} set to '{alias}'")
    else:
        await message.channel.send(f"Alias for index {effective_index} removed")


async def set_metadata(message: cinAPI.APIMessage):
    global clip_file_names
    """!>setmetadata <key> <value> - Update metadata fields (case-insensitive)"""
    words = message.content.split()
    if len(words) < 3:
        await message.channel.send("Usage: !>setmetadata <key> <value>\n"
                                   "Available keys: name, prefix, url, version")
        return

    data = await ensure_clip_file_and_load(message, await get_file_path_from_message(message))
    if data is None:
        return

    metadata = data[0]
    key = words[1].lower()  # Normalize to lowercase
    value = " ".join(words[2:])  # Join remaining words as value

    # List of allowed mutable metadata fields (excluding structural ones)
    allowed_fields = {'name', 'prefix', 'url', 'version'}

    if key not in allowed_fields:
        await message.channel.send(f"Invalid key. Allowed keys: {', '.join(sorted(allowed_fields))}")
        return

    # Special handling for version (must be integer)
    if key == 'version':
        try:
            value = int(value)
        except ValueError:
            await message.channel.send("Version must be an integer")
            return

    # Update the field (using original case from metadata if exists)
    original_case_key = next((k for k in metadata.keys() if k.lower() == key), key)
    metadata[original_case_key] = value

    save_json_to_filepath(data, clip_file_names[message.channel.name], False)
    await message.channel.send(f"Metadata updated: {original_case_key} = {value}")

async def show_metadata_command(message: cinAPI.APIMessage):
    return await show_metadata(message, await get_file_path_from_message(message))


# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[bindings]

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
        "setoffset": set_offset,
        "setalias": set_alias,
        "showmetadata": show_metadata_command,
        "setmetadata": set_metadata
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
        "renderclips": "Start rendering. Usage: `!>renderclips [start] [end]`",
        "setoffset": "Set offset for part numbers. Usage: `!>setoffset <part_number> <offset_value>`\n"
                     "Example: `!>setoffset 9 1` means part 9 is actually index 10 in playlist",
        "setalias": "Set alias for an index. Usage: `!>setalias <index> <alias>`\n"
                    "Example: `!>setalias 9 8.1` lets you use '8.1' instead of 9 in clip commands",
        "showmetadata": "Shows metadata for the project file associated with this channel. Usage: `!>showmetadata`",
        "setmetadata": "Update metadata fields. Use !>showmetadata first. Usage: !>setmetadata <key> <value>"
    }

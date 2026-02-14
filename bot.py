"""
todo:



### 1. Message Reply Wrapper
Add a function to get replied-to messages:
- **`cinAPI.py`**: Add `get_replied_message()` method to `APIMessage` protocol
- **`discord_api.py`**: Implement `get_replied_message()` for `DiscordMessage` class
- Used by bug report plugin to fetch replied messages



### 2. Bug Report Plugin (`cinBugReport.py`)

Create a new plugin module similar to `cinReminders` with:
- `!>bugreport` command that logs entire messages to a separate cache
    - Command behavior:
      - When used with text: `!>bugreport this is the bug` → logs current message
      - When used alone while replying: logs the replied-to message instead

- Cache structure:
```json
{
    "reports": [
        {
            "time": "unix_timestamp",
            "user_id": "user_id",
            "text": "message content after first space",
            "attachments": ["url1", "url2"],
            "client_name": "client_name"
            "status": "string provided buy client",
            "resolved": true/false
        },
        {
            "time": "unix_timestamp",
            ...
        },
        ...
    ]
}

- `!>getbugreports [resolved, unresolved (default), or all]` command that lists all bug reports with the given status
    - Command behavior:
      - Lists all bug reports with the given status (resolved or unresolved).
      - display index, time, text, status, and resolved status

- `!>resolvebugreport <index> <status>` command that marks a bug report as resolved
- `!>unresolvebugreport <index>` command that marks a bug report as unresolved

- `!>getbugreport <index>` command that shows the details of a specific bug report



### 3. Error Handling Improvements
Wrap command/phrase handling to ensure errors reach users:
- **`bot.py`**: Modify `handlePrompts()` to send errors to channel
- Current issue: Some errors fail silently (like 400 Bad Request shown)
- Solution: Add error message sending in exception handlers



### 4: `!>update` command (pull from github if there is a new version)
- hard check against my UUID before anything, as this is a command going in core.
- warn the user, then launch update.sh as a SEPARATE PROCESS, then quit bot:
- update.sh ~
    #!/bin/bash
    cd "$(dirname "$0")"

    echo "Checking for updates..."

    LOCAL=$(git rev-parse HEAD)
    REMOTE=$(git rev-parse origin/main)

    if [ "$LOCAL" = "$REMOTE" ]; then
        echo "Bot is up to date! with origin/main"
    else
        if git pull --no-rebase; then
            echo "Successfully updated!"
        else
            echo "\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!Update failed!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n"
            exit 1
        fi
    fi
    exec python3 bot.py
- still register command as usual, its handler is just.. going to be in core.



### 5: `!>next` command in tatoclip: should function as !>getclips [index of first video with no clip]
- `!>next` command should respond with the URL of the first unprocessed (clipless) video in the playlist.



"""


# bot.py
import cinIO
from cinIO import config

cinnamonVersion = "4.1.3"
description = "Multi-purpose bot that does basically anything I could think of"

debugSettings = {
    "doReminders": True
}

def hardCodedClientImport(): # todo: replace with discovery in api_contexts, similar to how plugins are loaded
    import api_contexts.discord_api
    api_contexts.discord_api.make_client("discord")

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[DEFINITIONS & IMPORTS]

import os.path
import traceback
import time
from datetime import datetime
import asyncio
import inspect
import importlib.util
from pathlib import Path
from typing import Dict, Callable, get_type_hints

import cinAPI
import cinLogging
from cinLogging import printHighlighted, printDefault, printLabelWithInfo, printErr
from cinPalette import *

# todo: log matches to handlers

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[GLOBAL STATE]

commands: Dict[str, Callable] = {}
phrases: Dict[str, Callable] = {}
reactionhandlers: Dict[str, Callable] = {}
loopfunctions = []

playlistURLs = []
initTime = datetime.now().replace(microsecond=0)
initTimeSession = datetime.now().replace(microsecond=0)
Nope = 0

bot_prefix = config["prefix"]
adminGuild = config["adminGuild"]
loopDelay = config["loopDelay"]
bigNumber = config["bigNumber"]

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[VALIDATION]

def validate_handler(fn, expected_args: int, name: str, expected_types: list = None):
    sig = inspect.signature(fn)

    if len(sig.parameters) != expected_args:
        raise TypeError(
            f"{name} has wrong arity: expected {expected_args}, got {len(sig.parameters)}"
        )

    hints = get_type_hints(fn)
    if not hints:
        raise TypeError(
            f"{name} must use explicit generic types (no implicit typing allowed)"
        )

    param_types = list(hints.values())

    if expected_types is not None:
        for i, (actual_type, expected_type) in enumerate(zip(param_types, expected_types)):
            if actual_type != expected_type:
                raise TypeError(
                    f"{name}: parameter {i + 1} must be type {expected_type.__name__}, not {actual_type}"
                )

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[MESSAGE HANDLERS]

async def handlePrompts(message: cinAPI.APIMessage, messageContent: str):
    global phrases

    for phrase, func in phrases.items():
        if phrase == "*":
            try:
                await func(message)
            except Exception as e:
                printErr(f"err in {func}: {e}")

    for phrase, func in phrases.items():
        if phrase in messageContent:
            try:
                await func(message)
            except Exception as e:
                printErr(f"err in {func}: {e}")
            return

async def handleRegularMessage(message: cinAPI.APIMessage):
    global Nope

    if message.author.bot:
        return

    messageContent = message.content

    await cinLogging.tryToLog(message)

    ImAwakeAndNotTalkingToABot = True
    if ImAwakeAndNotTalkingToABot:
        await handlePrompts(message, messageContent)
    else:
        Nope -= 1
        if "arise, cinnamon" in messageContent.lower():
            await message.channel.send("'mornin'!")
            Nope = 0

async def handleCommand(message: cinAPI.APIMessage):
    global commands
    if message.author.bot:
        return

    messageContent = message.content
    words = messageContent.lower().split(" ")

    printLabelWithInfo(time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime()))
    printLabelWithInfo(f"  !!>{message.author.display_name}", messageContent)

    message_command = words[0][len(bot_prefix):]

    if message_command not in commands:
        return

    try:
        await commands[message_command](message)
    except Exception as e:
        printErr(f"Command '{message_command}' failed:")
        printErr(f"  Error: {e}")
        printErr("  Full traceback:")
        printErr(traceback.format_exc())
        await message.channel.send(
            f"❌ Command failed: `{message_command}`\n```{type(e).__name__}: {e}```"
        )

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[STATUS]

lastStatusUpdateTime = 0

async def handleStatusUpdate():
    # printHighlighted(f"handling status update...")
    global lastStatusUpdateTime
    lastStatusUpdateTime = time.time()

    rn = datetime.now()
    thisHour = rn.hour
    thisMinute = rn.minute
    amOrPm = "am"

    if thisHour > 12:
        amOrPm = "pm"
        thisHour -= 12
    if thisHour == 0:
        thisHour = 12
    if thisMinute < 10:
        thisMinute = f"0{thisMinute}"

    clients = cinAPI.get_all_clients()
    for client_name, client in clients.items():
        try:
            await client.set_presence(f'online @{thisHour}:{thisMinute}{amOrPm} PST')
        except Exception as e:
            printErr(f"err in set_presence: {e}")


# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[cinAPI EVENTS]

@cinAPI.register_ready_handler
async def on_ready(client: cinAPI.APIClient):
    global initTimeSession
    initTimeSession = datetime.now().replace(microsecond=0)

    printHighlighted(f"{fiveLines}Login Successful!")
    printLabelWithInfo("  Name", client.user.name)
    printLabelWithInfo("  ID", client.user.id)
    printLabelWithInfo("  Cinnamon version", cinnamonVersion)
    printDefault(fiveLines)

@cinAPI.register_message_handler
async def on_message(message: cinAPI.APIMessage):
    # traceback.print_stack()
    if message.content.startswith(bot_prefix):
        await handleCommand(message)
    else:
        await handleRegularMessage(message)

@cinAPI.register_reaction_handler
async def on_reaction(reaction: cinAPI.APIReaction, user: cinAPI.APIUser):
    if user.bot:
        return
    if not reaction.message.author.bot:
        return

    message = reaction.message
    lowerContent = message.content.lower()
    for phrase, func in reactionhandlers.items():
        if phrase in lowerContent:
            try:
                await func(reaction, user)
            except Exception as e:
                printErr(f"err in {func}: {e}")
            return

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[LOOP]

async def loop():
    # to give clients a bit to start up, skip first cycle
    await asyncio.sleep(loopDelay)

    global lastStatusUpdateTime
    #print("loop started!")
    while True:  # Add a loop to run continuously
        try:
            #print("yo")
            #print(f"loop functions: {loopfunctions}")
            if time.time() - lastStatusUpdateTime > (60 - loopDelay / 2):
                await handleStatusUpdate()

            for func in loopfunctions:
                #print(func)
                try:
                    await func()
                except Exception as e:
                    printErr(f"err in {func}: {e}")
        except Exception as e:
            printErr(f"err in loop: {e}")
            traceback.print_exc()

        await asyncio.sleep(loopDelay)  # Wait before next iteration

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[PLUGINS]

def load_dictionary_component(
        module,
        bind_method_name,
        component_type,
        storage,
        validation_func,
        validation_args,
        plugin_dir
):
    """Load dictionary-based components (commands, phrases, reactions)."""
    if not hasattr(module, bind_method_name):
        return False

    cinLogging.printInBoxP(f"{highlightedColor} found {component_type}...", LARGE_WINDOW)
    attempted = success = 0

    try:
        items = getattr(module, bind_method_name)()
        for name, fn in items.items():
            attempted += 1
            try:
                arg_count, desc, arg_types = validation_args
                desc_formatted = desc.format(name=name)
                validation_func(fn, arg_count, desc_formatted, arg_types)
                storage[name] = fn
                success += 1
            except Exception as e:
                cinLogging.printInBoxP(
                    f"Failed to load {component_type[:-1]} '{name}':\n   {e}",
                    ERROR_BOX
                )

        cinLogging.printLoadStatus(f"  {component_type}", success, attempted)
        return True

    except Exception as e:
        cinLogging.printInBoxP(
            f"{errorColor}Error in {bind_method_name}() for plugin {plugin_dir}:\n   {e}",
            ERROR_BOX
        )
        return False

def load_plugins():
    global commands, phrases, reactionhandlers, loopfunctions

    # header
    print(fiveLines)
    cinLogging.printBoxBorderP(HEADER_BOX_BORDER)
    cinLogging.printInBoxP(f"    Loading plugins...", HEADER_BOX)
    cinLogging.printBoxBorderP(HEADER_BOX_BORDER)

    plugins_dir = Path("./plugins")
    for plugin_dir in plugins_dir.iterdir():
        if not plugin_dir.is_dir():
            continue

        print()
        cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)
        cinLogging.printInBoxP(f" plugin: {plugin_dir.name}", LARGE_WINDOW_HEADER)
        cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)

        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            printErr(f"no __init__ in plugin {plugin_dir}")
            cinLogging.printBoxBorderP(LARGE_WINDOW)
            continue

        module_name = f"plugins.{plugin_dir.name}"
        spec = importlib.util.spec_from_file_location(module_name, init_file)
        if spec is None:
            printErr(f"Failed to create spec for plugin {plugin_dir}")
            cinLogging.printBoxBorderP(LARGE_WINDOW)
            continue

        try:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore
        except Exception as e:
            printErr(f"Failed to import plugin {plugin_dir}: {e}")
            cinLogging.printBoxBorderP(LARGE_WINDOW)
            continue

        # -------------------- Commands --------------------
        if hasattr(module, "bind_commands"):
            load_dictionary_component(
                module, "bind_commands", "commands", commands,
                validate_handler, (1, "command '{name}'", [cinAPI.APIMessage]), plugin_dir
            )

        # -------------------- Phrases --------------------
        if hasattr(module, "bind_phrases"):
            load_dictionary_component(
                module, "bind_phrases", "phrases", phrases,
                validate_handler, (1, "phrase '{name}'", [cinAPI.APIMessage]), plugin_dir
            )

        # -------------------- Reactions --------------------
        if hasattr(module, "bind_reactions"):
            load_dictionary_component(
                module, "bind_reactions", "reactions", reactionhandlers,
                validate_handler, (2, "reaction '{name}'", [cinAPI.APIReaction, cinAPI.APIUser]), plugin_dir
            )

        # -------------------- Loop --------------------
        if hasattr(module, "bind_loop"):
            cinLogging.printInBoxP(f"{highlightedColor} found loops...", LARGE_WINDOW)
            attempted = success = 1
            try:
                loopy = module.bind_loop()
                try:
                    validate_handler(loopy, 0, "loop function")
                    loopfunctions.append(loopy)
                except Exception as e:
                    success = 0
                    cinLogging.printInBoxP(f"Failed to load loop function:\n   {e}", ERROR_BOX)
                cinLogging.printLoadStatus("  loop function", success, attempted)
            except Exception as e:
                cinLogging.printInBoxP(f"Error in bind_loop() for plugin {plugin_dir}:\n   {e}", ERROR_BOX)

        # -------------------- Help --------------------
        if hasattr(module, "bind_help"):
            cinLogging.printInBoxP(f"{highlightedColor} found help...", LARGE_WINDOW)
            attempted = success = 0
            try:
                entries = module.bind_help()
                for cmd, text in entries.items():
                    attempted += 1
                    cinIO.help_entries[cmd] = {
                        "help": text,
                        "plugin": plugin_dir.name
                    }
                    success += 1
                cinLogging.printLoadStatus("  help entries", success, attempted)
            except Exception as e:
                cinLogging.printInBoxP(f"Error in bind_help() for plugin {plugin_dir}:\n   {e}", ERROR_BOX)

        cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)

async def main():
    os.system("color")
    cinLogging.printBoxBorder(0, 130, debugColor)
    print("      bot starting...")
    load_plugins()
    print("      loop started!")
    print(f"      loop delay: {loopDelay} seconds")

    # box parameters
    boxIndentation = 3
    indentation = 3
    boxWidth = 120
    boxWidthMagic = boxWidth + 14

    # header
    print(fiveLines)
    cinLogging.printBoxBorderP(HEADER_BOX_BORDER)
    cinLogging.printInBoxP(f"    Loading clients...", HEADER_BOX)
    cinLogging.printBoxBorderP(HEADER_BOX_BORDER)

    # Client loading box
    print()
    cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)
    cinLogging.printInBoxP(f" Initializing clients...", LARGE_WINDOW_HEADER)
    cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)

    hardCodedClientImport()

    # Get all registered clients
    clients = cinAPI.get_all_clients()

    # Start all clients concurrently
    tasks = []
    for client_name, client in clients.items():
        cinLogging.printInBoxP(f"Starting client: {client_name}", LARGE_WINDOW)
        task = asyncio.create_task(client.start_client())
        tasks.append(task)
    cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)
    print(fiveLines)
    cinLogging.printBoxBorderP(LARGE_WINDOW_BORDER)
    print()

    # wait for all tasks and loop
    print(f"starting loop every {loopDelay} seconds, {len(loopfunctions)} loop functions: {loopfunctions}")
    # loop loop every loopDelay seconds
    loop_task = asyncio.create_task(loop(), name="loop_task")
    print(loop_task)
    tasks.append(loop_task)

    await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    asyncio.run(main())
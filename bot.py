import cinIO

print("bot starting...")
cinnamonVersion = "4.0.0"
description = "Multi-purpose bot that does basically anything I could think of"

# changelog in README.txt

debugSettings = {  # todo: what the FUCK is this doing in code
    "doReminders": True
}

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[DEFINITIONS & IMPORTS]

import platform
import sys
import os
import os.path

from logging import warning
import traceback

import time
from datetime import datetime

import asyncio
import discord
import discord.ext
from discord.ext import tasks

import cinLogging  # logging import changed to only import warning to prevent confusion here
from cinLogging import printHighlighted, printDefault, printLabelWithInfo, printErr, printDebug
from cinShared import *
from cinIO import config, token, userData, getOrCreateUserData
from cinPalette import *
#from cinYoinkytModule import setclipfile, clip, getClips, getAllClips, renderClips

import importlib.util
from pathlib import Path
from typing import Dict, Callable

os.system("color")

commands: Dict[str, Callable] = {}
phrases: Dict[str, Callable] = {}
reactionhandlers: Dict[str, Callable] = {}
help_strings: Dict[str, str] = {}
loopfunctions = []

client = discord.Client(intents=discord.Intents.all(), max_messages=100)

playlistURLs = []
initTime = datetime.now().replace(microsecond=0)
initTimeSession = datetime.now().replace(microsecond=0)
Nope = 0

bot_prefix = config["prefix"]
adminGuild = config["adminGuild"]
loopDelay = config["loopDelay"]
bigNumber = config["bigNumber"]

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[MESSAGE HANDLERS]

async def handlePrompts(message, messageContent):
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


async def handleRegularMessage(message: discord.message):
    global Nope
    messageContent = message.content

    await cinLogging.tryToLog(message)
    ImAwakeAndNotTalkingToABot = Nope <= 0 and not message.author.bot

    if ImAwakeAndNotTalkingToABot:
        await handlePrompts(message, messageContent)
    else:
        # sleepy prompts
        Nope -= 1
        if "arise, cinnamon" in messageContent.lower():
            await message.channel.send("'mornin'!")
            Nope = 0

async def handleCommand(message):
    global commands
    print(commands)
    messageContent = message.content
    words = messageContent.lower().split(" ")

    printLabelWithInfo(time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime()))
    printLabelWithInfo(f"  !!>{message.author.display_name}", messageContent)

    message_command = words[0][len(bot_prefix):]

    print(f"'{message_command}'")

    if not message_command in commands.keys():
        print(f"{message_command} not in commands!")
        return

    for cmd, func in commands.items():
        if cmd == message_command:
            try:
                await func(message)
            except Exception as e:
                printErr(f"err in {func}: {e}")
            return

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[STATUS]

lastStatusUpdateTime = 0
async def handleStatusUpdate():
    global lastStatusUpdateTime
    lastStatusUpdateTime = time.time()

    # every minute, update status
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
        thisMinute = "".join(["0", str(thisMinute)])

    printHighlighted(f"status updated at {thisHour}:{thisMinute}{amOrPm}")
    await client.change_presence(activity=discord.Game(f'online @{thisHour}:{thisMinute}{amOrPm} PST'))

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[DISCORD EVENTS]

@client.event
async def on_ready():
    global initTimeSession
    initTimeSession = datetime.now().replace(microsecond=0)

    printHighlighted(f"{fiveLines}Login Successful!")
    printLabelWithInfo("  Name", client.user.name)
    printLabelWithInfo("  ID", client.user.id)
    printLabelWithInfo("  Discord.py version", discord.__version__)
    printLabelWithInfo("  Cinnamon version", cinnamonVersion)
    printDefault(fiveLines)

    try:
        nonDiscordLoop.start()
    except asyncio.CancelledError:
        printErr("Non-Discord loop is already running.")
    except Exception as err:
        printErr(repr(err))
        printErr(traceback.format_exc())


@client.event
async def on_message(message):
    if message.content.startswith(bot_prefix):
        await handleCommand(message)
    else:
        await handleRegularMessage(message)


@client.event
async def on_reaction_add(reaction, user):
    global reactionhandlers
    if user.bot:
        return
    if not reaction.message.author.bot:
        return
    reactedMsgContent = reaction.message.content.lower()
    #print(reactedMsgContent)
    for phrase, func in reactionhandlers.items():
        #print(phrase)
        if phrase in reactedMsgContent:
            #print("YOOO")
            try:
                await func(reaction, user)
            except Exception as e:
                printErr(f"err in {func}: {e}")
            return


@tasks.loop(seconds=loopDelay)
async def nonDiscordLoop():
    global debugSettings
    global lastStatusUpdateTime
    global loopfunctions

    if time.time() - lastStatusUpdateTime > (60 - loopDelay / 2): await handleStatusUpdate()

    for func in loopfunctions:
        try:
            await func()
        except Exception as e:
            printErr(f"err in {func}: {e}")


def load_plugins():
    global commands, phrases, reactionhandlers, loopfunctions
    printHighlighted(f"{fiveLines}Loading plugins...")
    plugins_dir = Path("./plugins")

    # Iterate through all directories in the plugins folder
    for plugin_dir in plugins_dir.iterdir():
        printLabelWithInfo("  plugin", plugin_dir)
        if not plugin_dir.is_dir():
            continue

        # Check if the directory has an __init__.py file
        init_file = plugin_dir / "__init__.py"
        if not init_file.exists():
            printErr(f"no __init__ in plugin {plugin_dir}")
            continue

        # Create the module spec and import it
        module_name = f"plugins.{plugin_dir.name}"
        spec = importlib.util.spec_from_file_location(module_name, init_file)
        if spec is None:
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore

        # Call the bind functions if they exist
        if hasattr(module, "bind_commands"):
            cmd_dict = module.bind_commands()
            if isinstance(cmd_dict, dict):
                commands.update(cmd_dict)
                printLabelWithInfo("    commands", cmd_dict)
            else:
                printErr(f"bind_commands() in plugin {plugin_dir} returned invalid data? {cmd_dict}")

        if hasattr(module, "bind_phrases"):
            phrase_dict = module.bind_phrases()
            if isinstance(phrase_dict, dict):
                phrases.update(phrase_dict)
                printLabelWithInfo("    prompts", phrase_dict)
            else:
                printErr(f"bind_phrases() in plugin {plugin_dir} returned invalid data? {phrase_dict}")

        if hasattr(module, "bind_reactions"):
            reactionhandler = module.bind_reactions()
            if isinstance(reactionhandler, dict):
                reactionhandlers.update(reactionhandler)
                printLabelWithInfo("    reaction handlers:", reactionhandler)
            else:
                printErr(f"bind_reactions() in plugin {plugin_dir} returned invalid data? {phrase_dict}")

        if hasattr(module, "bind_help"):
            plugin_help = module.bind_help()
            if isinstance(plugin_help, dict):
                help_strings.update(plugin_help)
            else:
                printErr(f"bind_help() in plugin {plugin_dir} returned invalid data? {plugin_help}")

        if hasattr(module, "bind_loop"):
            loopy = module.bind_loop()
            loopfunctions.append(loopy)
            printLabelWithInfo("    loop function:", loopy)

load_plugins()

client.run(token)
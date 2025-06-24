
# tokenizer, validateAgainstWhitelist and secureEval functions in this module written by https://github.com/Koenig-Heinrich-der-4te

import math
# this floods the namespace, I know, but this is intentional to allow expressions in /solve to not explicitly specify math.whatever()
from math import *

import discord

from cinShared import *
from cinIO import config
from cinLogging import printHighlighted
from cinPalette import *
from cinShared import *

badParenthesisRegex = r"\(([ \t\n])*(-)*([ \t\n\d])*\)"  # catches parenthesis that are empty, or contain only a number, including negative numbers

adminGuild = config["adminGuild"]
solveBlacklist = config["solveBlacklist"]
solveWhitelist = config["solveWhitelist"]
secureSolve = config["secureSolve"]

if secureSolve:
    printHighlighted(f"         {highlightedColor}using whitelist for /solve")
else:
    printHighlighted(f"         {highlightedColor}using (insecure) blacklist for /solve (ADMIN GUILD ONLY)")


def formatEvalResult(value):
    return f"{value:,}"


tokenizer = re.compile("[\.,\(\)\*\/\+\-% ]|\d+|\w+")


def validateAgainstWhitelist(expression):
    i = 0
    while i < len(expression):
        match = tokenizer.match(expression, i)
        if match is None:
            return False
        token = match.group()
        if token[0].isalpha() and token not in solveWhitelist:
            return False
        i = match.end()
    return True


def secureEval(expression):
    if validateAgainstWhitelist(expression):
        try:
            return formatEvalResult(eval(expression, globals(), vars(math)))
        except Exception:
            return "failedToResolveEval"
    else:
        return "Bad Math expression"


def validateAgainstBlacklist(expression):
    # check if eval contains bad words OR parenthesis with only whitespace
    containsBadParenthesis = re.findall(badParenthesisRegex, expression)
    containsBadWords = containsAny(expression, solveBlacklist)
    containsBadWords = containsBadWords or containsBadParenthesis
    return not containsBadWords


def insecureEval(expression):
    if validateAgainstBlacklist(expression):
        try:
            evalResult = formatEvalResult(eval(expression))
        except Exception:
            evalResult = "failedToResolveEval"
    else:
        evalResult = "fuck you. (noticed bad keywords in eval)"
    return evalResult


async def solve_command(message: discord.Message):
    messageContent = message.content
    # default offsets are for /solve
    myCharOffset = [7, 0]
    if "cinnamon, eval(" in messageContent.lower():  # todo: get position of open parenthesis? lmao
        myCharOffset = [15, 1]
    elif "!>" in messageContent:  # todo: get position after space after solve? lmao
        myCharOffset = [8, 0]

    textToEval = messageContent[myCharOffset[0]:len(messageContent) - myCharOffset[1]]

    if secureSolve:
        response = secureEval(textToEval)
    else:
        if adminGuild == message.guild.id:
            response = insecureEval(textToEval)
        else:
            response = "guildIsNotAdminGuildMsg"

    await message.channel.send(response)


def bind_phrases():
    return {
        "cinnamon, eval(": solve_command,
        "/solve": solve_command,
    }

def bind_commands():
    return {
        "solve": solve_command
    }

def bind_help():
    return {
        "solve": "Occasionally convenient calculator. Usage:\n"
                 "`/solve <expression>` or `!>solve <expression>`\n\n"
                 "- Supports standard math operations (+-*/%), sin, cos, sqrt, pow, etc.)\n"
                 "Examples:\n"
                 "`/solve 2*(3+5)` → `16`\n"
                 "`/solve sqrt(2**8)` → `16`\n"
                 "`/solve sin(pi/2)` → `1.0`\n\n"
                 "alias: cinnamon, eval(<expression>)",
    }
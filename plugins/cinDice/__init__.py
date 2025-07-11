import math
import re
import random
import discord

# todo: re-implement modifiers

def getRollsAndDice(command):
    # extract rolls from command
    rolls = re.findall(r'\d+d', command)
    if len(rolls) == 0:
        rolls = "1"
    else:
        rolls = rolls[0]
        rolls = rolls[0:-1]

    # extract die from command
    die = re.findall(r'd\d+', command)
    if len(die) == 0:
        die = "20"
    else:
        die = die[0]
        die = die[1:]

    # rolled 0D20 or 1D0 or something like that
    if int(rolls) < 1:
        rolls = "1"
    if int(die) < 1:
        die = "1"

    # return [rolls, die] as int[]
    return [int(rolls), int(die)]


def roll(command: str):
    advantage = 0
    results = []

    rollsAndDice = getRollsAndDice(command)
    rolls = rollsAndDice[0]
    die = rollsAndDice[1]

    response = "Rolling "+str(rolls)+" D"+str(die)+"(s)...\n"

    if "adv" in command:
        response = response + "rolling with adv: \n"
        advantage = 1
    elif "dis" in command:
        advantage = -1
        response = response + "rolling with disadv: \n"

    # for each die,
    for i in range(rolls):
        # if there are multiple dice, add roll number to response
        if rolls > 1:
            response = response + "roll " + str(i+1) + ": "

        # generate 2 random rolls,
        rng = [math.floor(random.random()*die),
               math.floor(random.random()*die)]
        if die != 10:
            # add 1 to non-d10 rolls,
            rng = [rng[0]+1, rng[1]+1]

        # then, if in adv or disadv state, add both rolls to response if in an adv/disadv state, and choose higher or lower rng value,
        if advantage != 0:
            response = response + str(rng) + " - "
            if advantage == 1:
                rng = [max(rng)]
            elif advantage == -1:
                rng = [min(rng)]

        # then, add chosen die to results & response
        results.append(rng[0])
        response = response + str(rng[0]) + "\n"

    # after rolling, if multiple dice were rolled, add some math to response, with results
    if rolls > 1:
        response = response + "average: " + str(sum(results) / len(results))
        response = response + "\nmin: " + str(min(results))
        response = response + "\nmax: " + str(max(results))

    return response

async def rollWrapper(message: discord.message):
    startOfRollText = message.content.lower().find("roll ")
    rollCommandText = message.content.lower()[startOfRollText:len(message.content.lower())]

    response = roll(rollCommandText)
    await message.channel.send(response)

# Binding functions
def bind_phrases():
    return {
        "/roll": rollWrapper
    }

def bind_commands():
    return {
        "roll": rollWrapper
    }

def bind_help():
    return {
        "roll": "Rolls dice with various options. Usage: \n"
        "`/roll XdY` - Rolls X Y-sided dice (e.g. `/roll 3d6` rolls three 6-sided dice)\n"
        "`/roll dY` - Rolls one Y-sided die (e.g. `/roll d20` rolls one 20-sided die)\n"
        "`/roll XdY adv` - Rolls with advantage (rolls twice, takes higher)\n"
        "`/roll XdY dis` - Rolls with disadvantage (rolls twice, takes lower)\n"
        "\n"
        "Notes:\n"
        "- Default is 1d20 if no parameters given\n"
        "- For multiple dice, shows average, min, and max results\n"
        "- D10 rolls are mapped to 0-9, not 1-10\n"
    }
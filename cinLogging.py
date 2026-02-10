# cinLogging.py
import os
import re
import time
from typing import List

from cinAPI import APIMessage
from cinIO import defaultLoggingHtml
from cinPalette import *

regularTextHTMLHeader = '<p class="text"'
indentedLoggingCSSHeader = '<p class="indentedText"'

urlRegex = 'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
def getURLs(string):
    return re.findall(urlRegex, string)

def getLogFilePath(message: APIMessage) -> str:
    # Use guild name if available, otherwise use "DM"
    guild_name = "DM"
    if message.guild:
        guild_name = str(message.guild.name)


    # Use channel ID for uniqueness in DMs
    channel_identifier = str(message.channel.name) if message.guild else f"dm_{message.channel.name}"

    logFolderPath = os.path.join(os.path.dirname(__file__), f"logs/{guild_name}")
    logFilePath = os.path.join(logFolderPath, f"{channel_identifier}.html")

    os.makedirs(logFolderPath, exist_ok=True)

    if not os.path.isfile(logFilePath):
        with open(logFilePath, "w+") as logFile:
            logFile.writelines(defaultLoggingHtml)
    return logFilePath

def getAttachments(message: APIMessage) -> List[str]: # todo: deduplicate links, and move to cinAPI
    attachments = []

    # Handle attachments from message.attachments
    for attachment in message.attachments:
        if hasattr(attachment, 'url') and attachment.url:
            attachments.append(attachment.url)

    # Handle embeds
    for embed in message.embeds:
        if hasattr(embed, 'url') and embed.url:
            attachments.append(embed.url)

    # Extract URLs from message content
    content_urls = getURLs(message.content)
    attachments.extend(content_urls)

    return attachments

# formatting

def _step_escape(char: str, in_escape: bool) -> tuple[bool, bool]:
    """
    Process a single character for ANSI escapes.
    Returns (is_visible, new_in_escape).
    """
    if in_escape:
        return False, char != 'm'

    if char == '\033':
        return False, True

    return True, False


def _process_escape_sequences(chars: list, start_index: int = 0, track_last_space: bool = False) -> tuple[int, bool, int]:
    visible_count = 0
    in_escape = False
    last_space = -1

    for i in range(start_index, len(chars)):
        char = chars[i]
        is_visible, in_escape = _step_escape(char, in_escape)

        if not is_visible:
            continue

        if track_last_space and char == ' ':
            last_space = i

        visible_count += 1

    return visible_count, in_escape, last_space



def _get_visible_width(text: str) -> int:
    """Calculate the visible width of text, ignoring ANSI escape sequences."""
    visible_count, _, _ = _process_escape_sequences(list(text))
    return visible_count

def printInBoxP(text: str, params: BoxParams):
    return printInBox(
        text=text,
        boxColor=params.box_color,
        boxIndentation=params.box_indentation,
        indentation=params.indentation,
        width=params.width,
        color=params.text_color,
        altFirstBorder=params.alt_first_border,
    )

def printInBox(text: str, boxColor: str, boxIndentation: int = 1, indentation: int = 1, width: int = 40,
               color: str = defaultColor, altFirstBorder: bool = False):
    if text is None:
        raise ValueError("Text cannot be None")
    if width < 1:
        raise ValueError("Width must be positive")
    if boxIndentation < 0 or indentation < 0:
        raise ValueError("Indentation values must be non-negative")

    # constants
    BORDER_ALT = "| |"
    BORDER_NORMAL = "||"
    firstBorder = BORDER_ALT if altFirstBorder else BORDER_NORMAL
    box_indent = indent * boxIndentation
    inner_indent = indent * indentation

    # cleanup
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # setup
    usable_width = width - len(inner_indent)

    current_line = []
    lines = []
    current_pos = 0
    text_length = len(text)

    in_escape = False
    visible_count = 0

    while current_pos < text_length:
        char = text[current_pos]
        if char == '\n': # immediately break on newline
            line = ''.join(current_line)
            lines.append(line)
            current_line = []
            visible_count = 0
            current_pos += 1
            continue
        # not on newline

        # escape sequences (very redundant redundancy is redundant)
        if in_escape:
            current_line.append(char)
            if char == 'm':
                in_escape = False
            current_pos += 1
            continue
        if char == '\033':
            in_escape = True
            current_line.append(char)
            current_pos += 1
            continue
        # not on newline or in escape sequence: count char as visible
        current_line.append(char)
        visible_count += 1

        if visible_count >= usable_width:
            # visible width exceeded, break line
            # look for last space in visible characters using helper
            visible_chars, _, last_space = _process_escape_sequences(current_line, track_last_space=True)

            # if we found a space within usable width, split the line at that point
            if last_space != -1:
                line = ''.join(current_line[:last_space])
                lines.append(line)
                remaining = current_line[last_space + 1:]
                current_line = []

                # recalculate visible count for remaining line using helper
                visible_count, _ = _process_escape_sequences(remaining)[:2]
                current_line = remaining

                # Adjust position to account for characters we're keeping
                current_pos = current_pos - (len(current_line) - visible_count)
            else:  # otherwise, ya yeet
                line = ''.join(current_line)
                lines.append(line)
                current_line = []
                visible_count = 0
        # step
        current_pos += 1

    if current_line:
        lines.append(''.join(current_line))

    # Print with proper padding
    for line in lines:
        visible_width = _get_visible_width(line)
        padding_needed = usable_width - visible_width
        if padding_needed > 0:
            padding = " " * padding_needed
            print(
                f"{box_indent}{boxColor}{firstBorder}{inner_indent}{color}{line}{padding}{indent * 2}{boxColor}|{clearFormatting}")
        else:
            print(
                f"{box_indent}{boxColor}{firstBorder}{inner_indent}{color}{line}{indent * 2}{boxColor}|{clearFormatting}")

def printBoxBorder(indentation: int = 1, width: int = 40, boxColor: str = highlightedColor):
    print(f"{indent*indentation}{boxColor}(-){'=' * width}=){clearFormatting}")

def printBoxBorderP(params: BoxParams = LARGE_WINDOW):
    print(f"{indent*params.box_indentation}{params.box_color}(-){'=' * params.width}=){clearFormatting}")

def printLoadStatus(label: str, success: int, attempted: int, indentation: int = 1, width: int = 40):
    """
    Green: all success
    Orange: partial success
    Red: all failed
    """
    if attempted == 0:
        return  # nothing attempted, don't print

    if success == attempted:
        color = debugColor          # green
    elif success == 0:
        color = errorColor          # red
    else:
        color = highlightedColor    # orange / cyan-ish

    #print(f"{'    ' * indentation}{defaultColor}|{label}: {color}{success}/{attempted}{defaultColor} |{clearFormatting}")
    printInBoxP(f"    {label}: {color}{success}/{attempted}{defaultColor}", LOAD_STATUS)

lastMessageChannelID = 0


def printCinnamonMessage(message: APIMessage):
    global lastMessageChannelID
    shouldLabel = lastMessageChannelID != message.channel.id

    try:
        # Handle cases where guild might not exist (DMs)
        guild_info = f"{message.guild.id} - {message.guild.name}:            " if message.guild and hasattr(
            message.guild, 'id') else ""
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "Unknown"

        if shouldLabel:
            if lastMessageChannelID != 0:
                printBoxBorderP(LARGE_WINDOW_BORDER)
                print()
            printBoxBorderP(LARGE_WINDOW_BORDER)
            printInBoxP(f"{labelColor}{guild_info}{channel_name}", LARGE_WINDOW_HEADER)
            printBoxBorderP(LARGE_WINDOW_BORDER)
        printInBoxP(f"{debugColor}    >>>CINNAMON \n{message.content}", LARGE_WINDOW)
        lastMessageChannelID = message.channel.id
    except Exception as e:
        print(f'    {labelColor}Cinnamon (error: {e}): {message.content}')


def printHumanMessage(message: APIMessage):
    global lastMessageChannelID
    shouldLabel = lastMessageChannelID != message.channel.id

    try:
        # Handle cases where guild might not exist (DMs)
        guild_info = f"{message.guild.id} - {message.guild.name}:            " if message.guild and hasattr(message.guild, 'id') else ""
        channel_name = message.channel.name if hasattr(message.channel, 'name') else "Unknown"

        if shouldLabel:
            if lastMessageChannelID != 0:
                printBoxBorderP(LARGE_WINDOW_BORDER)
                print()
            printBoxBorderP(LARGE_WINDOW_BORDER)
            printInBoxP(f"{labelColor}{guild_info}{channel_name}", LARGE_WINDOW_HEADER)
            printBoxBorderP(LARGE_WINDOW_BORDER)
        printInBoxP(f"{highlightedColor}    {message.author.display_name}:{defaultColor} \n{message.content}", LARGE_WINDOW)
        lastMessageChannelID = message.channel.id
    except Exception as e:
        print(f'    {labelColor}{message.author.display_name} (error: {e}): {message.content}')

def logCinnamonMessage(message: APIMessage):
    logFilePath = getLogFilePath(message)
    if logFilePath:
        now = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
        with open(logFilePath, 'a', encoding='utf-8') as logFile:
            logFile.write(
                f'{regularTextHTMLHeader} style="background-color: {message.author.color}">{now}<br /><br />CINNAMON (bot): {message.content}<br /></p>')


def logDiscordMessage(message: APIMessage):
    logFilePath = getLogFilePath(message)
    if logFilePath:
        now = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
        with open(logFilePath, 'a', encoding='utf-8') as logFile:
            logFile.write(
                f'{regularTextHTMLHeader} style="background-color: {message.author.color}">{now}<br /><br />{message.author.display_name}: {message.content}<br /></p>')


# ---------- end print/log message of type

async def tryToLog(message: APIMessage):
    if message.author.bot:
        printCinnamonMessage(message)
        logCinnamonMessage(message)
    else:
        printHumanMessage(message)
        logDiscordMessage(message)
        logAttachmentsFromMessage(message)
    printInBoxP(f"{debugColor}                                                                                @" + time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime()), LARGE_WINDOW)



# ----------

def printLabelWithInfo(label, info=None):
    if info:
        info = f"{highlightedColor}{info}"
        print(f"  {labelColor}{label}: {highlightedColor}{info}")
    else:
        print(f"  {labelColor}{label}")


def printHighlighted(text, indentation = 1):
    print(f"{indent*indentation}{highlightedColor}{text}")


def printDefault(text, indentation = 1):
    print(f"{indent*indentation}{defaultColor}{text}")


def printErr(text, indentation = 1):
    print(f"{indent*indentation}{errorColor}{text}")


def printDebug(text, indentation = 1):
    print(f"{indent*indentation}{debugColor}{text}")


def logAttachmentsFromMessage(message: APIMessage):
    attachments = getAttachments(message)
    logFilePath = getLogFilePath(message)

    log_entries = []
    logged_urls = []

    if not attachments or len(attachments) == 0: return

    printInBoxP("attachments:", LARGE_WINDOW)

    for file_url in attachments:
        if file_url and len(file_url) > 3:  # Ensure it's a valid URL
            # Check if attachment ends with a file extension
            if file_url in logged_urls: continue
            logged_urls.append(file_url)

            printInBoxP(f"{highlightedColor}{file_url}", LARGE_WINDOW)

            # Determine if the attached file is an image or not
            if any(ext in file_url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                log_entries.append(
                    f'\n{indentedLoggingCSSHeader} style="background-color: {message.author.color};">'
                    f'<img src="{file_url}" alt="{file_url}" class="embeddedImage" style="max-height: 50%; height: auto;" loading="lazy">'
                    f'</p>'
                )
            else:
                log_entries.append(
                    f'\n<a href="{file_url}" style="background-color: rgba(150, 200, 255, 0.2);">{file_url}</a>'
                )

    if log_entries:
        with open(logFilePath, 'a', encoding='utf-8') as logFile:
            logFile.write(f"\n{' '.join(log_entries)}\n")

import os

from bot import help_strings
async def send_long_message(channel, content):
    """Helper function to send messages that may exceed Discord's limit"""
    if len(content) <= 2000:
        await channel.send(content)
        return

    # Split by lines if possible to avoid breaking mid-line
    lines = content.split('\n')
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > 1900:  # +1 for the newline
            await channel.send(current_chunk)
            current_chunk = line
        else:
            if current_chunk:
                current_chunk += "\n"
            current_chunk += line

    if current_chunk:
        await channel.send(current_chunk)


async def help_command(message):
    words = message.content.lower().split()

    # Build base command list
    formatted_commands = "\n".join([f"• `{cmd}`" for cmd in sorted(help_strings.keys())])
    base_response = f"Available commands:\n{formatted_commands}\n\nType `/help <command>` for more info."

    # Handle different command variations
    if len(words) == 1:
        await send_long_message(message.channel, base_response)
        return

    if len(words) > 2:
        await message.channel.send(
            help_strings["help"]
        )
        return

    # Handle specific command cases
    if words[1] == "all" or words[1] == "dump":
        # Build complete help message
        full_help = []
        for cmd, help_text in sorted(help_strings.items()):
            full_help.append(f"# **{cmd}**\n{help_text}")
        complete_help = "\n\n".join(full_help)

        if words[1] == "dump":
            if not dump_help_to_md(complete_help):
                message.channel.send("Already dumped help this session! It'll just be the same!")

        await send_long_message(message.channel, complete_help)
    elif words[1] in help_strings:
        help_text = help_strings[words[1]]
        await send_long_message(message.channel, help_text)
    else:
        await message.channel.send(f"Unknown command '{words[1]}'. Available options:\n{formatted_commands}\n\nOr use `/help all` to see all help messages.")

has_dumped_help = False


def dump_help_to_md(help_str):
    global has_dumped_help
    if has_dumped_help:
        return False
    has_dumped_help = True

    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    parent_parent_dir = os.path.dirname(os.path.dirname(current_file_dir))

    readme_path = os.path.join(parent_parent_dir, 'README.md')
    help_content = f"GENERATED HELP PAGE FROM PLUGINS:\n\n{help_str}".replace("# ", "### ").replace("\n", "\\\n")

    help_file_path = os.path.join(parent_parent_dir, 'help.md')
    try:
        with open(help_file_path, 'w', encoding='utf-8') as f:
            f.write(help_content.strip())
    except Exception as e:
        print(f"Failed to create help file: {e}")
        return False

    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            readme_content = f.read()

        # Check if the marker exists in readme.md
        marker_pos = readme_content.find("GENERATED HELP PAGE")
        if marker_pos != -1:
            # Keep content before marker and append new help content
            new_content = readme_content[:marker_pos] + help_content

            # Write updated README
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        else:
            print("couldn't find help page preamble in README.md, ")
        return True
    return False

def bind_commands():
    return {
        "help": help_command
    }

def bind_help():
    return{
        "help":
        "`!>help` - list commands\n"
        "`!>help <command>` - specific help\n"
        "`!>help all` - show all help messages\n"
        "`!>help dump` - dump all help messages to help.md\n"
        "`!>help help` - show this help message"
    }
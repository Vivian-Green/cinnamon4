import os
from bot import help_entries  # Changed from help_strings to help_entries


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

    # Build base command list grouped by plugin
    plugins_commands = {}
    for cmd, entry in help_entries.items():
        plugin_name = entry["plugin"]
        if plugin_name not in plugins_commands:
            plugins_commands[plugin_name] = []
        plugins_commands[plugin_name].append(cmd)

    # Format base response with plugins
    formatted_response = []
    for plugin_name, cmds in sorted(plugins_commands.items()):
        formatted_response.append(f"\n**{plugin_name}:**")
        formatted_response.extend([f"• `{cmd}`" for cmd in sorted(cmds)])

    base_response = "Available commands (grouped by plugin):" + "\n".join(formatted_response)
    base_response += "\n\nType `!>help <command>` for more info. `!>help help` for helpier help"

    # Handle different command variations
    if len(words) == 1:
        await send_long_message(message.channel, base_response)
        return

    if len(words) > 2:
        await message.channel.send(
            help_entries["help"]["help"]  # Updated to use new structure
        )
        return

    # Handle specific command cases
    if words[1] == "all" or words[1] == "dump":
        # Build complete help message organized by plugin
        full_help = []
        current_plugin = None

        # Sort commands by plugin then by command name
        sorted_entries = sorted(help_entries.items(), key=lambda x: (x[1]["plugin"], x[0]))

        for cmd, entry in sorted_entries:
            if entry["plugin"] != current_plugin:
                current_plugin = entry["plugin"]
                full_help.append(f"\n## {current_plugin.upper()} ##")
            full_help.append(f"### {cmd}\n{entry['help']}")

        complete_help = "\n\n".join(full_help)

        if words[1] == "dump":
            if not dump_help_to_md(complete_help):
                await message.channel.send("Already dumped help this session! It'll just be the same!")

        await send_long_message(message.channel, complete_help)
    elif words[1] in help_entries:
        help_text = help_entries[words[1]]["help"]
        await send_long_message(message.channel, help_text)
    else:
        await message.channel.send(
            f"Unknown command '{words[1]}'. {base_response}"
        )


has_dumped_help = False


def dump_help_to_md(help_str):
    global has_dumped_help
    if has_dumped_help:
        return False
    has_dumped_help = True

    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    parent_parent_dir = os.path.dirname(os.path.dirname(current_file_dir))

    readme_path = os.path.join(parent_parent_dir, 'README.md')
    help_content = f"# GENERATED HELP PAGE FROM PLUGINS\n\n{help_str}"

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

        marker_pos = readme_content.find("# GENERATED HELP PAGE")
        if marker_pos != -1:
            new_content = readme_content[:marker_pos] + help_content
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        else:
            print("Couldn't find help page marker in README.md")
        return True
    return False


def bind_commands():
    return {
        "help": help_command
    }


def bind_help():
    return {
        "help":
            "`!>help` - list commands grouped by plugin\n"
            "`!>help <command>` - specific command help\n"
            "`!>help all` - show all help messages organized by plugin\n"
            "`!>help dump` - dump all help messages to help.md\n"
            "`!>help help` - show this help message"
    }
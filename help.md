# GENERATED HELP PAGE FROM PLUGINS


## CINDICE ##

### roll
Rolls dice with various options. Usage: 
`/roll XdY` - Rolls X Y-sided dice (e.g. `/roll 3d6` rolls three 6-sided dice)
`/roll dY` - Rolls one Y-sided die (e.g. `/roll d20` rolls one 20-sided die)
`/roll XdY adv` - Rolls with advantage (rolls twice, takes higher)
`/roll XdY dis` - Rolls with disadvantage (rolls twice, takes lower)

Notes:
- Default is 1d20 if no parameters given
- For multiple dice, shows average, min, and max results
- D10 rolls are mapped to 0-9, not 1-10



## CINREMINDERS ##

### reminder
Set a new reminder with flexible time formats. Usage:
`!>reminder <time> <message>`

Time formats supported:
• Relative: `30m`, `2h15m`, `1d6h`, `3w`, `1y`
• Timestamp: `<t:1625097600>` (Unix timestamp)

Examples:
`!>reminder 45m Check laundry`
`!>reminder 2d4h Check very slow laundry`
`!>reminder <t:1735689600> New Year's Eve!`

### reminders
Manage your active reminders. Usage:
`!>reminders` - Lists all your upcoming reminders

- Shows time remaining, text for each reminder
- React with 🇦, 🇧, 🇨 etc. to delete reminders



## CINSOLVE ##

### solve
Occasionally convenient calculator. Usage:
`/solve <expression>` or `!>solve <expression>`

- Supports standard math operations (+-*/%), sin, cos, sqrt, pow, etc.)
Examples:
`/solve 2*(3+5)` → `16`
`/solve sqrt(2**8)` → `16`
`/solve sin(pi/2)` → `1.0`

alias: cinnamon, eval(<expression>)


## HELP ##

### help
`!>help` - list commands grouped by plugin
`!>help <command>` - specific command help
`!>help all` - show all help messages organized by plugin
`!>help dump` - dump all help messages to help.md
`!>help help` - show this help message


## TATOCLIP_PLUGIN ##

### clip
Add/edit clips. Usage:
`[clip] <index> <timestamp> <duration>`
`[clip] <timestamp> <duration>` (uses last index)
`clip toggle` - Toggle clipping mode
Set duration=0 to delete clip

### getallclips
View all clips. Usage: `!>getallclips`

### getclips
View clips for video. Usage: `!>getclips <index>`

### renderclips
Start rendering. Usage: `!>renderclips [start] [end]`

### setalias
Set alias for an index. Usage: `!>setalias <index> <alias>`
Example: `!>setalias 9 8.1` lets you use '8.1' instead of 9 in clip commands

### setclipfile
Initialize or configure clip settings. Usage:
`!>setclipfile [filename.json] [playlist_url]`

• Creates new config if file doesn't exist
• URL is optional
• Auto-matches similar filenames
• Defaults to `targets_[channelname].json`

### setmetadata
Update metadata fields. Use !>showmetadata first. Usage: !>setmetadata <key> <value>

### setoffset
Set offset for part numbers. Usage: `!>setoffset <part_number> <offset_value>`
Example: `!>setoffset 9 1` means part 9 is actually index 10 in playlist

### seturl
Add/update playlist URL. Usage: `!>seturl <playlist_url>`

### showmetadata
Shows metadata for the project file associated with this channel. Usage: `!>showmetadata`
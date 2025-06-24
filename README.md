# cinnamon-4
discord bot a few friends use, rewritten again again

DO NOT ADD UNTRUSTED USERS TO YOUR ADMIN GUILD. DO NOT SET YOUR ADMIN GUILD TO A SERVER WITH UNTRUSTED USERS. Access to /solve (if secureSolve is off) can cause problems that I do not intend to fix. They're locked behind the admin guild for a reason.


# GENERATED HELP PAGE FROM PLUGINS:\
\
### **clip**\
Add/edit video clips. Usage:\
`[clip] <video index> <timestamp> <duration>` (sets video index)\
`[clip] <timestamp> <duration>` (uses previous video index)\
`clip toggle` - Toggle clipping mode (whether "clip" command is needed)\
\
- Timestamp format: `HH:MM:SS` or `MM:SS`\
- Set duration to 0 to delete a clip\
- autocorrects ; to :\
Examples:\
`clip 3 1:30 15` (index 3 at 1m30s for 15s)\
`2;45 10` (last index at 2m45s for 10s, with clipping mode enabled)\
`clip toggle` (enable/disable clipping mode)\
\
### **getallclips**\
View all clips in playlist with total runtime calculation. Usage:\
`!>getallclips`\
\
\
\
### **getclips**\
View clips for specific video. Usage:\
`!>getclips <index>`\
\
\
\
### **help**\
`!>help` - list commands\
`!>help <command>` - specific help\
`!>help all` - show all help messages\
`!>help dump` - dump all help messages to help.md\
`!>help help` - show this help message\
\
### **reminder**\
Set a new reminder with flexible time formats. Usage:\
`!>reminder <time> <message>`\
\
Time formats supported:\
• Relative: `30m`, `2h15m`, `1d6h`, `3w`, `1y`\
• Timestamp: `<t:1625097600>` (Unix timestamp)\
\
Examples:\
`!>reminder 45m Check laundry`\
`!>reminder 2d4h Check very slow laundry`\
`!>reminder <t:1735689600> New Year's Eve!`\
\
### **reminders**\
Manage your active reminders. Usage:\
`!>reminders` - Lists all your upcoming reminders\
\
- Shows time remaining, text for each reminder\
- React with 🇦, 🇧, 🇨 etc. to delete reminders\
\
\
### **renderclips**\
Start rendering process. Usage:\
`!>renderclips [start_index] [end_index]`\
\
\
\
### **roll**\
Rolls dice with various options. Usage: \
`/roll XdY` - Rolls X Y-sided dice (e.g. `/roll 3d6` rolls three 6-sided dice)\
`/roll dY` - Rolls one Y-sided die (e.g. `/roll d20` rolls one 20-sided die)\
`/roll XdY adv` - Rolls with advantage (rolls twice, takes higher)\
`/roll XdY dis` - Rolls with disadvantage (rolls twice, takes lower)\
\
Notes:\
- Default is 1d20 if no parameters given\
- For multiple dice, shows average, min, and max results\
- D10 rolls are mapped to 0-9, not 1-10\
\
\
### **setclipfile**\
Initialize or configure clip settings. Usage:\
`!>setclipfile [filename.json] [playlist_url]`\
\
• Creates new config if file doesn't exist\
• Auto-matches similar filenames\
• Defaults to `targets_[channelname].json`\
\
Example:\
`!>setclipfile targets_tutorials.json https://youtube.com/playlist?list=...`\
\
### **solve**\
Occasionally convenient calculator. Usage:\
`/solve <expression>` or `!>solve <expression>`\
\
- Supports standard math operations (+-*/%), sin, cos, sqrt, pow, etc.)\
Examples:\
`/solve 2*(3+5)` → `16`\
`/solve sqrt(2**8)` → `16`\
`/solve sin(pi/2)` → `1.0`\
\
alias: cinnamon, eval(<expression>)
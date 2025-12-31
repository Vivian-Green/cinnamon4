# Changes in Cinnamon 4.1.0
## How it's shaped, now that it's been decoupled from discord.py

After watching discord become what it currently is, I've been itching to make my chatbot (not my OS) Cinnamon client-agnostic for probably the better part of a year, and have finally committed to it.. as of a couple weeks ago. I'm happy to say that: I've done it. And broken everything in the process.

## How I've Broken Everything - 4.1 Changes

### 1. cinLogging changes

Since I broke everything and had to keep looking at my disgusting logging: new logging system uses the new `BoxParams` dataclass in `cinPalette.py`:

```python
@dataclass(slots=True, frozen=True)
class BoxParams:
    box_color: str = highlightedColor
    box_indentation: int = 1
    indentation: int = 1
    width: int = 40
    text_color: str = defaultColor
    alt_first_border: bool = False
```

This allows for consistent theming across different logging contexts through predefined boxParams (read: themes) like `LARGE_WINDOW`, `ERROR_BOX`, and `LOAD_STATUS`. This is used for `cinLogging.printBoxBorderP(boxParams)` and `cinLogging.printInBoxP(text, boxParams)` to produce windows like this:

### LOOK HOW NOT-TRASH THESE ERRORS ARE!

![plugin loading with the new printInBox() system](https://i.imgur.com/5IQKzNi.png)
![and message logging](https://i.imgur.com/cMxfe6I.png)

where it used to be... this
![old system plugin loading... very one color, and formatted like the wild mf west](https://i.imgur.com/9yunkTk.png)
![old system for logging messages... mentioning channel context every single time... ew......](https://i.imgur.com/2AbYVCV.png)

`printInBoxP()` makes an attempt to smartly wrap the text you give it to the character width of the boxParams you provide it. It does a pretty decent job, but doesn't handle emoji very well, causing misalignments 

### 2. Protocol-Based Abstraction (cinAPI pt 1)

to "replace" `discord.py`-specific code, I'm using Python's `Protocol` classes to define interfaces without inheritance, in a way that's currently very `discord.py` shaped:

```python
# actual class in cinAPI.py
class APIMessage(Protocol): # definitely not a discord.py message object
    content: str  
    author: APIUser  
    channel: APIChannel  
    created_at: datetime  
    attachments: List[Any]  
    embeds: List[Any]  
    guild: Optional[APIGuild]  
    id: int  
    client_name: str  
  
    async def reply(self, reply_text,mention_author):  
        # gets message context, to send a message in the same channel  
        ...
```

**Pros**:
- No dependency on specific client libraries
- Core and logging have never even heard of what a discord is! They just get tossed cinAPI shaped events from some `discord_api.py` thing, check if they match any of the handlers bound by the imported plugins, and the plugins shove more cinAPI-shaped things back into the thing-the-events-came-from hole.
- Runtime type checking via `validate_handler()` shows me all the places I duck-typed myself into a skill issue hole with every last one of my plugins. 
- New client implementations shouldn't be too hard to write, when I choose to migrate from discord. Porting to a new client library is now just writing a new `<context>_api.py` in `./api_contexts/`
**Cons**:
 - Every plugin was at some point broken
 - Structure is more OOPy, with protocols and inheritance and such
 - And that's AFTER doing all of the other work in this writeup

### 3. CinAPIManager Singleton (cinAPI pt 2)
`CinAPIManager` assumes a few roles previously hardcoded into core, as a single point of control for:
- Client registration and retrieval
- Event handler routing
- Global state management

This decouples plugins from clients, and.. core from some previously hardcoded parts of core

### 4. Signature Validation for Plugin Registry System
Plugin Registry was 4.0, but to support cinAPI in 4.1, **Signature validation** has been added to ensure plugins are using objects that follow the new client-agnostic cinAPI protocols. This also makes errors log more explicitly.

### misc changes:
- loop tasks are now handled by asyncio directly, instead of as a discord.py task, which shouldn't need any changes to plugins' bind functions
- betterEmbeds plugin - just replies to messages containing direct links from reddit and twitter & such, with embeddable versions of the same link. 
- reminder plugin now tracks the APIClient a message was received from, to.. ask the right client where to send the reminder message 
- cinTypes no longer exists
- cinMessageUtil was basically just a proto-cinAPI.APIMessage, so that's gone, too
- cinShared has been largely rolled into cinReminders and cinLogging, where it was most used, and is now also gone.

---
---
# How Things Work Now That I've Broken Everything(tm):

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Platform API   │    │   API Context   │    │                 │
│      layer      │────▶     Adapter     │────▶                 │
│   (discord.py)  │    │ (discord_api.py)│    │                 │
│ event dispatch  │    │                 │    │ cinAPI Protocol │ 
└─────────────────┘    └─────────────────┘    │  (APIMessage,   │
                                              │  APIUser, etc.) │
┌─────────────────┐                           │ event dispatch  │
│  Future         │    ┌─────────────────┐    │                 │
│  Platform       │────▶  Future         │    │                 │
│  (not discord)  │    │  Adapter        │────▶                 │
└─────────────────┘    └─────────────────┘    └────────────┬────┘
                                                           │
                                                           ▼
┌───────────────────────────────────────────────────────────────┐
│           Protocol-Based Bot Core (bot.py)               │    │
├─────────────────────────────────────────────────────┐    │    │
│  - Plugin Loading on initialization:                │    ▼    │
│      for each plugin in ./plugins/ :                │         │
│        import plugin and call bind_*() functions to │    │    │
│        register handlers for commands, phrases, etc │    │    │
│                                                     │    ▼    │
│  - Event Handlers (registered with cinAPI):         │         │
│      on_ready, on_message, on_reaction              │    │    │
│                                                     │    │    │
│  - Client loading                                   │    │    │
│                                                     │    │    │
│  - Main Loop:                                       │    ▼    │
│      runs bound loop functions from plugins         │         │
├─────────────────────────────────────────────────────┘    │    │
│  When a cinAPI event arrives:                         ◀──┘    │
│      if event matches a registered binding pattern:           │
│              call plugin's handler                            │
└───────────────────────────────────────────────────────────────┘
                                    │
                                    │ (calls)
                                    ▼
┌───────────────────────────────────────────────────────────────┐
│                          Plugins                              │
│                                                               │
│                    Example plugin binding:                    │
│    def bind_commands():                                       │
│        return {"mycommand": my_command}                       │
│                                                               │
│        handler triggered on every message that starts         │
│              with "!>mycommand", from any client:             |
│                                                               │
│    async def my_command(message: APIMessage):                 │
│        await message.channel.send("Hello!")                   │
└───────────────────────────────────────────────────────────────┘
```

```python
cinnamon4/
├── bot.py # core - loads other modules, plugins, and clients
├── cinAPI.py # API protocol all contexts must implement, + manager singleton
├── cinIO.py # basic IO wrapper for configs and caches
├── cinLogging.py # does stuff
├── cinPalette.py # style / formatting consistency
│
├── api_contexts/
│   ├── base.py # base mixin
│   └── discord_api.py # discord api layer
│
├── plugins/
│   ├── betterEmbeds/
│   │   └── __init__.py # replaces direct links with embeddable ones
│   ├── cinDice/
│   │   └── __init__.py # rolls D&D dice
│   ├── cinReminders/
│   │   └── __init__.py # load-bearing reminder plugin that I use too much
│   ├── cinSolve/
│   │   └── __init__.py # just a calculator that uses eval() with a whitelist
│   ├── help/
│   │   └── __init__.py # help system is plugin, too!
│   └── tatoclip_plugin/ # NOT broken at the time of writing actually, I FIXED it
│       ├── __init__.py # tatoclip integration
│       ├── file_operations.py
│       ├── metadata_handler.py
│       ├── notes/
│       ├── project_validation.py
│       └── time_utils.py
│
├── assets/
├── cache/
│   ├── tatoclip/
│   │   ├── <guild_id>/
│   │   │   └── targets_<whatever>.json files live here
│   │   └── tatoclip_config.json
│   ├── reminders.json
│   └── userData.json # currently just time zones
├── configs/
│   ├── config.yaml
│   └── token.yaml
├── logs/
│   └── <guild_name>/
│       └── <channel_name>.html log files live here
├── README.md
├── documentation-4.1.0.md # you are here
└── help.md
```

---
---
# Documentation on the important core files
Feel free to not look at any of this. It's for future vivian, lol. THIS IS AS OF 4.1.0 AND IS LIKELY ALREADY OUTDATED

---
---
# bot.py:

The bot's core. Loads plugins and clients, and does its best to tape them together

## initialization:
- import core modules
- load config.yaml and token.yaml via cinIO
- plugin and handler discovery: for each \_\_init\_\_.py plugin in plugins:
	- check for binding functions to register commands, phrases, reactions, loop, and help handlers to their respective dispatchers
- client discovery: for each hardcoded client api layer imported in hardCodedClientImport() in bot.py:
	- register client via cinAPI.register_client(), called from make_client(), from the api context module for the given client.
	- start client
- loop initialization: 
	- all loop functions found in plugins are bound to the same loop, ran every loopDelay (from config.yaml) seconds, in a task queued alongside client loads. The first loop is always loopDelay after initialization, whether clients are loaded or not.

---
## Plugins:
Each plugin is a directory in `plugins/` containing an `__init__.py` file with specific binding functions:

```python
def bind_commands() -> Dict[str, Callable[[cinAPI.APIMessage], Awaitable[None]]]:
    return {
        "command_name": command_handler_function
    }

def bind_phrases() -> Dict[str, Callable[[cinAPI.APIMessage], Awaitable[None]]]:
    return {
        "trigger_phrase": phrase_handler_function
    }

def bind_reactions() -> Dict[str, Callable[[cinAPI.APIReaction, cinAPI.APIUser], Awaitable[None]]]:
    return {
        "message_phrase": reaction_handler_function
    }

def bind_loop() -> Callable[[], Awaitable[None]]:
    return loop_function

def bind_help() -> Dict[str, str]:
    return {
        "command_name": "Help text for command"
    }
```

### Plugin initialization
During initialization, `bot.py`:
- Iterates through all directories in `plugins/`, looking for `__init__.py` in each directory
- Dynamically imports the `__init__.py` module
- Checks for and calls binding functions to register handlers, validating handler signatures using runtime type checking
- BEFORE CLIENT INITIALIZATION

### Handler Types
- **Commands**: Triggered by prefix (`!>`) followed by command name
- **Phrase Handlers**: Triggered when message contains specific phrases
- **Reaction Handlers**: Triggered on reactions to bot messages containing phrases
- **Loop Functions**: Called periodically on the main loop every `<loopDelay>` seconds
- **Help Entries**: Documentation for commands

---
---
# cinAPI.py

Allows Cinnamon to be client-agnostic instead of only supporting Discord. Uses Python's `Protocol` classes so everything talks to abstract shapes instead of specific libraries. 

```python
# instead of discord.py objects, plugins only see these:
class APIMessage(Protocol):
    content: str          # message text
    author: APIUser       # who sent it
    channel: APIChannel   # where it was sent
    async def reply(self, text): ...  # how to respond

# plugins don't care who sent an APIMessage, except to know that "who" is the square hole to shove more cinAPI-shaped objects into, in any response.
```

### How it works:
There's a `CinAPIManager` singleton and registry functions. Core fires the relevant registry functions on loading plugin bindings, and on loading clients. CinAPIManager is the tape that core references to handle routing client events to their relevant plugin handlers. 

- Client (Discord/etc.) events are wrapped in `cinAPI` protocol
- `CinAPIManager` routes to registered plugin handlers
- Plugin(s) respond using abstract methods, which route back to original client
- Nobody has to hear about discord, except for `discord_api.py`, to which I owe great pity

---
---
# cinIO.py

Wrapper that manages configs and cache files. Supports yaml OR json for configs, but ONLY json for caches. It does what I need it to do, which includes storing help entries, now

```python
config = loadConfig("config.yaml")  # Load configs
token = loadConfig("token.yaml")["token"]  # Get token
user_data = loadCache("userData.json")  # Load cache
overwriteCache("reminders.json", new_data)  # Replace cache
writeConfig("settings.yaml", config_dict)  # Write config
```

---
---
# cinLogging.py

It logs things. I'm tired. 

Uses boxParams from cinPalette to print about things in pretty boxes. 

You can also use `printInBoxP(text, boxParams)` and `printBoxBorderP(boxParams)` to print random arbitrary other things. Static boxParams objects (read: themes) are stored in cinPalettes 

`cinLogging.printInBoxP()` will auto-wrap text to the line width determined by the boxParams object arg.

boxParams objects are structured as follows:

```python
@dataclass(slots=True, frozen=True)  
class BoxParams:  
    box_color: str = highlightedColor  
    box_indentation: int = 4  
    indentation: int = 1  
    width: int = 120 
    text_color: str = defaultColor  
    alt_first_border: bool = False
```

 `cinPalettes` contains predefined boxParams objects for `LARGE_WINDOW_BORDER, LARGE_WINDOW, LARGE_WINDOW_HEADER, LOAD_STATUS,` and `ERROR_BOX` , as well as `HEADER_BOX` and `HEADER_BOX_BORDER`
 
---
---


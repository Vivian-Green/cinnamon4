# api_contexts/discord_api.py
import traceback

import discord
from datetime import datetime
from typing import Optional, List, Union, Dict, Any

import cinAPI
import cinIO
import cinLogging
from cinPalette import *

CLIENT_NAME = "discord"


# ---------- ADAPTER OBJECTS ----------

class DiscordUser:
    def __init__(self, user: Union[discord.User, discord.Member]):
        self._u = user

    @property
    def id(self) -> int:
        return self._u.id

    @property
    def name(self) -> str:
        return self._u.name

    @property
    def display_name(self) -> str:
        return getattr(self._u, 'display_name', self._u.name)

    @property
    def bot(self) -> bool:
        return self._u.bot

    @property
    def color(self) -> Optional[str]:
        if hasattr(self._u, 'color') and self._u.color:
            return str(self._u.color)
        return None

    async def send(self, content: str):
        await self._u.send(content)

channel_id_names_dict = {}


class DiscordChannel:
    def __init__(self, channel: Union[discord.TextChannel, discord.DMChannel, discord.GroupChannel], author_name: str):
        self.author_name = author_name
        self._c = channel
        self._cached_name = None
        self._id = channel.id
        self.client_name = CLIENT_NAME

    async def send(self, content: str) -> None:
        await self._c.send(content)

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        if self._cached_name:
            return self._cached_name

        # Check global memoization first
        cached = channel_id_names_dict.get(self._id)
        if cached:
            self._cached_name = cached
            return cached

        # Guild channel
        if isinstance(self._c, discord.TextChannel):
            self._cached_name = self._c.name
            channel_id_names_dict[self._id] = self._cached_name
            return self._cached_name

        # DM channel
        if isinstance(self._c, discord.DMChannel):
            self._cached_name = f"DM-{self.author_name}"
        else:
            self._cached_name = f"GroupDM-{self._c.id}"

        # Update global memoization
        channel_id_names_dict[self._id] = self._cached_name

        return self._cached_name


class DiscordGuild:
    def __init__(self, guild: discord.Guild):
        self._g = guild

    @property
    def id(self) -> int:
        return self._g.id

    @property
    def name(self) -> str:
        return self._g.name


class DiscordMessage:
    def __init__(self, msg: discord.Message):
        self.content = msg.content
        self.author = DiscordUser(msg.author)
        self.channel = DiscordChannel(msg.channel, msg.author.display_name)
        self.created_at = msg.created_at
        self.attachments = list(msg.attachments)
        self.embeds = list(msg.embeds)
        self._guild = msg.guild
        self.id = msg.id
        self.client_name = CLIENT_NAME

    @property
    def guild(self) -> Optional[DiscordGuild]:
        if self._guild:
            return DiscordGuild(self._guild)
        return None

    async def reply(self, reply_text: str, mention_author: bool = False) -> None:
        """Sends a reply to the current message in the same channel."""
        try:
            await self.channel.send(reply_text)
        except discord.HTTPException as e2:
            print(f"Failed to send message: {e2}")


class DiscordReaction:
    def __init__(self, reaction: discord.Reaction, message: DiscordMessage):
        self.message = message
        self.emoji = reaction.emoji


class DiscordAPIClient(cinAPI.InternalEventDispatchMixin, discord.Client):
    """Discord.py implementation of the APIClient protocol"""

    def __init__(self, name: str, **kwargs):
        # Initialize the mixin
        cinAPI.InternalEventDispatchMixin.__init__(self, name)

        # Set up discord.py client
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        self.client_name = CLIENT_NAME

        # Initialize discord.Client with intents
        discord.Client.__init__(self, intents=intents, **kwargs)

        # Set up event handlers
        self._setup_task = None
        boxIndentation, indentation, boxWidth = 3, 3, 120
        cinLogging.printInBoxP("DiscordAPIClient init", LARGE_WINDOW)

    async def get_channel_by_id(self, channelID: int) -> Optional[DiscordChannel]:
        """Get a channel by ID."""
        channel = self.get_channel(channelID)
        if channel:
            # Determine author_name for DM channels
            author_name = None
            if isinstance(channel, discord.DMChannel):
                recipient = getattr(channel, 'recipient', None)
                if recipient:
                    author_name = recipient.display_name
            return DiscordChannel(channel, author_name)
        return None

    async def get_user_by_id(self, userID: int) -> Optional[DiscordUser]:
        """Get a user by ID."""
        user = self.get_user(userID)
        if user:
            return DiscordUser(user)
        return None

    async def _setup_event_handlers(self) -> None:
        print("DiscordAPIClient setting up event handlers")
        """Set up discord.py event handlers"""
        await super()._setup_event_handlers()
        print("DiscordAPIClient event handlers set up")

        # Setup discord.py event handlers
        self._setup_task = self.loop.create_task(self._setup_discord_handlers())
        print("DiscordAPIClient event handlers setup task created")

    async def _setup_discord_handlers(self) -> None:
        """Setup discord.py event handlers after client is ready"""
        # We'll set these up after the client is ready to ensure everything is initialized
        pass

    async def on_ready(self) -> None:
        """Discord.py ready event handler"""
        print(f'Discord client "{self.name}" logged in as {self.user}')
        await self._on_internal_ready()

    async def on_message(self, message: discord.Message) -> None:
        """Discord.py message event handler"""
        # Don't process messages from self
        if message.author == self.user:
            return

        await self._on_internal_message(DiscordMessage(message))

    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User) -> None:
        """Discord.py reaction add event handler"""
        # Don't process reactions from self
        if user == self.user:
            return

        # Create wrapper objects
        discord_message = DiscordMessage(reaction.message)
        discord_reaction = DiscordReaction(reaction, discord_message)
        discord_user = DiscordUser(user)

        await self._on_internal_reaction_add(discord_reaction, discord_user)

    async def set_presence(self, activity: str, status: str = "online") -> None:
        """Change the bot's presence with activity type support"""
        #print(f"actually setting presence in discord api to {activity}")

        # Check if client is ready and WebSocket is connected
        if not self.is_ready():
            print(f"  Warning: Client not ready yet, postponing presence update")
            return

        if self.ws is None or not self.ws.open:
            print(f"  Warning: WebSocket not connected, postponing presence update")
            return

        # Convert status string to discord.Status enum
        status_map = {
            "online": discord.Status.online,
            "idle": discord.Status.idle,
            "dnd": discord.Status.do_not_disturb,
            "do_not_disturb": discord.Status.do_not_disturb,
            "invisible": discord.Status.invisible,
            "offline": discord.Status.offline
        }

        discord_activity = None
        if activity:
            discord_activity = discord.Activity(name=activity, type=discord.ActivityType.playing)

        # Actually change the presence
        try:
            #print(
                #f"  Client status: ready={self.is_ready()}, ws={self.ws is not None}, ws.open={self.ws.open if self.ws else 'N/A'}")
            await self.change_presence(activity=discord_activity,
                                       status=status_map.get(status.lower(), discord.Status.online))
            thisHour = datetime.now().hour
            thisMinute = datetime.now().minute
            amOrPm = "am"
            if thisHour > 12:
                amOrPm = "pm"
                thisHour -= 12
                if thisHour == 0:
                    thisHour = 12

            cinLogging.printInBox(f"status updated at {thisHour}:{thisMinute}{amOrPm}", debugColor, 4, 8, 120, color=debugColor)
        except Exception as e:
            print(f"Failed to set presence: {e}")
            traceback.print_exc()
            # Don't exit - just log the error and continue
            print(f"  Non-fatal error, continuing...")

        # Optionally call super if the mixin has its own handling
        await super().set_presence(activity=activity, status=status)

    async def start_client(self) -> None:
        """Start the discord client - non-blocking version"""
        print(f"Starting DiscordAPIClient '{self.name}'...")

        try:
            # This is the correct way to start a discord.py client
            await self.login(cinIO.token)
            await self.connect()
        except Exception as e:
            print(f"Discord client '{self.name}' failed to start: {e}")
            traceback.print_exc()
            raise

    async def stop_client(self) -> None:
        """Stop the discord client"""
        if not self.is_closed():
            await self.close()

    @property
    def user(self) -> DiscordUser:
        """Get the client user as DiscordUser"""
        return DiscordUser(super().user)


def make_client(name: str, **kwargs) -> DiscordAPIClient:
    """Create and register a Discord client"""
    # Create the client
    client = DiscordAPIClient(name=name, **kwargs)

    # Register with cinAPI
    set_as_default = kwargs.get('set_as_default', False)
    cinAPI.register_client(name, client, set_as_default=set_as_default)

    # Just return the client, don't start it yet
    return client
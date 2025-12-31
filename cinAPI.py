# cinAPI.py
from datetime import datetime
from typing import List, Dict, Callable, Awaitable, Literal, Optional, Any, Protocol
import logging
from cinPalette import LARGE_WINDOW


# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[ discord.py shaped things

class APIUser(Protocol):
    id: int
    name: str
    display_name: str
    bot: bool
    color: Optional[str]

    async def send(self, content: str) -> None: ...

class APIGuild(Protocol):
    id: int
    name: str

class APIChannel(Protocol):
    id: int
    name: str
    client_name: str

    async def send(self, content: str) -> None: ...


class APIMessage(Protocol):
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


class APIReaction(Protocol):
    message: APIMessage
    emoji: Any

class APIClient(Protocol):
    """Base protocol that API clients must implement"""
    name: str
    user: APIUser

    async def set_presence(self, activity: str, status: str = "online"): ...

    async def start_client(self): ...

    async def stop_client(self): ...

    # Methods for internal event handling that concrete clients should implement
    async def _setup_event_handlers(self): ...
    """Setup internal event handlers that will call cinAPI dispatchers"""

    async def _on_internal_ready(self): ...
    """Internal ready handler that concrete clients should call"""

    async def _on_internal_message(self, message: APIMessage): ...
    """Internal message handler that concrete clients should call"""

    async def _on_internal_reaction_add(self, reaction: APIReaction, user: APIUser): ...
    """Internal reaction handler that concrete clients should call"""

    async def get_channel_by_id(self, param):
        pass

    async def get_user_by_id(self, param):
        pass

# !!!~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~[ actual cinAPI code:

logger = logging.getLogger(__name__)

# Registry for multiple clients
class ClientRegistry:
    """Manages multiple API client instances"""

    def __init__(self):
        self._clients: Dict[str, APIClient] = {}
        self._default_client: Optional[str] = None

    def register(self, name: str, client: APIClient, set_as_default: bool = False):
        """Register a new client instance"""
        if name in self._clients:
            logger.warning(f"Client '{name}' is already registered. Overwriting.")

        self._clients[name] = client
        if set_as_default or self._default_client is None:
            self._default_client = name
        logger.debug(f"Registered client '{name}'")

    def get(self, name: Optional[str] = None) -> APIClient:
        """Get a client by name, or the default client"""
        client_name = name or self._default_client
        if client_name is None or client_name not in self._clients:
            raise ValueError(f"No client registered with name '{client_name}'")
        return self._clients[client_name]

    def get_all(self) -> Dict[str, APIClient]:
        """Get all registered clients"""
        return self._clients.copy()


# Event handling system with client-specific handlers
class EventHandlerRegistry:
    """Manages event handlers with client-specific routing"""

    def __init__(self):
        # Structure: {client_name: {event_type: [handlers]}}
        self._client_handlers: Dict[str, Dict[str, List[Callable]]] = {}
        # Global handlers (for all clients)
        self._global_handlers: Dict[str, List[Callable]] = {
            'ready': [],
            'message': [],
            'reaction': []
        }

    def register_global_handler(self, event_type: str, handler: Callable):
        """Register a handler for all clients"""
        if event_type not in self._global_handlers:
            raise ValueError(f"Unknown event type: {event_type}")
        self._global_handlers[event_type].append(handler)
        logger.debug(f"Registered global {event_type} handler")

    def register_client_handler(self, client_name: str, event_type: str, handler: Callable):
        """Register a handler for a specific client"""
        if event_type not in self._global_handlers:
            raise ValueError(f"Unknown event type: {event_type}")

        if client_name not in self._client_handlers:
            self._client_handlers[client_name] = {
                'ready': [],
                'message': [],
                'reaction': []
            }

        self._client_handlers[client_name][event_type].append(handler)
        logger.debug(f"Registered {event_type} handler for client '{client_name}'")

    async def dispatch(self, client_name: str, event_type: str, *args, **kwargs):
        """Dispatch an event to appropriate handlers"""
        handlers_called = 0
        # print(f"DEBUG: Dispatching {event_type} from client '{client_name}'")

        # Call global handlers first
        for handler in self._global_handlers.get(event_type, []):
            # print(f"DEBUG: Calling global handler: {handler.__name__} (id: {id(handler)})")
            await handler(*args, **kwargs)
            handlers_called += 1

        # Call client-specific handlers
        if client_name in self._client_handlers:
            for handler in self._client_handlers[client_name].get(event_type, []):
                # print(f"DEBUG: Calling client handler: {handler.__name__} (id: {id(handler)})")
                await handler(*args, **kwargs)
                handlers_called += 1

        if handlers_called == 0:
            logger.debug(f"No handlers for {event_type} event from client '{client_name}'")

# Singleton instance of the API manager
class CinAPIManager: # todo: does this need to be shaped like this?
    """Main API manager supporting multiple clients"""

    _instance: Optional['CinAPIManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.clients = ClientRegistry()
            self.events = EventHandlerRegistry()
            self._initialized = True

    def register_client(self, name: str, client: APIClient, set_as_default: bool = False):
        """Register a new API client"""
        self.clients.register(name, client, set_as_default)

    def get_client(self, name: Optional[str] = None) -> APIClient:
        """Get a client by name or the default client"""
        return self.clients.get(name)


# Global singleton instance
_manager = CinAPIManager()


# Public API functions
def register_client(name: str, client: APIClient, set_as_default: bool = False):
    """Register a new API client"""
    _manager.register_client(name, client, set_as_default)


def get_client(name: Optional[str] = None) -> APIClient:
    """Get a client by name or the default client"""
    return _manager.get_client(name)


def get_all_clients() -> Dict[str, APIClient]:
    """Get all registered clients"""
    return _manager.clients.get_all()


# Event handler registration with client support
def register_ready_handler(handler: Callable[[APIClient], Awaitable[None]],
                           client_name: Optional[str] = None):
    """Register a handler for ready events"""
    if client_name:
        _manager.events.register_client_handler(client_name, 'ready', handler)
    else:
        _manager.events.register_global_handler('ready', handler)


def register_message_handler(handler: Callable[[APIMessage], Awaitable[None]],
                             client_name: Optional[str] = None):
    """Register a handler for message events"""
    if client_name:
        _manager.events.register_client_handler(client_name, 'message', handler)
    else:
        _manager.events.register_global_handler('message', handler)

def register_reaction_handler(handler: Callable[[APIReaction, APIUser], Awaitable[None]],
                              client_name: Optional[str] = None):
    """Register a handler for reaction events"""
    if client_name:
        _manager.events.register_client_handler(client_name, 'reaction', handler)
    else:
        _manager.events.register_global_handler('reaction', handler)






class InternalEventDispatchMixin:
    """
    Mixin providing shared internal event dispatch plumbing.
    """

    name: str
    _setup_done: bool

    def __init__(self, name: str):
        self.name = name
        self._setup_done = False
        import cinLogging
        cinLogging.printInBoxP("InternalEventDispatchMixin init", LARGE_WINDOW)

    async def set_presence(self, activity: str, status: str = "online"): ...

    async def _setup_event_handlers(self):
        """
        Sets up internal event handlers to dispatch to cinAPI.

        Concrete clients should:
        - override this method
        - register SDK-specific callbacks
        - call super()._setup_event_handlers() last
        """
        if self._setup_done:
            return

        self._setup_done = True
        logger.debug("Internal event handlers set up for client '%s'", self.name)

    async def _on_internal_ready(self):
        """
        Called by the concrete client when the underlying SDK is ready.
        """
        logger.debug("Internal ready event for client '%s'", self.name)
        await _manager.events.dispatch(self.name, 'ready', self)

    async def _on_internal_message(self, message: APIMessage):
        """
        Called by the concrete client when a message is received.
        """
        logger.debug("Internal message event for client '%s'", self.name)
        await _manager.events.dispatch(self.name, 'message', message)

    async def _on_internal_reaction_add(
        self,
        reaction: APIReaction,
        user: APIUser,
    ):
        """
        Called by the concrete client when a reaction is added.
        """
        logger.debug("Internal reaction event for client '%s'", self.name)
        await _manager.events.dispatch(self.name, 'reaction', reaction, user)

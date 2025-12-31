import re
import cinAPI as CinAPI
from typing import Dict, List, Tuple, Optional

MY_USER_ID = 888470282367565895  # Replace with actual support user ID

# Constants for consistent messaging
EMBED_FIX_MESSAGE = "Here's your link(s), but actually embeddable in Discord:"

# map domains to unenshittified alternatives that don't force you to sign up for a fukin account, or view their ads
EMBED_FIXERS = {
    # twitter/X
    'twitter.com': 'fxtwitter.com',
    'x.com': 'fxtwitter.com',

    # instagram
    'instagram.com': 'ddinstagram.com',
    'kkinstagram.com': 'ddinstagram.com',

    # reddit
    'reddit.com': 'rxyddit.com',
    'old.reddit.com': 'rxyddit.com',

    # tiktok
    'tiktok.com': 'vxtiktok.com',
    'tiktxk.com': 'vxtiktok.com',

    # facebook
    'facebook.com': 'facebookez.com',

    # bluesky
    'bsky.app': 'fxbsky.app',
}

ALTERNATIVES = {
    'fxtwitter.com': ['vxtwitter.com', 'fixvx.com', 'twittpr.com'],
    'ddinstagram.com': ['instagramez.com', 'www.instagr.am', 'ddinsta.com'],
    'rxyddit.com': ['fxreddit.com', 'redditez.com', 'rxyddit.com'],
    'vxtiktok.com': ['tiktxk.com', 'tiktokcdn.com'],
    'facebookez.com': [],
    'fxbsky.app': []
}

failed_embeds_cache = set()

URL_REGEX = re.compile(
    r'https?://(?:www\.)?([^/\s]+)(/[^\s<>"\']*)?'
)


def find_and_fix_urls(content: str) -> List[Tuple[str, str]]:
    """replace embed domains with unenshittified alternatives."""
    urls = URL_REGEX.finditer(content)
    replacements = []

    for match in urls:
        full_url = match.group(0)
        domain = match.group(1)

        if not (domain in EMBED_FIXERS):
            continue

        # for each url in message that matches a domain in EMBED_FIXERS: unenshittify it

        fixed_domain = EMBED_FIXERS[domain]
        fixed_url = full_url.replace(domain, fixed_domain, 1)
        replacements.append((full_url, fixed_url, fixed_domain))

    return replacements


async def auto_fix_embeds(message: CinAPI.APIMessage):
    if message.author.bot:
        return

    original_content = message.content
    replacements = find_and_fix_urls(original_content)

    if not replacements:
        return

    # on message that contains a url matching an EMBED_FIXERS key: build a reply with the fixed urls

    lines = [EMBED_FIX_MESSAGE]

    for original, fixed, fixed_domain in replacements:
        lines.append(fixed)

    reply_text = "\n".join(lines)

    reply_message = await message.reply(reply_text, mention_author=False)

    # Add reactions for feedback
    try:
        await reply_message.add_reaction("❌")
    except:
        pass  # Bot doesn't have reaction permissions


async def handle_embed_failed_reaction(reaction: CinAPI.APIReaction, user: CinAPI.APIUser):
    if user.bot:
        return

    message = reaction.message

    # is this the embed replacement message?
    if message.author != user.bot:
        return
    if not message.content.startswith(EMBED_FIX_MESSAGE):
        return

    # Handle ❌ reaction - embed didn't work
    if not (str(reaction.emoji) == "❌" and message.id not in failed_embeds_cache):
        return
    failed_embeds_cache.add(message.id)

    # extract the fixed domains from the original reply
    urls = URL_REGEX.findall(message.content)
    if not urls:
        # should not be a valid path. if cinnamon gets here... do better? skill issue? I ain't throwing here
        return

    alternative_lines = []

    # get all unique fixed domains from the URLs
    fixed_domains = set()
    for url_match in urls:
        domain = url_match[0] if url_match else ""
        # check if this domain is one of our fixed domains (in ALTERNATIVES keys)
        if domain in ALTERNATIVES:
            fixed_domains.add(domain)

    # build alternatives message for each fixed domain
    for fixed_domain in fixed_domains:
        if ALTERNATIVES[fixed_domain]:
            # get all alternatives for this domain
            for alt_domain in ALTERNATIVES[fixed_domain]:
                # for each URL in the message that uses this fixed domain, create alternative
                for url_match in urls:
                    domain = url_match[0] if url_match else ""
                    path = url_match[1] if url_match[1] else ""
                    if domain == fixed_domain:
                        alt_url = f"https://{alt_domain}{path}"
                        alternative_lines.append(f"alt: {alt_url}")

    if alternative_lines:
        support_message = "Well frick. alternatives:\n" + "\n".join(alternative_lines)
    else:
        support_message = "No known alternatives available for these domains."

    support_message += f"\n-# Oi! <@{MY_USER_ID}>! somefink ain't right with the embed unenshittification for {message.id}\n hopefully that mirror is just down atm."

    await message.channel.send(support_message)


def bind_reactions() -> Dict[str, callable]:
    """bind reaction handlers for feedback."""
    return {
        "❌": handle_embed_failed_reaction
    }


def bind_phrases() -> Dict[str, callable]:
    """triggers on any message containing a URL."""
    return {
        "http": auto_fix_embeds
    }
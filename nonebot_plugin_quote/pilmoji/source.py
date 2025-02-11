from abc import ABC, abstractmethod
from io import BytesIO

from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import quote_plus

from typing import Any, ClassVar, Dict, Optional

try:
    import requests
    _has_requests = True
except ImportError:
    requests = None
    _has_requests = False

__all__ = (
    'BaseSource',
    'HTTPBasedSource',
    'DiscordEmojiSourceMixin',
    'EmojiCDNSource',
    'TwitterEmojiSource',
    'AppleEmojiSource',
    'GoogleEmojiSource',
    'FacebookEmojiSource',
    'TwemojiEmojiSource',
    'Twemoji',
)


class BaseSource(ABC):
    """The base class for an emoji image source."""

    @abstractmethod
    def get_emoji(self, emoji: str, /) -> Optional[BytesIO]:
        """Retrieves a :class:`io.BytesIO` stream for the image of the given emoji.

        Parameters
        ----------
        emoji: str
            The emoji to retrieve.

        Returns
        -------
        :class:`io.BytesIO`
            A bytes stream of the emoji.
        None
            An image for the emoji could not be found.
        """
        raise NotImplementedError

    @abstractmethod
    def get_discord_emoji(self, id: int, /) -> Optional[BytesIO]:
        """Retrieves a :class:`io.BytesIO` stream for the image of the given Discord emoji.

        Parameters
        ----------
        id: int
            The snowflake ID of the Discord emoji.

        Returns
        -------
        :class:`io.BytesIO`
            A bytes stream of the emoji.
        None
            An image for the emoji could not be found.
        """
        raise NotImplementedError

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'


class HTTPBasedSource(BaseSource):
    """Represents an HTTP-based source."""

    REQUEST_KWARGS: ClassVar[Dict[str, Any]] = {
        'headers': {'User-Agent': 'Mozilla/5.0'}
    }

    def __init__(self) -> None:
        if _has_requests:
            self._requests_session = requests.Session()

    def request(self, url: str) -> bytes:
        """Makes a GET request to the given URL.

        If the `requests` library is installed, it will be used.
        If it is not installed, :meth:`urllib.request.urlopen` will be used instead.

        Parameters
        ----------
        url: str
            The URL to request from.

        Returns
        -------
        bytes

        Raises
        ------
        Union[:class:`requests.HTTPError`, :class:`urllib.error.HTTPError`]
            There was an error requesting from the URL.
        """
        if _has_requests:
            with self._requests_session.get(url, **self.REQUEST_KWARGS) as response:
                if response.ok:
                    return response.content
        else:
            req = Request(url, **self.REQUEST_KWARGS)
            with urlopen(req) as response:
                return response.read()

    @abstractmethod
    def get_emoji(self, emoji: str, /) -> Optional[BytesIO]:
        raise NotImplementedError

    @abstractmethod
    def get_discord_emoji(self, id: int, /) -> Optional[BytesIO]:
        raise NotImplementedError


class DiscordEmojiSourceMixin(HTTPBasedSource):
    """A mixin that adds Discord emoji functionality to another source."""

    BASE_DISCORD_EMOJI_URL: ClassVar[str] = 'https://cdn.discordapp.com/emojis/'

    @abstractmethod
    def get_emoji(self, emoji: str, /) -> Optional[BytesIO]:
        raise NotImplementedError

    def get_discord_emoji(self, id: int, /) -> Optional[BytesIO]:
        url = self.BASE_DISCORD_EMOJI_URL + str(id) + '.png'
        _to_catch = HTTPError if not _has_requests else requests.HTTPError

        try:
            return BytesIO(self.request(url))
        except _to_catch:
            pass


class EmojiCDNSource(DiscordEmojiSourceMixin):
    """A base source that fetches emojis from https://emojicdn.elk.sh/."""

    BASE_EMOJI_CDN_URL: ClassVar[str] = 'https://emojicdn.elk.sh/'
    STYLE: ClassVar[str] = None
    CACHE_DIR: ClassVar[str] = 'emoji_cache'

    def __init__(self, disk_cache=False):
        super().__init__()
        self.disk_cache = disk_cache
        if self.disk_cache:
            self.cache_dir = Path(self.CACHE_DIR)
            self.cache_dir.mkdir(exist_ok=True)

    def get_emoji(self, emoji: str, /) -> Optional[BytesIO]:
        if self.STYLE is None:
            raise TypeError('STYLE class variable unfilled.')

        if self.disk_cache:
            cache_file = self.cache_dir / f"{emoji}_{self.STYLE}.png"

            if cache_file.exists():
                with cache_file.open('rb') as f:
                    return BytesIO(f.read())
            else:
                url = self.BASE_EMOJI_CDN_URL + quote_plus(emoji) + '?style=' + quote_plus(self.STYLE)
                _to_catch = HTTPError if not _has_requests else requests.HTTPError

                try:
                    data = self.request(url)
                    with cache_file.open('wb') as f:
                        f.write(data)
                    return BytesIO(data)
                except _to_catch:
                    pass
        else:
            url = self.BASE_EMOJI_CDN_URL + quote_plus(emoji) + '?style=' + quote_plus(self.STYLE)
            _to_catch = HTTPError if not _has_requests else requests.HTTPError

            try:
                return BytesIO(self.request(url))
            except _to_catch:
                pass


class TwitterEmojiSource(EmojiCDNSource):
    """A source that uses Twitter-style emojis. These are also the ones used in Discord."""
    STYLE = 'twitter'


class AppleEmojiSource(EmojiCDNSource):
    """A source that uses Apple emojis."""
    STYLE = 'apple'


class GoogleEmojiSource(EmojiCDNSource):
    """A source that uses Google emojis."""
    STYLE = 'google'


class FacebookEmojiSource(EmojiCDNSource):
    """A source that uses Facebook emojis."""
    STYLE = 'facebook'


# Aliases
TwemojiEmojiSource = Twemoji = TwitterEmojiSource

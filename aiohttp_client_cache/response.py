import json
from datetime import datetime
from http.cookies import SimpleCookie
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, Mapping

import attr
from aiohttp import ClientResponse, ClientResponseError
from aiohttp.client_reqrep import ContentDisposition, RequestInfo
from aiohttp.typedefs import RawHeaders, StrOrURL
from multidict import CIMultiDict, CIMultiDictProxy, MultiDict, MultiDictProxy
from yarl import URL

# CachedResponse attributes to not copy directly from ClientResponse
EXCLUDE_ATTRS = {
    '_body',
    '_links',
    'created_at',
    'encoding',
    'expires',
    'history',
    'last_used',
    'real_url',
    'request_info',
}
JsonResponse = Optional[Dict[str, Any]]
DictItems = List[Tuple[str, str]]
LinkItems = List[Tuple[str, DictItems]]
LinkMultiDict = MultiDictProxy[MultiDictProxy[Union[str, URL]]]


@attr.s(slots=True)
class CachedResponse:
    """A dataclass containing cached response information, used for serialization.
    It will mostly behave the same as a :py:class:`aiohttp.ClientResponse` that has been read,
    with some additional cache-related info.
    """

    method: str = attr.ib()
    reason: str = attr.ib()
    status: int = attr.ib()
    url: StrOrURL = attr.ib()
    version: str = attr.ib()
    _body: Any = attr.ib(default=None)
    _links: LinkItems = attr.ib(factory=list)
    content_disposition: ContentDisposition = attr.ib(default=None)
    cookies: SimpleCookie = attr.ib(default=None)
    created_at: datetime = attr.ib(factory=datetime.utcnow)
    encoding: str = attr.ib(default=None)
    expires: Optional[datetime] = attr.ib(default=None)
    raw_headers: RawHeaders = attr.ib(factory=tuple)
    real_url: StrOrURL = attr.ib(default=None)
    history: Iterable = attr.ib(factory=tuple)
    last_used: datetime = attr.ib(factory=datetime.utcnow)

    @classmethod
    async def from_client_response(cls, client_response: ClientResponse, expires: datetime = None):
        """Convert a ClientResponse into a CachedReponse"""
        # Response may not have been read yet, if fetched by something other than CachedSession
        if not client_response._released:
            await client_response.read()

        # Copy most attributes over as is
        copy_attrs = set(attr.fields_dict(cls).keys()) - EXCLUDE_ATTRS
        response = cls(**{k: getattr(client_response, k) for k in copy_attrs})

        # Set some remaining attributes individually
        response._body = client_response._body
        response._links = [(k, _to_str_tuples(v)) for k, v in client_response.links.items()]
        response.expires = expires
        response.real_url = client_response.request_info.real_url

        # The encoding may be unset even if the response has been read
        try:
            response.encoding = client_response.get_encoding()
        except RuntimeError:
            pass

        response.url = str(client_response.url)
        if client_response.history:
            response.history = (
                *[await cls.from_client_response(r) for r in client_response.history],
            )
        return response

    @property
    def ok(self) -> bool:
        """Returns ``True`` if ``status`` is less than ``400``, ``False`` if not"""
        try:
            self.raise_for_status()
            return True
        except ClientResponseError:
            return False

    def get_encoding(self):
        return self.encoding

    @property
    def headers(self) -> CIMultiDictProxy[str]:
        """Get headers as an immutable, case-insensitive multidict from raw headers"""

        def decode_header(header):
            return (
                header[0].decode('utf-8', 'surrogateescape'),
                header[1].decode('utf-8', 'surrogateescape'),
            )

        return CIMultiDictProxy(CIMultiDict([decode_header(h) for h in self.raw_headers]))

    @property
    def is_expired(self) -> bool:
        """Determine if this cached response is expired"""
        return self.expires is not None and datetime.utcnow() > self.expires

    @property
    def links(self) -> LinkMultiDict:
        """Convert stored links into the format returned by :attr:`ClientResponse.links`"""
        items = [(k, _to_url_multidict(v)) for k, v in self._links]
        return MultiDictProxy(MultiDict([(k, MultiDictProxy(v)) for k, v in items]))

    async def json(self, encoding: Optional[str] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Read and decode JSON response"""
        stripped = self._body.strip()
        if not stripped:
            return None
        return json.loads(stripped.decode(encoding or self.encoding))

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise ClientResponseError(
                self.request_info,  # type: ignore  # These types are interchangeable
                tuple(),
                status=self.status,
                message=self.reason,
                headers=self.headers,
            )

    def read(self):
        """No-op function for compatibility with ClientResponse"""

    def release(self):
        """No-op function for compatibility with ClientResponse"""

    @property
    def request_info(self) -> RequestInfo:
        return RequestInfo(
            url=URL(self.url),
            method=self.method,
            headers=self.headers,
            real_url=URL(self.real_url),
        )

    async def text(self, encoding: Optional[str] = None, errors: str = "strict") -> str:
        """Read response payload and decode"""
        return self._body.decode(encoding or self.encoding, errors=errors)


def _to_str_tuples(data: Mapping) -> DictItems:
    return [(k, str(v)) for k, v in data.items()]


def _to_url_multidict(data: DictItems) -> MultiDict:
    return MultiDict([(k, URL(url)) for k, url in data])


AnyResponse = Union[ClientResponse, CachedResponse]

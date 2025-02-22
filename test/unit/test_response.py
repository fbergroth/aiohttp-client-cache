import asyncio
import pytest
from datetime import datetime, timedelta

from aiohttp import ClientResponseError, ClientSession, web
from multidict import MultiDictProxy
from yarl import URL

from aiohttp_client_cache.response import CachedResponse, RequestInfo


async def get_real_response():
    # Just for debugging purposes, not used by unit tests
    async with ClientSession() as session:
        return await session.get('http://httpbin.org/get')


async def get_test_response(client_factory, url='/', **kwargs):
    app = web.Application()
    app.router.add_route('GET', '/valid_url', mock_handler)
    client = await client_factory(app)
    client_response = await client.get(url)

    return await CachedResponse.from_client_response(client_response, **kwargs)


async def mock_handler(request):
    return web.Response(
        body=b'Hello, world',
        headers={'Link': '<https://example.com>; rel="preconnect"'},
    )


async def test_basic_attrs(aiohttp_client):
    response = await get_test_response(aiohttp_client)

    assert response.method == 'GET'
    assert response.reason == 'Not Found'
    assert response.status == 404
    assert response.encoding == 'utf-8'
    assert response.headers['Content-Type'] == 'text/plain; charset=utf-8'
    assert await response.text() == '404: Not Found'
    assert response.history == tuple()
    assert response.is_expired is False


async def test_expiration(aiohttp_client):
    response = await get_test_response(
        aiohttp_client, expires=datetime.utcnow() + timedelta(seconds=0.01)
    )
    await asyncio.sleep(0.01)
    assert response.is_expired is True


async def test_encoding(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    assert response.encoding == response.get_encoding() == 'utf-8'


async def test_request_info(aiohttp_client):
    response = await get_test_response(aiohttp_client, '/valid_url')
    request_info = response.request_info

    assert isinstance(request_info, RequestInfo)
    assert request_info.method == 'GET'
    assert request_info.url == request_info.real_url
    assert str(request_info.url).endswith('/valid_url')
    assert 'Content-Type' in request_info.headers and 'Content-Length' in request_info.headers


async def test_headers(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    raw_headers = dict(response.raw_headers)

    assert b'Content-Type' in raw_headers and b'Content-Length' in raw_headers
    assert 'Content-Type' in response.headers and 'Content-Length' in response.headers
    with pytest.raises(TypeError):
        response.headers['key'] = 'value'


async def test_headers__case_insensitive_multidict(aiohttp_client):
    """Headers should be case-insensitive and allow multiple values"""
    response = await get_test_response(aiohttp_client)
    response.raw_headers += ((b'Cache-Control', b'public'),)
    response.raw_headers += ((b'Cache-Control', b'max-age=360'),)

    assert response.headers['Cache-Control'] == 'public'
    assert response.headers.get('Cache-Control') == 'public'
    assert response.headers.get('CACHE-CONTROL') == 'public'
    assert set(response.headers.getall('Cache-Control')) == {'max-age=360', 'public'}


async def test_links(aiohttp_client):
    response = await get_test_response(aiohttp_client, '/valid_url')
    expected_links = [('preconnect', [('rel', 'preconnect'), ('url', 'https://example.com')])]
    assert response._links == expected_links
    assert isinstance(response.links, MultiDictProxy)
    assert response.links['preconnect']['url'] == URL('https://example.com')


# TODO
async def test_history(aiohttp_client):
    pass


# TODO
async def test_json(aiohttp_client):
    pass


async def test_raise_for_status__200(aiohttp_client):
    response = await get_test_response(aiohttp_client, '/valid_url')
    assert not response.raise_for_status()
    assert response.ok is True


async def test_raise_for_status__404(aiohttp_client):
    response = await get_test_response(aiohttp_client, '/invalid_url')
    with pytest.raises(ClientResponseError):
        response.raise_for_status()
    assert response.ok is False


async def test_text(aiohttp_client):
    response = await get_test_response(aiohttp_client)
    assert await response.text() == '404: Not Found'


async def test_no_op(aiohttp_client):
    # Just make sure CachedResponse doesn't explode if extra ClientResponse methods are called
    response = await get_test_response(aiohttp_client)
    response.read()
    response.release()

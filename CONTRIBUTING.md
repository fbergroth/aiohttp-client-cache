# Contributing

## Installation
To set up for local development:

```bash
$ git clone https://github.com/JWCook/aiohttp-client-cache
$ cd aiohttp-client-cache
$ pip install -Ue ".[dev]"
```

## Pre-commit hooks
[Pre-commit](https://github.com/pre-commit/pre-commit) config is uncluded to run the same checks
locally that are run in CI jobs by GitHub Actions. This is optional but recommended.
```bash
$ pre-commit install --config .github/pre-commit.yml
```

To uninstall:
```bash
$ pre-commit uninstall
```

## Integration Tests
Local databases are required to run integration tests, and docker-compose config is included to make
this easier. First, [install docker](https://docs.docker.com/get-docker/) and
[install docker-compose](https://docs.docker.com/compose/install/).

Then, run:
```bash
$ docker-compose up -d
pytest test/integration
```

## Documentation
[Sphinx](http://www.sphinx-doc.org/en/master/) is used to generate documentation.

To build the docs locally:
```bash
$ make -C docs html
```

To preview:
```bash
# MacOS:
$ open docs/_build/index.html
# Linux:
$ xdg-open docs/_build/index.html
```

### Readthedocs
Documentation is automatically built by Readthedocs whenever code is merged into the `main` branch.

Sometimes, there are differences in the Readthedocs build environment that can cause builds to
succeed locally but fail remotely. To help debug this, you can use the Readthedocs Docker container
(`readthedocs/build`) to perform the build. Example:
```bash
docker pull readthedocs/build
docker run --rm -ti \
  -v (pwd):/home/docs/project \
  readthedocs/build \
  /bin/bash -c \
  "cd /home/docs/project \
    && pip3 install '.[dev]' \
    && make -C docs html"
```

## Releases
Releases are built and published to pypi based on **git tags.**
[Milestones](https://github.com/JWCook/aiohttp-client-cache/milestones) will be used to track
progress on major and minor releases.


## Code Layout
Here is a brief overview of the main classes and modules:
* `session.CacheMixin`, `session.CachedSession`: A mixin and wrapper class, respectively, for `aiohttp.ClientSession`. There is little logic  here except wrapping `ClientSession._request()` with caching behavior.
* `response.CachedResponse`: A wrapper class built from an `aiohttp.ClientResponse`, with additional cache-related info. This is what is serialized and persisted to the cache.
* `backends.base.CacheBackend`: Most of the caching logic lives here, including saving and retriving responses, creating cache keys, expiration, etc. It contains two `BaseCache` objects for storing responses and redirects, respectively. By default this is just a non-persistent dict cache.
* `backends.base.BaseCache`: Base class for lower-level storage operations, overridden by individual backends.
* Other backend implementations in `backends.*`: A backend implementation subclasses `CacheBackend` (for higher-level operations), as well as `BaseCache` (for lower-level operations).

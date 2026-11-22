import os
from dataclasses import dataclass

import pydantic
import pytest
from hypothesis import settings, strategies
from hypothesis.provisional import urls
from starlette.testclient import TestClient

from rsserpent_rev.main import create_app
from rsserpent_rev.plugins.builtin import plugin as builtin_plugin

settings.register_profile("ci", deadline=500, max_examples=200)
settings.register_profile("default", max_examples=50)
settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "default"))
strategies.register_type_strategy(pydantic.EmailStr, strategies.emails())
strategies.register_type_strategy(pydantic.HttpUrl.__origin__, urls())  # type: ignore [attr-defined]


@dataclass
class Times:
    """Constants, specifying how many times a `hypothesis` test should run.

    * `ONCE` for tests that only need to be run once;
    * `SOME` for tests that are meant to be mildly tested;
    * `THOROUGH` for tests that are meant to be thoroughly tested.
    """

    ONCE = 1
    SOME = settings.default.max_examples // 3
    THOROUGH = settings.default.max_examples


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Share one test client across the whole module with `pytest.fixture`."""
    return TestClient(create_app([builtin_plugin]), backend_options={"use_uvloop": True})


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--live", action="store_true", help="Run tests that need the network or a browser.")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--live"):
        skip_live = pytest.mark.skip(reason="requires --live")
        for item in items:
            if item.get_closest_marker("live") is not None:
                item.add_marker(skip_live)

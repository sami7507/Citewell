"""Shared pytest configuration (import paths are set in pytest.ini)."""

import os

import pytest

from citewell import config


@pytest.fixture(autouse=True)
def _isolate_environment_and_config():
    """
    Give every test a clean environment and configuration.

    Some tests deliberately write settings into os.environ (for example the secrets-bridging
    test sets GROQ_MODEL). Because config.reload_from_env() copies the environment into the
    config module, such a write would otherwise leak into later tests, including the live API
    tests, which would then call a model that does not exist.
    """
    saved_environment = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved_environment)
    config.reload_from_env()

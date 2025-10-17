"""Pytest configuration and fixtures."""

import pytest
import os


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    # Set dummy AWS credentials for tests that don't actually use them
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "test_key_id")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test_secret_key")
    os.environ.setdefault("AWS_REGION", "us-east-1")

    # INDRA settings
    os.environ.setdefault("INDRA_BASE_URL", "https://network.indra.bio")
    os.environ.setdefault("INDRA_TIMEOUT", "30")

    yield

    # Cleanup if needed

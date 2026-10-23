from types import SimpleNamespace
import shutil
import tempfile
from pathlib import Path

import pytest

from backend.app.main import app, current_local_user


@pytest.fixture
def local_test_dir():
    """Create test artifacts inside the writable checkout, not the OS sandbox temp path."""
    root = Path(__file__).resolve().parents[2] / ".test-tmp"
    root.mkdir(exist_ok=True)
    directory = tempfile.mkdtemp(dir=root)
    try:
        yield directory
    finally:
        shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture(autouse=True)
def default_admin_for_existing_api_tests(request):
    """Keep existing feature API tests authenticated as an administrator.

    Authentication-specific tests clear this override to exercise the real flow.
    """
    if request.fspath.basename == "test_auth.py":
        app.dependency_overrides.clear()
        yield
        app.dependency_overrides.clear()
        return
    app.dependency_overrides[current_local_user] = lambda: SimpleNamespace(
        id="test-admin", username="test-admin", role="admin", is_active=True
    )
    yield
    app.dependency_overrides.clear()

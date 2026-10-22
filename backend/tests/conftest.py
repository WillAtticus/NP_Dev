from types import SimpleNamespace

import pytest

from backend.app.main import app, current_local_user


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

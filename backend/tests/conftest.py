"""pytest / Django test configuration."""
import django
import pytest
from django.test.utils import setup_test_environment

# pytest-django handles DJANGO_SETTINGS_MODULE via pytest.ini


@pytest.fixture(scope="session")
def django_db_setup():
    """Use the default DB; PostGIS extensions must be present."""


@pytest.fixture
def hex_cell(db):
    from tests.factories import HexCellFactory
    return HexCellFactory()


@pytest.fixture
def user(db):
    from tests.factories import UserFactory
    return UserFactory()

import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from movie_lottery import create_app
from movie_lottery.models import LibraryMovie, PollVoterProfile
from movie_lottery.utils import helpers


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'false')
    application = create_app()
    application.config['TESTING'] = True
    ctx = application.app_context()
    ctx.push()

    yield application

    ctx.pop()


def test_library_route_falls_back_to_added_at(app, monkeypatch):
    order_calls = []

    query_mock = MagicMock()

    def order_by_side_effect(column):
        order_calls.append(column)
        if len(order_calls) == 1:
            raise OperationalError("stmt", {}, Exception("fail"))
        result = MagicMock()
        result.all.return_value = []
        return result

    query_mock.order_by.side_effect = order_by_side_effect
    monkeypatch.setattr(LibraryMovie, 'query', query_mock)

    client = app.test_client()
    response = client.get('/library')

    assert response.status_code == 200
    assert len(order_calls) == 2
    assert order_calls[0].element.name == 'bumped_at'
    assert order_calls[1].element.name == 'added_at'


def test_ensure_voter_profile_returns_fallback_when_table_missing(app, monkeypatch):
    class BrokenQuery:
        def get(self, _token):
            raise OperationalError("stmt", {}, Exception("missing"))

    monkeypatch.setattr(PollVoterProfile, 'query', BrokenQuery())

    profile = helpers.ensure_voter_profile('token-123', device_label='Device 1')

    assert profile.token == 'token-123'
    assert profile.total_points == 0
    assert getattr(profile, '_is_fallback', False) is True


def test_change_voter_points_balance_skips_db_when_profiles_missing(app, monkeypatch):
    class BrokenQuery:
        def get(self, _token):
            raise OperationalError("stmt", {}, Exception("missing"))

    monkeypatch.setattr(PollVoterProfile, 'query', BrokenQuery())

    def fail_flush():
        raise AssertionError('flush should not be called for fallback profiles')

    monkeypatch.setattr(helpers.db.session, 'flush', fail_flush)

    balance = helpers.change_voter_points_balance('token-xyz', 5)

    assert balance == 5

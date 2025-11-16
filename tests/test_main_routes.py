import os
import sys
import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from movie_lottery import create_app, db
from movie_lottery.models import LibraryMovie, Poll, PollVoterProfile, Vote
from movie_lottery.utils import helpers
from movie_lottery.routes import api_routes


def _build_movie(name, **extra):
    payload = {
        'name': name,
        'year': extra.pop('year', '2024'),
    }
    payload.update(extra)
    return payload


def _create_poll_via_api(client, movies, token=None):
    if token:
        client.set_cookie('poll_creator_token', token)
    return client.post('/api/polls/create', json={'movies': movies})


def _add_vote_for_poll(poll, voter_suffix='1'):
    voter_token = f'voter-{voter_suffix}'
    profile = PollVoterProfile(token=voter_token, total_points=0)
    db.session.add(profile)
    db.session.flush()
    movie_id = poll.movies[0].id
    db.session.add(Vote(poll_id=poll.id, movie_id=movie_id, voter_token=voter_token, points_awarded=0))
    db.session.commit()


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('WERKZEUG_RUN_MAIN', 'false')
    db_fd, db_path = tempfile.mkstemp(prefix='movie-lottery-tests-', suffix='.db')
    os.close(db_fd)
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{db_path}')
    application = create_app()
    application.config['TESTING'] = True
    ctx = application.app_context()
    ctx.push()
    db.create_all()

    yield application

    db.session.remove()
    db.drop_all()
    ctx.pop()
    os.remove(db_path)


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


def test_create_poll_sets_creator_cookie(app):
    client = app.test_client()

    response = _create_poll_via_api(client, [_build_movie('One'), _build_movie('Two')])

    assert response.status_code == 200
    data = response.get_json()
    poll = Poll.query.get(data['poll_id'])
    assert poll is not None

    cookie = client.get_cookie('poll_creator_token')
    assert cookie is not None
    assert cookie.value == poll.creator_token


def test_create_poll_reuses_existing_creator_token(app):
    client = app.test_client()
    existing_token = 'a' * 32

    response = _create_poll_via_api(client, [_build_movie('One'), _build_movie('Two')], token=existing_token)

    assert response.status_code == 200
    data = response.get_json()
    poll = Poll.query.get(data['poll_id'])
    assert poll.creator_token == existing_token

    cookie = client.get_cookie('poll_creator_token')
    assert cookie is not None
    assert cookie.value == existing_token


def test_create_poll_requires_minimum_movies(app):
    client = app.test_client()

    response = client.post('/api/polls/create', json={'movies': [_build_movie('Solo')]})

    assert response.status_code == 400
    data = response.get_json()
    assert 'Нужно добавить хотя бы два фильма' in data['error']


def test_create_poll_persists_extended_payload(app):
    client = app.test_client()

    movies = [
        _build_movie(
            'Movie A',
            kinopoisk_id=123,
            search_name='movie-a',
            poster='poster-url',
            description='desc',
            rating_kp=7.5,
            genres='Drama',
            countries='RU'
        ),
        _build_movie('Movie B')
    ]

    response = _create_poll_via_api(client, movies)

    assert response.status_code == 200
    data = response.get_json()
    poll = Poll.query.get(data['poll_id'])
    assert poll is not None
    first_movie = poll.movies[0]
    assert first_movie.kinopoisk_id == 123
    assert first_movie.search_name == 'movie-a'
    assert first_movie.poster == 'poster-url'
    assert first_movie.genres == 'Drama'
    assert first_movie.countries == 'RU'


def test_get_my_polls_returns_only_creator_polls(app):
    client = app.test_client()

    token_a = 'a' * 32
    token_b = 'b' * 32

    response_a = _create_poll_via_api(client, [_build_movie('One'), _build_movie('Two')], token=token_a)
    response_b = _create_poll_via_api(client, [_build_movie('Three'), _build_movie('Four')], token=token_b)

    poll_a = Poll.query.get(response_a.get_json()['poll_id'])
    poll_b = Poll.query.get(response_b.get_json()['poll_id'])
    _add_vote_for_poll(poll_a, 'a')
    _add_vote_for_poll(poll_b, 'b')

    client.set_cookie('poll_creator_token', token_a)
    response = client.get('/api/polls/my-polls')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data['polls']) == 1
    assert data['polls'][0]['poll_id'] == poll_a.id


def test_voter_stats_returns_json_on_missing_tables(app, monkeypatch):
    class BrokenQuery:
        def order_by(self, *_args, **_kwargs):
            raise OperationalError("stmt", {}, Exception("missing table"))

    monkeypatch.setattr(api_routes.PollVoterProfile, 'query', BrokenQuery())

    recovery_called = {'called': False}

    def fake_ensure_tables():
        recovery_called['called'] = True

    monkeypatch.setattr(api_routes, 'ensure_poll_tables', fake_ensure_tables)

    client = app.test_client()
    response = client.get('/api/polls/voter-stats')

    assert response.status_code == 503
    data = response.get_json()
    assert data['error']
    assert recovery_called['called'] is True

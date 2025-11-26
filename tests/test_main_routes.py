import os
import sys
import os
import calendar
import shutil
import sys
import tempfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy import inspect, text
from datetime import datetime, time, timedelta
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


def _align_to_end_of_day(dt):
    return datetime.combine(dt.date(), time(23, 59, 59))


def _add_months(dt, months):
    total_months = dt.month - 1 + months
    year = dt.year + total_months // 12
    month = total_months % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def _calculate_expected_ban_until(base_time, months):
    return _add_months(_align_to_end_of_day(base_time), months)


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
    db.engine.dispose()
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


def test_register_user_id_returns_points_totals(app):
    client = app.test_client()
    existing_token = 'register-token-1'
    db.session.add(
        PollVoterProfile(
            token=existing_token,
            total_points=12,
            points_accrued_total=50,
        )
    )
    db.session.commit()

    client.set_cookie(api_routes.VOTER_TOKEN_COOKIE, existing_token)
    response = client.post('/api/polls/auth/register', json={'user_id': 'tester'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['voter_token'] == existing_token
    assert payload['points_balance'] == 12
    assert payload['points_earned_total'] == 50
    assert payload['points_accrued_total'] == 50

    refreshed = PollVoterProfile.query.filter_by(user_id='tester').first()
    assert refreshed is not None
    assert refreshed.token == existing_token


def test_login_user_id_returns_points_totals(app):
    client = app.test_client()
    profile = PollVoterProfile(
        token='login-token-1',
        user_id='login-user',
        total_points=7,
        points_accrued_total=33,
    )
    db.session.add(profile)
    db.session.commit()

    response = client.post('/api/polls/auth/login', json={'user_id': 'login-user'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['voter_token'] == 'login-token-1'
    assert payload['points_balance'] == 7
    assert payload['points_earned_total'] == 33
    assert payload['points_accrued_total'] == 33


def test_ensure_voter_profile_columns_backfill_points_accrued(app):
    db.session.execute(text('ALTER TABLE poll_voter_profile DROP COLUMN points_accrued_total'))
    db.session.commit()

    engine = db.engine
    before_columns = {col['name'] for col in inspect(engine).get_columns('poll_voter_profile')}
    assert 'points_accrued_total' not in before_columns

    created = helpers.ensure_poll_voter_user_id_column()
    assert created is True

    after_columns = {col['name'] for col in inspect(engine).get_columns('poll_voter_profile')}
    assert 'points_accrued_total' in after_columns

    db.session.add(PollVoterProfile(token='restored-token'))
    db.session.commit()

    restored = PollVoterProfile.query.get('restored-token')
    assert restored is not None
    assert (restored.points_accrued_total or 0) == 0


def test_ensure_poll_movie_points_column_backfills_missing_column(app):
    client = app.test_client()
    response = _create_poll_via_api(client, [_build_movie('One'), _build_movie('Two')])
    assert response.status_code == 200

    db.session.execute(text('ALTER TABLE poll_movie DROP COLUMN points'))
    db.session.commit()

    engine = db.engine
    before_columns = {col['name'] for col in inspect(engine).get_columns('poll_movie')}
    assert 'points' not in before_columns

    created = helpers.ensure_poll_movie_points_column()
    assert created is True

    after_columns = {col['name'] for col in inspect(engine).get_columns('poll_movie')}
    assert 'points' in after_columns

    db.session.expire_all()
    poll = Poll.query.get(response.get_json()['poll_id'])
    assert poll is not None
    assert all(movie.points == 1 for movie in poll.movies)


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


def test_create_poll_rejects_banned_library_movies(app):
    client = app.test_client()

    banned = LibraryMovie(
        name='Banned Movie',
        year='2024',
        badge='ban',
        ban_until=datetime.utcnow() + timedelta(days=1),
    )
    db.session.add(banned)
    db.session.commit()

    response = _create_poll_via_api(client, [
        {"id": banned.id, "name": banned.name, "year": banned.year},
        _build_movie('Allowed Movie'),
    ])

    assert response.status_code == 422
    assert 'бане' in response.get_json()['error']


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


def test_get_poll_restores_points_for_existing_token(app):
    client = app.test_client()

    primary_response = _create_poll_via_api(client, [_build_movie('One'), _build_movie('Two')])
    secondary_response = _create_poll_via_api(client, [_build_movie('Three'), _build_movie('Four')])

    primary_poll_id = primary_response.get_json()['poll_id']
    primary_poll = Poll.query.get(primary_poll_id)
    secondary_poll = Poll.query.get(secondary_response.get_json()['poll_id'])

    voter_token = 'abcd' * 8

    profile = PollVoterProfile(
        token=voter_token,
        total_points=10,
        points_accrued_total=7,
    )
    db.session.add(profile)
    db.session.add(
        Vote(
            poll_id=primary_poll.id,
            movie_id=primary_poll.movies[0].id,
            voter_token=voter_token,
            points_awarded=3,
        )
    )
    db.session.add(
        Vote(
            poll_id=secondary_poll.id,
            movie_id=secondary_poll.movies[0].id,
            voter_token=voter_token,
            points_awarded=4,
        )
    )
    db.session.commit()

    client.set_cookie(api_routes.VOTER_TOKEN_COOKIE, voter_token)
    initial_response = client.get(f'/api/polls/{primary_poll_id}')
    assert initial_response.status_code == 200
    initial_payload = initial_response.get_json()
    assert initial_payload['points_earned_total'] == 7

    client.delete_cookie(api_routes.VOTER_TOKEN_COOKIE)
    client.delete_cookie(api_routes.VOTER_USER_ID_COOKIE)

    response = client.get(
        f'/api/polls/{primary_poll_id}',
        headers={api_routes.VOTER_TOKEN_HEADER: voter_token},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['points_earned_total'] == 7

    restored_cookie = client.get_cookie(api_routes.VOTER_TOKEN_COOKIE)
    assert restored_cookie is not None
    assert restored_cookie.value == voter_token


def test_points_total_survives_logout_with_same_token(app):
    client = app.test_client()

    polls = []
    for idx in range(4):
        response = _create_poll_via_api(
            client,
            [_build_movie(f'Movie {idx}A'), _build_movie(f'Movie {idx}B')],
        )
        polls.append(Poll.query.get(response.get_json()['poll_id']))

    voter_token = '1234abcd' * 4

    db.session.add(
        PollVoterProfile(
            token=voter_token,
            total_points=25,
            points_accrued_total=sum(range(1, 5)),
        )
    )
    for idx, poll in enumerate(polls, start=1):
        db.session.add(
            Vote(
                poll_id=poll.id,
                movie_id=poll.movies[0].id,
                voter_token=voter_token,
                points_awarded=idx,
            )
        )
    db.session.commit()

    client.set_cookie(api_routes.VOTER_TOKEN_COOKIE, voter_token)

    initial_response = client.get(f'/api/polls/{polls[0].id}')
    assert initial_response.status_code == 200
    initial_payload = initial_response.get_json()
    assert initial_payload['points_earned_total'] == sum(range(1, 5))

    logout_response = client.post('/api/polls/auth/logout')
    assert logout_response.status_code == 200
    logout_payload = logout_response.get_json()
    assert logout_payload['voter_token'] == voter_token
    assert logout_payload['rotated_token'] is None

    post_logout_response = client.get(
        f'/api/polls/{polls[0].id}',
        headers={api_routes.VOTER_TOKEN_HEADER: voter_token},
    )

    assert post_logout_response.status_code == 200
    post_logout_payload = post_logout_response.get_json()
    assert post_logout_payload['voter_token'] == voter_token
    assert post_logout_payload['points_earned_total'] == sum(range(1, 5))


def test_get_poll_uses_requested_token_history_with_user_id_cookie(app):
    client = app.test_client()

    response = _create_poll_via_api(client, [_build_movie('First'), _build_movie('Second')])
    poll_id = response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)

    legacy_token = 'b' * 32
    user_id = 'poll-user-1'
    new_token = 'c' * 32

    db.session.add(
        PollVoterProfile(
            token=legacy_token,
            total_points=0,
            points_accrued_total=5,
        )
    )
    db.session.add(
        Vote(
            poll_id=poll.id,
            movie_id=poll.movies[0].id,
            voter_token=legacy_token,
            points_awarded=5,
        )
    )
    db.session.add(
        PollVoterProfile(
            token=new_token,
            total_points=0,
            user_id=user_id,
            points_accrued_total=5,
        )
    )
    db.session.commit()

    client.set_cookie(api_routes.VOTER_USER_ID_COOKIE, user_id)
    client.set_cookie(api_routes.VOTER_TOKEN_COOKIE, new_token)

    response = client.get(
        f'/api/polls/{poll_id}',
        query_string={'voter_token': legacy_token},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['voter_token'] == new_token
    assert payload['points_earned_total'] == 5


def test_get_poll_uses_recent_device_history_when_cookie_missing(app):
    client = app.test_client()

    response = _create_poll_via_api(client, [_build_movie('Old'), _build_movie('New')])
    poll_id = response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)

    legacy_token = 'd' * 32
    device_label = 'device-xyz'

    db.session.add(
        PollVoterProfile(
            token=legacy_token,
            total_points=0,
            points_accrued_total=6,
            device_label=device_label,
        )
    )
    db.session.add(
        Vote(
            poll_id=poll.id,
            movie_id=poll.movies[0].id,
            voter_token=legacy_token,
            points_awarded=6,
        )
    )
    db.session.commit()

    poll_response = client.get(
        f'/api/polls/{poll_id}',
        headers={'X-Device-Label': device_label},
    )

    assert poll_response.status_code == 200

    payload = poll_response.get_json()
    assert payload['voter_token'] == legacy_token
    assert payload['points_earned_total'] == 6


def test_poll_ban_sets_forced_winner(app):
    client = app.test_client()

    create_response = _create_poll_via_api(client, [
        _build_movie('Movie A'),
        _build_movie('Movie B'),
    ])

    poll_id = create_response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    other_movie = poll.movies[1]
    target_movie = poll.movies[0]

    voter_token = 'ban-voter-token'
    client.set_cookie('voter_token', voter_token)
    db.session.add(PollVoterProfile(token=voter_token, total_points=5))
    db.session.commit()

    ban_response = client.post(
        f'/api/polls/{poll_id}/ban',
        json={'movie_id': target_movie.id, 'months': 2},
    )

    assert ban_response.status_code == 200
    payload = ban_response.get_json()
    assert payload['closed_by_ban'] is True
    assert payload['points_balance'] == 3
    assert payload['forced_winner']['id'] == other_movie.id

    db.session.expire_all()
    poll = Poll.query.get(poll_id)
    assert poll.forced_winner_movie_id == other_movie.id
    assert poll.is_expired is True


def test_poll_ban_aligns_to_end_of_day(app):
    client = app.test_client()

    create_response = _create_poll_via_api(client, [
        _build_movie('Movie A'),
        _build_movie('Movie B'),
    ])

    poll_id = create_response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    target_movie = poll.movies[0]

    now_utc = datetime.utcnow()
    voter_token = 'ban-aligned'
    client.set_cookie('voter_token', voter_token)
    db.session.add(PollVoterProfile(token=voter_token, total_points=5))
    db.session.commit()

    months = 2

    response = client.post(
        f'/api/polls/{poll_id}/ban',
        json={'movie_id': target_movie.id, 'months': months},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ban_until = datetime.fromisoformat(payload['ban_until'])

    expected_end = _calculate_expected_ban_until(now_utc, months)

    assert ban_until == expected_end


def test_poll_ban_extension_aligns_to_end_of_day(app):
    client = app.test_client()

    create_response = _create_poll_via_api(client, [
        _build_movie('Movie A'),
        _build_movie('Movie B'),
    ])

    poll_id = create_response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    target_movie = poll.movies[0]

    base_ban_until = datetime.utcnow() + timedelta(hours=12)
    target_movie.ban_until = base_ban_until
    db.session.commit()

    voter_token = 'extended-ban'
    client.set_cookie('voter_token', voter_token)
    db.session.add(PollVoterProfile(token=voter_token, total_points=5))
    db.session.commit()

    months = 2

    response = client.post(
        f'/api/polls/{poll_id}/ban',
        json={'movie_id': target_movie.id, 'months': months},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ban_until = datetime.fromisoformat(payload['ban_until'])

    expected_end = _calculate_expected_ban_until(base_ban_until, months)

    assert ban_until == expected_end


def test_poll_ban_updates_library_movie(app):
    client = app.test_client()

    library_movie = LibraryMovie(
        kinopoisk_id=321,
        name='Library Match',
        year='2024',
        badge='watchlist',
    )
    db.session.add(library_movie)
    db.session.commit()

    create_response = _create_poll_via_api(client, [
        _build_movie('Library Match', kinopoisk_id=321, year='2024'),
        _build_movie('Other Movie'),
    ])

    poll_id = create_response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    target_movie = poll.movies[0]

    voter_token = 'library-ban'
    client.set_cookie('voter_token', voter_token)
    db.session.add(PollVoterProfile(token=voter_token, total_points=10))
    db.session.commit()

    response = client.post(
        f'/api/polls/{poll_id}/ban',
        json={'movie_id': target_movie.id, 'months': 3},
    )

    assert response.status_code == 200
    payload = response.get_json()
    library_payload = payload.get('library_ban')

    assert library_payload is not None
    assert library_payload['badge'] == 'ban'
    assert library_payload['ban_cost'] == 3
    assert library_payload['ban_applied_by'] == 'poll-ban'

    db.session.expire_all()
    updated_library_movie = LibraryMovie.query.filter_by(kinopoisk_id=321).first()
    assert updated_library_movie.badge == 'ban'
    assert updated_library_movie.ban_cost == 3
    assert updated_library_movie.ban_applied_by == 'poll-ban'
    assert updated_library_movie.ban_until is not None


def test_library_ban_resets_after_expiry(app):
    client = app.test_client()

    expired_ban = LibraryMovie(
        name='Expired Ban',
        year='2023',
        badge='ban',
        ban_until=datetime.utcnow() - timedelta(hours=1),
    )
    db.session.add(expired_ban)
    db.session.commit()

    response = client.get('/api/library')

    assert response.status_code == 200
    payload = response.get_json()
    movie_payload = next((m for m in payload['movies'] if m['name'] == 'Expired Ban'), None)

    assert movie_payload is not None
    assert movie_payload['badge'] == 'watchlist'
    assert movie_payload['ban_until'] is None

    db.session.expire_all()
    refreshed_movie = LibraryMovie.query.filter_by(name='Expired Ban').first()
    assert refreshed_movie.badge == 'watchlist'
    assert refreshed_movie.ban_until is None


def test_library_badge_ban_aligns_to_end_of_day(app):
    client = app.test_client()

    movie = LibraryMovie(
        name='Manual Ban',
        year='2024',
        badge='watchlist',
    )
    db.session.add(movie)
    db.session.commit()

    now_utc = datetime.utcnow()

    months = 1

    response = client.put(
        f'/api/library/{movie.id}/badge',
        json={'badge': 'ban', 'ban_duration_months': months},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ban_until = datetime.fromisoformat(payload['ban_until'])

    expected_end = _calculate_expected_ban_until(now_utc, months)
    assert ban_until == expected_end


def test_library_badge_accepts_ban_until_and_aligns(app):
    client = app.test_client()

    movie = LibraryMovie(
        name='Ban Until',
        year='2024',
        badge='watchlist',
    )
    db.session.add(movie)
    db.session.commit()

    target_until = datetime.utcnow() + timedelta(days=3, hours=5)

    response = client.put(
        f'/api/library/{movie.id}/badge',
        json={'badge': 'ban', 'ban_until': target_until.isoformat()},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ban_until = datetime.fromisoformat(payload['ban_until'])

    expected_end = datetime.combine(target_until.date(), time(23, 59, 59))
    assert ban_until == expected_end


def test_library_badge_ban_extends_from_existing_ban(app):
    client = app.test_client()

    base_ban_until = datetime.utcnow() + timedelta(hours=12)
    movie = LibraryMovie(
        name='Extended Ban',
        year='2024',
        badge='ban',
        ban_until=base_ban_until,
    )
    db.session.add(movie)
    db.session.commit()

    months = 1

    response = client.put(
        f'/api/library/{movie.id}/badge',
        json={'badge': 'ban', 'ban_duration_months': months},
    )

    assert response.status_code == 200
    payload = response.get_json()
    ban_until = datetime.fromisoformat(payload['ban_until'])

    expected_end = _calculate_expected_ban_until(base_ban_until, months)
    assert ban_until == expected_end


def test_cannot_ban_last_movie(app):
    client = app.test_client()

    create_response = _create_poll_via_api(client, [
        _build_movie('Solo A'),
        _build_movie('Solo B'),
    ])

    poll_id = create_response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    first_movie = poll.movies[0]
    second_movie = poll.movies[1]

    first_movie.ban_until = datetime.utcnow() + timedelta(days=1)
    db.session.commit()

    voter_token = 'limited-bans'
    client.set_cookie('voter_token', voter_token)
    db.session.add(PollVoterProfile(token=voter_token, total_points=10))
    db.session.commit()

    response = client.post(
        f'/api/polls/{poll_id}/ban',
        json={'movie_id': second_movie.id, 'months': 1},
    )

    assert response.status_code == 409
    assert 'Нельзя забанить последний фильм' in response.get_json()['error']


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


def test_create_poll_normalizes_movie_points(app):
    client = app.test_client()

    movies = [
        _build_movie('Low', points=-5),
        _build_movie('Default', points='nan'),
        _build_movie('High', points=5000),
    ]

    response = _create_poll_via_api(client, movies)
    assert response.status_code == 200
    poll = Poll.query.get(response.get_json()['poll_id'])

    assert poll is not None
    assert [movie.points for movie in poll.movies] == [0, 1, 999]


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


def test_voter_stats_filters_by_user_id(app):
    client = app.test_client()

    profile_a = PollVoterProfile(token='token-a', user_id='alice')
    profile_b = PollVoterProfile(token='token-b', user_id='bob')
    db.session.add_all([profile_a, profile_b])
    db.session.commit()

    response = client.get('/api/polls/voter-stats', query_string={'user_id': 'ali'})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['total'] == 1
    assert payload['items'][0]['voter_token'] == 'token-a'
    assert payload['items'][0]['user_id'] == 'alice'
    assert payload['items'][0]['points_accrued_total'] == 0


def test_vote_in_poll_awards_movie_points(app):
    client = app.test_client()

    movies = [
        _build_movie('Winner', points=7),
        _build_movie('Other', points=1),
    ]

    response = _create_poll_via_api(client, movies)
    poll_id = response.get_json()['poll_id']
    poll = Poll.query.get(poll_id)
    movie_id = poll.movies[0].id

    vote_response = client.post(f'/api/polls/{poll_id}/vote', json={'movie_id': movie_id})
    assert vote_response.status_code == 200

    payload = vote_response.get_json()
    assert payload['points_awarded'] == 7
    vote = Vote.query.filter_by(poll_id=poll_id).first()
    assert vote.points_awarded == 7

    profile = PollVoterProfile.query.first()
    assert profile.total_points == 7


def test_patch_device_label_updates_profile(app):
    client = app.test_client()
    token = 'device-token-1'
    profile = PollVoterProfile(token=token, device_label='Старое устройство', total_points=5)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/device-label',
        json={'device_label': '   Новая метка   '},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['device_label'] == 'Новая метка'
    assert payload['updated_at'] is not None

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.device_label == 'Новая метка'
    assert refreshed.updated_at is not None


def test_patch_device_label_allows_clearing_value(app):
    client = app.test_client()
    token = 'device-token-2'
    profile = PollVoterProfile(token=token, device_label='Для очистки')
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/device-label',
        json={'device_label': '   '},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['device_label'] is None

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.device_label is None


def test_patch_total_points_updates_profile(app):
    client = app.test_client()
    token = 'points-token-1'
    profile = PollVoterProfile(token=token, total_points=5)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/points',
        json={'total_points': 42},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['total_points'] == 42
    assert payload['updated_at'] is not None
    assert payload['points_accrued_total'] == 0

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.total_points == 42
    assert refreshed.updated_at is not None


def test_patch_points_accrued_total_updates_profile(app):
    client = app.test_client()
    token = 'accrued-token-1'
    profile = PollVoterProfile(token=token, total_points=5, points_accrued_total=10)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/points-accrued',
        json={'points_accrued_total': 123},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['points_accrued_total'] == 123
    assert payload['total_points'] == 5
    assert payload['updated_at'] is not None

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.points_accrued_total == 123
    assert refreshed.total_points == 5
    assert refreshed.updated_at is not None


def test_patch_points_accrued_total_validates_payload(app):
    client = app.test_client()
    token = 'accrued-token-2'
    profile = PollVoterProfile(token=token, points_accrued_total=7)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/points-accrued',
        json={'points_accrued_total': 'oops'},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert 'целым' in payload['error']

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.points_accrued_total == 7

def test_patch_total_points_validates_payload(app):
    client = app.test_client()
    token = 'points-token-2'
    profile = PollVoterProfile(token=token, total_points=7)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/points',
        json={'total_points': 'invalid'},
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert 'целым' in payload['error']

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.total_points == 7


def test_patch_user_id_updates_profile(app):
    client = app.test_client()
    token = 'user-token-1'
    profile = PollVoterProfile(token=token, user_id='old-id', device_label='device-1', total_points=3)
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/user-id',
        json={'user_id': '  new-id  '},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['user_id'] == 'new-id'
    assert payload['device_label'] == 'device-1'
    assert payload['total_points'] == 3
    assert payload['updated_at']

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.user_id == 'new-id'
    assert refreshed.updated_at is not None


def test_patch_user_id_allows_clearing_value(app):
    client = app.test_client()
    token = 'user-token-2'
    profile = PollVoterProfile(token=token, user_id='to-clear')
    db.session.add(profile)
    db.session.commit()

    response = client.patch(
        f'/api/polls/voter-stats/{token}/user-id',
        json={'user_id': None},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['user_id'] is None

    refreshed = PollVoterProfile.query.get(token)
    assert refreshed.user_id is None

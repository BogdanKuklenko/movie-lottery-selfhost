"""Add points_transaction table for detailed logging

Revision ID: f5g6h7i8j9k0
Revises: e2f3g4h5i6j7
Create Date: 2025-12-04 12:00:00.000000

=============================================================================
ОПИСАНИЕ МИГРАЦИИ (для коллег)
=============================================================================

Эта миграция создаёт таблицу `points_transaction` для детального логирования
всех операций с баллами пользователей.

ТАБЛИЦА points_transaction:
- id              : первичный ключ
- voter_token     : токен пользователя (связь с poll_voter_profile)
- transaction_type: тип операции ('vote', 'custom_vote', 'trailer', 'ban', 'admin')
- amount          : сумма изменения (+N = начисление, -N = списание)
- balance_before  : баланс ДО операции
- balance_after   : баланс ПОСЛЕ операции
- description     : текстовое описание операции
- movie_name      : название фильма (если применимо)
- poll_id         : ID опроса (если применимо)
- created_at      : время операции

ФУНКЦИЯ _backfill_transactions():
- Выполняется ОДИН РАЗ при применении миграции
- Переносит старые голосования из таблицы `vote` в `points_transaction`
- Вычисляет баланс накопительно по времени для каждого пользователя
- После применения миграции Alembic запоминает её в alembic_version
  и больше никогда не запустит повторно

ТИПЫ ТРАНЗАКЦИЙ:
- 'vote'        : обычное голосование (начисление баллов)
- 'custom_vote' : кастомный голос (списание баллов, points_awarded < 0)
- 'trailer'     : просмотр трейлера (списание) - только новые операции
- 'ban'         : бан фильма (списание) - только новые операции
- 'admin'       : ручное изменение админом

ВАЖНО: Списания за трейлеры и баны до этой миграции НЕ записывались,
поэтому их нет в истории. Только голосования можно восстановить.

=============================================================================
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f5g6h7i8j9k0'
down_revision = 'e2f3g4h5i6j7'
branch_labels = None
depends_on = None


def _backfill_transactions():
    """
    Переносит старые голосования из таблицы vote в points_transaction.
    
    ВЫПОЛНЯЕТСЯ ТОЛЬКО ОДИН РАЗ при первом применении миграции.
    Alembic запоминает версию в таблице alembic_version и не запускает повторно.
    
    Логика работы:
    1. Загружаем все голоса из таблицы vote с названиями фильмов из poll_movie
    2. Сортируем по (voter_token, voted_at) для правильного расчёта баланса
    3. Для каждого пользователя вычисляем баланс накопительно:
       - balance_before = текущий накопленный баланс
       - balance_after = balance_before + points_awarded
    4. Определяем тип транзакции:
       - points_awarded >= 0 → 'vote' (обычное голосование)
       - points_awarded < 0  → 'custom_vote' (кастомный голос со списанием)
    5. Вставляем записи в points_transaction
    
    ОГРАНИЧЕНИЯ:
    - Баланс вычисляется приблизительно (накопительно по голосованиям)
    - Списания за трейлеры и баны до миграции не восстанавливаются
    """
    bind = op.get_bind()
    metadata = sa.MetaData()

    # Проверяем что нужные таблицы существуют
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()
    
    if 'vote' not in table_names or 'poll_movie' not in table_names:
        print("[backfill] Таблицы vote или poll_movie не найдены, пропускаем backfill")
        return
    
    if 'points_transaction' not in table_names:
        print("[backfill] Таблица points_transaction не создана, пропускаем backfill")
        return

    # Загружаем таблицы через reflection
    vote_table = sa.Table('vote', metadata, autoload_with=bind)
    poll_movie_table = sa.Table('poll_movie', metadata, autoload_with=bind)
    transaction_table = sa.Table('points_transaction', metadata, autoload_with=bind)

    # Проверяем что в points_transaction ещё нет данных (защита от повторного запуска)
    existing_count = bind.execute(
        sa.select(sa.func.count()).select_from(transaction_table)
    ).scalar()
    
    if existing_count > 0:
        print(f"[backfill] В points_transaction уже есть {existing_count} записей, пропускаем backfill")
        return

    # Получаем все голоса с названиями фильмов, сортируем по токену и времени
    # Это важно для правильного расчёта накопительного баланса
    votes_query = sa.select(
        vote_table.c.voter_token,
        vote_table.c.poll_id,
        vote_table.c.points_awarded,
        vote_table.c.voted_at,
        poll_movie_table.c.name.label('movie_name')
    ).select_from(
        vote_table.join(
            poll_movie_table, 
            vote_table.c.movie_id == poll_movie_table.c.id
        )
    ).order_by(
        vote_table.c.voter_token,  # Группируем по пользователю
        vote_table.c.voted_at      # Сортируем по времени для расчёта баланса
    )

    votes = bind.execute(votes_query).fetchall()

    if not votes:
        print("[backfill] Нет голосов для переноса")
        return

    print(f"[backfill] Найдено {len(votes)} голосов для переноса в points_transaction")

    # Формируем записи для вставки
    # Для каждого пользователя отслеживаем накопительный баланс
    current_token = None
    running_balance = 0
    payload = []

    for vote in votes:
        # При смене пользователя сбрасываем баланс
        if vote.voter_token != current_token:
            current_token = vote.voter_token
            running_balance = 0

        # Вычисляем баланс до и после операции
        balance_before = running_balance
        balance_after = running_balance + (vote.points_awarded or 0)
        running_balance = balance_after

        # Определяем тип транзакции по знаку суммы
        # points_awarded >= 0 → обычное голосование (начисление)
        # points_awarded < 0  → кастомный голос (списание)
        if (vote.points_awarded or 0) >= 0:
            tx_type = 'vote'
            description = f"Голосование за «{vote.movie_name}»"
        else:
            tx_type = 'custom_vote'
            description = f"Кастомный голос за «{vote.movie_name}»"

        payload.append({
            'voter_token': vote.voter_token,
            'transaction_type': tx_type,
            'amount': vote.points_awarded or 0,
            'balance_before': balance_before,
            'balance_after': balance_after,
            'description': description,
            'movie_name': vote.movie_name,
            'poll_id': vote.poll_id,
            'created_at': vote.voted_at,
        })

    # Вставляем все записи одним запросом
    if payload:
        bind.execute(transaction_table.insert(), payload)
        print(f"[backfill] Успешно перенесено {len(payload)} транзакций в points_transaction")


def upgrade():
    """
    Создаёт таблицу points_transaction и переносит старые голосования.
    
    Порядок выполнения:
    1. Проверяем что таблицы ещё нет (идемпотентность)
    2. Создаём таблицу points_transaction
    3. Создаём индексы для быстрого поиска
    4. Вызываем _backfill_transactions() для переноса старых данных
    
    После выполнения Alembic записывает revision в alembic_version
    и миграция больше никогда не запустится повторно.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Идемпотентность: если таблица уже существует, пропускаем
    if 'points_transaction' in inspector.get_table_names():
        print("[upgrade] Таблица points_transaction уже существует, пропускаем создание")
        # Но всё равно пробуем backfill (вдруг таблица пустая)
        _backfill_transactions()
        return

    # Создаём таблицу points_transaction
    op.create_table(
        'points_transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('voter_token', sa.String(length=64), nullable=False),
        sa.Column('transaction_type', sa.String(length=30), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('balance_before', sa.Integer(), nullable=False),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('movie_name', sa.String(length=200), nullable=True),
        sa.Column('poll_id', sa.String(length=8), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )

    # Создаем индексы для быстрого поиска по частым запросам
    op.create_index('ix_points_transaction_voter_token', 'points_transaction', ['voter_token'], unique=False)
    op.create_index('ix_points_transaction_created_at', 'points_transaction', ['created_at'], unique=False)
    op.create_index('ix_points_transaction_type', 'points_transaction', ['transaction_type'], unique=False)

    # Переносим старые голосования из vote в points_transaction
    # Это выполнится только один раз при первом применении миграции
    _backfill_transactions()


def downgrade():
    """
    Откатывает миграцию: удаляет таблицу points_transaction.
    
    ВНИМАНИЕ: При откате все данные транзакций будут потеряны!
    Голосования в таблице vote останутся нетронутыми.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'points_transaction' not in inspector.get_table_names():
        print("[downgrade] Таблица points_transaction не существует, пропускаем")
        return

    # Удаляем индексы
    op.drop_index('ix_points_transaction_type', table_name='points_transaction')
    op.drop_index('ix_points_transaction_created_at', table_name='points_transaction')
    op.drop_index('ix_points_transaction_voter_token', table_name='points_transaction')
    
    # Удаляем таблицу
    op.drop_table('points_transaction')


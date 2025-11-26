"""merge poll heads including points accrued

Revision ID: 25ef3a9435e3
Revises: 1f4d79d2663e, 7b4ec1771b6a, 8d0a5cc20edd, c65cc8c663a8
Create Date: 2025-11-26 09:28:09.236078

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25ef3a9435e3'
down_revision = ('1f4d79d2663e', '7b4ec1771b6a', '8d0a5cc20edd', 'c65cc8c663a8')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass

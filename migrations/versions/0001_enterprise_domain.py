"""Create the initial tenant-aware enterprise domain.

Revision ID: 0001_enterprise_domain
Revises:
"""

from alembic import op

from src.enterprise.models import Base

revision = "0001_enterprise_domain"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The initial revision is generated from the reviewed SQLAlchemy metadata.
    # Later revisions must use explicit Alembic operations for safe evolution.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())

"""initial_schema: 与 SQLAlchemy models 对齐的首版表结构

Revision ID: 001_initial
Revises:
Create Date: 2026-03-28

升级时使用当前 metadata 创建全部表；降级时删除全部表。
生产环境后续变更请使用 autogenerate 生成增量迁移。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.database import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

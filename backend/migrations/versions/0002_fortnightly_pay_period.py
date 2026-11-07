"""Support fortnightly salary profiles.

Revision ID: 0002_fortnightly
Revises: 0001_initial_double_entry
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_fortnightly"
down_revision = "0001_initial_double_entry"
branch_labels = None
depends_on = None


def upgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TYPE payperiod ADD VALUE IF NOT EXISTS 'FORTNIGHTLY'")
    else:
        with op.batch_alter_table("salary_profiles") as batch:
            batch.alter_column("pay_period", existing_type=sa.String(7), type_=sa.String(11))


def downgrade():
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT COUNT(*) FROM salary_profiles WHERE pay_period = 'FORTNIGHTLY'")
    ).scalar_one():
        raise RuntimeError("Remove fortnightly profiles before downgrading")
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE payperiod RENAME TO payperiod_old")
        op.execute("CREATE TYPE payperiod AS ENUM ('MONTHLY', 'ANNUAL')")
        op.execute(
            "ALTER TABLE salary_profiles ALTER COLUMN pay_period "
            "TYPE payperiod USING pay_period::text::payperiod"
        )
        op.execute("DROP TYPE payperiod_old")
    else:
        with op.batch_alter_table("salary_profiles") as batch:
            batch.alter_column("pay_period", existing_type=sa.String(11), type_=sa.String(7))

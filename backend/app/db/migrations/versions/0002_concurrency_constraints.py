"""race-safe unique constraints for concurrent same-pile runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-06

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Lets deliverable-section writes use INSERT ... ON CONFLICT DO UPDATE —
    # atomic at the database level, closing the read-then-write race that two
    # concurrent runs on the same pile would otherwise hit.
    op.create_unique_constraint(
        "uq_deliverable_sections_pile_section", "deliverable_sections", ["pile_id", "section_key"]
    )
    # Same idea for conflicts: lets detect_conflicts use INSERT ... ON CONFLICT
    # DO NOTHING instead of an app-level check-then-insert dedup, which had
    # the same race.
    op.create_unique_constraint("uq_conflicts_pile_description", "conflicts", ["pile_id", "description"])


def downgrade() -> None:
    op.drop_constraint("uq_conflicts_pile_description", "conflicts", type_="unique")
    op.drop_constraint("uq_deliverable_sections_pile_section", "deliverable_sections", type_="unique")

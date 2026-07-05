"""Single-user helpers (local deployment — exactly one user row)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_single_user(db: Session) -> User:
    """Return the one user, creating a default if the table is empty."""
    user = db.execute(select(User).order_by(User.id)).scalars().first()
    if user is None:
        user = User(name="Breadwinner", base_currency="USD")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

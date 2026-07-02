import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from axiom.db.base import BaseSchema


class UserSchema(BaseSchema):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(sa.String, nullable=False)
    country_code: Mapped[str] = mapped_column(sa.String(5), nullable=False, server_default=sa.text("'+91'"))
    phone_number: Mapped[str] = mapped_column(sa.String(15), index=True, nullable=False)
    name: Mapped[str] = mapped_column(sa.String(100), index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(sa.String(255), index=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, server_default=sa.text("true"))


__all__ = [
    "UserSchema",
]
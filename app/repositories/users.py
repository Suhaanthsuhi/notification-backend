import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UserSchema
from axiom.db.manager import GenericManager

class UserRepository(GenericManager[UserSchema]):
    def __init__(self, session: AsyncSession):
        super().__init__(UserSchema, session)

    async def get_by_phone_and_tenant(
        self, phone_number: str, tenant_id: str
    ) -> UserSchema | None:
        """The single user identified by (tenant, phone) — guaranteed unique."""
        result = await self.session.execute(
            sa.select(self.model).filter_by(phone_number=phone_number, tenant_id=tenant_id)
        )
        return result.scalar_one_or_none()

# Backward-compatible alias
UserManager = UserRepository

__all__ = [
    "UserManager",
]
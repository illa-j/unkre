from uuid import UUID

from sqlalchemy import select, update

from adapters.database.models import AdminModel
from adapters.database.repositiries import CrudRepository
from domain.entities.admin import Admin
from domain.exceptions.auth import AuthenticationConflictError
from ports import DatabaseManagerInterface


class AdminRepository(CrudRepository[AdminModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, AdminModel)

    async def get_admin(self, admin_id: UUID) -> Admin | None:
        model = await self.get(admin_id)
        return model.to_entity() if model else None

    async def find_by_username(self, username: str) -> Admin | None:
        model = await self._db.scalar(
            select(AdminModel).where(AdminModel.username == username)
        )
        return model.to_entity() if model else None

    async def create_admin(self, admin: Admin) -> Admin:
        model = await self.create(AdminModel.from_entity(admin))
        return model.to_entity()

    async def update_password_hash(
        self, admin_id: UUID, old_hash: str, new_hash: str
    ) -> None:
        updated = await self._db.scalar(
            update(AdminModel)
            .where(AdminModel.id == admin_id, AdminModel._hashed_password == old_hash)
            .values(_hashed_password=new_hash)
            .returning(AdminModel.id)
        )
        if updated is None:
            raise AuthenticationConflictError

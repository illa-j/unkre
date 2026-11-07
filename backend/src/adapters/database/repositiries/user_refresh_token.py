from adapters.database.models import UserRefreshTokenModel
from adapters.database.repositiries import CrudRepository
from ports import DatabaseManagerInterface


class UserRefreshTokenRepository(CrudRepository[UserRefreshTokenModel, int]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, UserRefreshTokenModel)

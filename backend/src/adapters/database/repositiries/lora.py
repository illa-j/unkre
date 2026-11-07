from adapters.database.models import LoraModel
from adapters.database.repositiries import CrudRepository
from ports import DatabaseManagerInterface


class LoraRepository(CrudRepository[LoraModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, LoraModel)

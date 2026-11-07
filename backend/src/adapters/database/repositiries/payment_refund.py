from adapters.database.models import PaymentRefundModel
from adapters.database.repositiries import CrudRepository
from ports import DatabaseManagerInterface


class PaymentRefundRepository(CrudRepository[PaymentRefundModel]):
    def __init__(self, db: DatabaseManagerInterface) -> None:
        super().__init__(db, PaymentRefundModel)

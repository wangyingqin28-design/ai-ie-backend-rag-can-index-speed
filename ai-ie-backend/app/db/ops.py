

from app.db.repositories.base import AsyncBaseRepository, SyncBaseRepository

class DatabaseOps(
    SyncBaseRepository,
):
    pass


class AsyncDatabaseOps(
    AsyncBaseRepository,
):
    pass


async_db_ops = AsyncDatabaseOps()
db_ops = DatabaseOps()

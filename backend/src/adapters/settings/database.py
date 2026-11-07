from pydantic import Field, computed_field
from sqlalchemy import URL

from adapters.settings import BaseAppSettings


class DatabaseSettings(BaseAppSettings):
    POSTGRES_HOST: str
    POSTGRES_DB_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DB_POOL_SIZE: int = Field(default=5, ge=1)
    DB_MAX_OVERFLOW: int = Field(default=5, ge=0)

    def _render_url(self, drivername: str) -> str:
        return URL.create(
            drivername,
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_DB_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL_ASYNC(self) -> str:
        return self._render_url("postgresql+asyncpg")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def DATABASE_URL_SYNC(self) -> str:
        return self._render_url("postgresql+psycopg2")

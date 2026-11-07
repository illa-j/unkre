from pydantic import Field

from adapters.settings.base import BaseAppSettings


class TaskQueueSettings(BaseAppSettings):
    REDIS_URL: str = "redis://localhost:6379/0"
    TASK_QUEUE_NAME: str = Field(default="unkre:tasks", min_length=1)
    TASK_QUEUE_MAX_JOBS: int = Field(default=10, ge=1)
    TASK_QUEUE_MAX_TRIES: int = Field(default=5, ge=1)
    TASK_QUEUE_JOB_TIMEOUT_SECONDS: int = Field(default=90, ge=1)
    GENERATION_POLL_INTERVAL_SECONDS: int = Field(default=5, ge=1)
    GENERATION_RETENTION_DAYS: int = Field(default=7, ge=1)
    GENERATION_CLEANUP_BATCH_SIZE: int = Field(default=50, ge=1, le=500)
    IMAGE_CLEANUP_BATCH_SIZE: int = Field(default=100, ge=1, le=1000)
    IMAGE_ORPHAN_GRACE_HOURS: int = Field(default=1, ge=1)

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    event,
    inspect,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, validates

from adapters.database.models import Base, LoraModel, TimestampMixin, WorkflowModel
from adapters.database.types import (
    LoraStrengths,
    String255,
    String4096,
    String8192,
    Timestamp,
    UUIDPrimaryKey,
)
from domain.entities import Generation
from domain.enums import GenerationStatus
from domain.exceptions import (
    InvalidLoraStrengthsError,
    LoraNotFoundError,
    LoraNotInWorkflowError,
    WorkflowMismatchError,
    WorkflowNotFoundError,
)
from domain.validators import NumberValidator, TextValidator

if TYPE_CHECKING:
    from adapters.database.models import UserModel


class GenerationModel(Base, TimestampMixin):
    __tablename__ = "generations"
    id: Mapped[UUIDPrimaryKey]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user: Mapped[UserModel] = relationship("UserModel", back_populates="generations")
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    workflow: Mapped[WorkflowModel] = relationship(
        "WorkflowModel", back_populates="generations", lazy="selectin"
    )
    prompt: Mapped[String8192] = mapped_column(nullable=False)
    negative_prompt: Mapped[String8192] = mapped_column(
        default="", server_default="", nullable=False
    )
    loras_strength: Mapped[LoraStrengths] = mapped_column(
        MutableDict.as_mutable(JSONB().with_variant(JSON(), "sqlite")),
        default=dict,
        nullable=False,
    )

    status: Mapped[GenerationStatus] = mapped_column(
        Enum(
            GenerationStatus,
            values_callable=lambda x: [v.value for v in x],
            name="generation_status",
            create_constraint=True,
        ),
        default=GenerationStatus.PENDING,
    )
    uploaded_images: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0"
    )

    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    runpod_job_id: Mapped[String255 | None] = mapped_column(unique=True, index=True)
    runpod_endpoint_id: Mapped[String255 | None] = mapped_column(nullable=True)
    error: Mapped[String4096 | None] = mapped_column(nullable=True)
    credits_spent: Mapped[int | None] = mapped_column(nullable=True)
    completed_at: Mapped[Timestamp | None] = mapped_column(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "length(trim(prompt)) BETWEEN 1 AND 8192 AND length(prompt) <= 8192",
            name="check_generations_prompt_length",
        ),
        CheckConstraint(
            "length(negative_prompt) <= 8192",
            name="check_generations_negative_prompt_length",
        ),
        CheckConstraint(
            "error IS NULL OR length(error) <= 4096",
            name="check_generations_error_length",
        ),
        CheckConstraint(
            "runpod_job_id IS NULL OR length(trim(runpod_job_id)) BETWEEN 1 AND 255 AND length(runpod_job_id) <= 255",
            name="check_generations_runpod_job_id_length",
        ),
        CheckConstraint(
            "runpod_endpoint_id IS NULL OR length(trim(runpod_endpoint_id)) BETWEEN 1 AND 255 AND length(runpod_endpoint_id) <= 255",
            name="check_generations_runpod_endpoint_id_length",
        ),
        CheckConstraint(
            "seed IS NULL OR seed BETWEEN 0 AND 9223372036854775807",
            name="check_generations_seed_range",
        ),
        CheckConstraint(
            "uploaded_images BETWEEN 0 AND 32767",
            name="check_generations_uploaded_images_range",
        ),
        CheckConstraint(
            "credits_spent IS NULL OR credits_spent BETWEEN 0 AND 2147483647",
            name="check_generations_credits_spent_range",
        ),
        CheckConstraint(
            "jsonb_typeof(loras_strength) = 'object'",
            name="check_generations_loras_strength_object",
        ).ddl_if(dialect="postgresql"),
        CheckConstraint(
            "json_type(loras_strength) = 'object'",
            name="check_generations_loras_strength_object",
        ).ddl_if(dialect="sqlite"),
        Index("ix_generations_stats_created", "created_at"),
        Index(
            "ix_generations_stats_active",
            "created_at",
            postgresql_where=text("status IN ('pending', 'queued', 'processing')"),
        ),
        Index(
            "ix_generations_retention",
            "status",
            text("COALESCE(completed_at, updated_at)"),
            "id",
            postgresql_where=text(
                "status IN ('completed', 'failed', 'cancelled', 'timed_out')"
            ),
        ),
    )

    @validates("prompt")
    def validate_prompt(self, key: str, value: str) -> str:
        return TextValidator.validate(value, max_length=8192, strip=True)

    @validates("negative_prompt")
    def validate_negative_prompt(self, key: str, value: str) -> str:
        return TextValidator.validate(
            value, min_length=0, max_length=8192, strip=True
        )

    @validates("runpod_job_id", "runpod_endpoint_id")
    def validate_runpod_id(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(value, max_length=255, strip=True, nullable=True)

    @validates("error")
    def validate_error(self, key: str, value: str | None) -> str | None:
        return TextValidator.validate(
            value, min_length=0, max_length=4096, nullable=True
        )

    @validates("uploaded_images")
    def validate_uploaded_images(self, key: str, value: int) -> int:
        return NumberValidator.validate_integer(value, min_value=0, max_value=32767)

    @validates("credits_spent")
    def validate_credits_spent(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=0, max_value=2**31 - 1, nullable=True
        )

    @validates("seed")
    def validate_seed(self, key: str, value: int | None) -> int | None:
        return NumberValidator.validate_integer(
            value, min_value=0, max_value=2**63 - 1, nullable=True
        )

    @validates("loras_strength")
    def validate_loras_strength(self, key: str, value: LoraStrengths) -> LoraStrengths:
        if not isinstance(value, dict):
            raise InvalidLoraStrengthsError(
                "expected an object mapping LoRA UUIDs to strengths"
            )
        result = {}
        for lora_id, strength in value.items():
            if not isinstance(lora_id, str):
                raise InvalidLoraStrengthsError("keys must be canonical UUID strings")
            try:
                parsed_id = uuid.UUID(lora_id)
            except ValueError:
                raise InvalidLoraStrengthsError(
                    "keys must be canonical UUID strings"
                ) from None
            if str(parsed_id) != lora_id:
                raise InvalidLoraStrengthsError("keys must be canonical UUID strings")
            result[lora_id] = NumberValidator.validate(strength)
        return result

    def validate_loras(self, session: Session) -> None:
        state = inspect(self)
        relationship_changed = state.attrs.workflow.history.has_changes()
        foreign_key_changed = state.attrs.workflow_id.history.has_changes()
        workflow: WorkflowModel | None = self.workflow
        if (
            foreign_key_changed
            and self.workflow_id is None
            and not relationship_changed
        ):
            raise WorkflowNotFoundError(None)
        if foreign_key_changed and self.workflow_id is not None:
            if (
                relationship_changed
                and workflow is not None
                and workflow.id != self.workflow_id
            ):
                raise WorkflowMismatchError()
            workflow = next(
                (
                    item
                    for item in session.new
                    if isinstance(item, WorkflowModel) and item.id == self.workflow_id
                ),
                None,
            ) or session.get(WorkflowModel, self.workflow_id)
        if workflow is None or workflow in session.deleted:
            raise WorkflowNotFoundError(self.workflow_id)
        if foreign_key_changed and not relationship_changed:
            self.workflow = workflow
        strengths = self.validate_loras_strength(
            "loras_strength",
            self.loras_strength if self.loras_strength is not None else {},
        )
        available = {lora.id for lora in workflow.loras if lora not in session.deleted}
        for key in strengths:
            lora_id = uuid.UUID(key)
            if lora_id in available:
                continue
            lora = next(
                (
                    item
                    for item in session.new
                    if isinstance(item, LoraModel) and item.id == lora_id
                ),
                None,
            ) or session.get(LoraModel, lora_id)
            if lora is None or lora in session.deleted:
                raise LoraNotFoundError(lora_id)
            raise LoraNotInWorkflowError(lora_id, workflow.id)

    def to_entity(self) -> Generation:
        return Generation(
            id=self.id,
            user_id=self.user_id,
            workflow_id=self.workflow_id,
            prompt=self.prompt,
            negative_prompt=self.negative_prompt,
            loras_strength={
                uuid.UUID(ident): strength
                for ident, strength in self.loras_strength.items()
            },
            uploaded_images=self.uploaded_images,
            status=self.status,
            runpod_job_id=self.runpod_job_id,
            seed=self.seed,
            error=self.error,
            completed_at=self.completed_at,
            created_at=self.created_at,
            credits_spent=self.credits_spent,
            runpod_endpoint_id=self.runpod_endpoint_id,
        )

    @classmethod
    def from_entity(cls, generation: Generation) -> GenerationModel:
        return cls(
            id=generation.id,
            user_id=generation.user_id,
            workflow_id=generation.workflow_id,
            prompt=generation.prompt,
            negative_prompt=generation.negative_prompt,
            loras_strength={
                str(ident): strength
                for ident, strength in generation.loras_strength.items()
            },
            uploaded_images=generation.uploaded_images,
            status=generation.status,
            runpod_job_id=generation.runpod_job_id,
            seed=generation.seed,
            error=generation.error,
            completed_at=generation.completed_at,
            credits_spent=generation.credits_spent,
            runpod_endpoint_id=generation.runpod_endpoint_id,
        )


@event.listens_for(Session, "before_flush")
def validate_generation_loras(
    session: Session, flush_context: object, instances: object
) -> None:
    generations = {
        item
        for item in session.new | session.dirty
        if isinstance(item, GenerationModel)
    }
    workflows = {
        item for item in session.new | session.dirty if isinstance(item, WorkflowModel)
    }
    for item in session.deleted:
        if isinstance(item, LoraModel):
            workflows.update(item.workflows)
    for workflow in workflows:
        if workflow not in session.deleted:
            generations.update(workflow.generations)
    for generation in generations:
        if generation not in session.deleted:
            generation.validate_loras(session)
    for item in session.new | session.dirty:
        if isinstance(item, LoraModel) and item.preview_urls is not None:
            item.validate_preview_urls("preview_urls", item.preview_urls)

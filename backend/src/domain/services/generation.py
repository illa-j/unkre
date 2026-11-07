import base64
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import fields, replace
from datetime import datetime
from logging import getLogger
from uuid import UUID, uuid7

from domain.entities.generation import Generation
from domain.entities.workflow import Workflow
from domain.enums import GenerationStatus
from domain.exceptions.auth import InvalidCredentialsError, UserBlockedError
from domain.exceptions.generation import (
    GenerationNotFoundError,
    InsufficientCreditsError,
    InvalidGenerationImagesError,
    InvalidGenerationStateError,
    InvalidLoraStrengthsError,
    LoraNotInWorkflowError,
    TooManyReferenceImagesError,
    UnsupportedReferenceImagesError,
    WorkflowNotFoundError,
)
from domain.exceptions.repositories import InvalidRepositoryFieldError
from domain.validators import (
    NumberValidator,
    TextValidator,
    validate_lora_strength,
)
from ports.repositories.generation import (
    GenerationRepositoryInterface,
    WorkflowRepositoryInterface,
)
from ports.repositories.payment import (
    TransactionRepositoryInterface,
    WalletRepositoryInterface,
)
from ports.repositories.user import UserRepositoryInterface
from ports.services.generation import GenerationRunnerInterface

logger = getLogger(__name__)
ACTIVE_STATUSES = {
    GenerationStatus.PENDING,
    GenerationStatus.QUEUED,
    GenerationStatus.PROCESSING,
}
INPUT_FIELDS = {
    "workflow_id",
    "prompt",
    "negative_prompt",
    "loras_strength",
    "uploaded_images",
    "seed",
}
READ_ONLY_FIELDS = {"id", "user_id", "created_at"}
# The API does not expose size controls yet, but the Krea graphs carry
# {{width}}/{{height}} placeholders. A fixed default keeps those graphs runnable.
DEFAULT_IMAGE_SIZE = (1024, 1024)
# TextEncodeQwenImage21 autogrows images.image_1..image_16.
MAX_REFERENCE_IMAGES = 16


class GenerationService:
    def __init__(
        self,
        generations: GenerationRepositoryInterface,
        workflows: WorkflowRepositoryInterface,
        users: UserRepositoryInterface,
        runpod: GenerationRunnerInterface,
        wallets: WalletRepositoryInterface,
        transactions: TransactionRepositoryInterface,
    ) -> None:
        self._generations = generations
        self._workflows = workflows
        self._users = users
        self._runpod = runpod
        self._wallets = wallets
        self._transactions = transactions

    async def create(self, generation: Generation) -> Generation:
        await self._require_user(generation.user_id)
        generation, _ = await self._prepare(generation)
        return await self._generations.create_generation(generation)

    async def get(self, generation_id: UUID) -> Generation:
        generation = await self._generations.get_generation(generation_id)
        if generation is None:
            raise GenerationNotFoundError(generation_id)
        return generation

    async def get_all(self, *, limit: int = 100, offset: int = 0) -> list[Generation]:
        self._validate_pagination(limit, offset)
        return await self._generations.get_generations(limit=limit, offset=offset)

    async def update(
        self, generation_id: UUID, values: Mapping[str, object]
    ) -> Generation:
        available = {field.name for field in fields(Generation)}
        for field in values:
            if field not in available:
                raise InvalidRepositoryFieldError(field, "unknown generation field")
            if field in READ_ONLY_FIELDS:
                raise InvalidRepositoryFieldError(field, "field is read-only")
        generation = await self.get(generation_id)
        if generation.runpod_job_id is not None and INPUT_FIELDS.intersection(values):
            raise InvalidGenerationStateError(
                "submitted generation inputs cannot be changed"
            )
        candidate, _ = await self._prepare(replace(generation, **values))
        changes = {field: getattr(candidate, field) for field in values}
        updated = await self._generations.update_generation(generation_id, changes)
        if updated is None:
            raise GenerationNotFoundError(generation_id)
        return updated

    async def delete(self, generation_id: UUID) -> bool:
        generation = await self._generations.get_generation(generation_id)
        if generation is None:
            return False
        await self._cancel_active(generation)
        return await self._generations.delete_generation(generation_id)

    async def create_generation(
        self,
        user_id: UUID,
        *,
        workflow_id: UUID,
        prompt: str,
        negative_prompt: str = "",
        images: Sequence[str] = (),
        loras_strength: Mapping[UUID, int | float] | None = None,
        seed: int | None = None,
    ) -> Generation:
        await self._require_user(user_id)
        images = self._validate_images(images)
        if loras_strength is not None and not isinstance(loras_strength, Mapping):
            raise InvalidLoraStrengthsError("expected LoRA UUIDs mapped to strengths")
        generation, workflow = await self._prepare(
            Generation(
                user_id=user_id,
                workflow_id=workflow_id,
                prompt=prompt,
                negative_prompt=negative_prompt,
                loras_strength=dict(loras_strength)
                if loras_strength is not None
                else {},
                uploaded_images=len(images),
                seed=seed if seed is not None else secrets.randbelow(2**63),
            )
        )
        if images and workflow.name.strip().casefold() != "qwen image 2.1":
            raise UnsupportedReferenceImagesError()
        endpoint_id = TextValidator.validate(
            self._runpod.endpoint_for(workflow.name), max_length=255, strip=True
        )
        generation.runpod_endpoint_id = endpoint_id
        strengths = None
        if loras_strength is not None:
            names = {lora.id: lora.name for lora in workflow.loras}
            strengths = {
                names[ident]: strength
                for ident, strength in generation.loras_strength.items()
            }
            if len(strengths) != len(generation.loras_strength):
                raise InvalidLoraStrengthsError("selected LoRA names must be unique")
        credits = workflow.generation_credits
        wallet = None
        if credits:
            wallet = await self._wallets.get_by_user(user_id)
            if wallet is not None:
                # Refresh after acquiring the lock; another purchase or generation
                # may have changed the balance since the initial user lookup.
                wallet = await self._wallets.get_for_update(wallet.id)
            if wallet is None or wallet.credits < credits:
                raise InsufficientCreditsError(
                    credits, wallet.credits if wallet is not None else 0
                )
        generation = replace(generation, credits_spent=credits)
        generation = await self._generations.create_generation(generation)
        if credits and wallet is not None:
            await self._transactions.post_spend(
                wallet,
                amount=credits,
                generation_id=generation.id,
                idempotency_key=f"generation:{generation.id}",
                description="Image generation",
            )
        job_id = await self._runpod.run(
            images,
            generation.seed,
            workflow.name,
            generation.prompt,
            loras_strength=strengths,
            negative_prompt=generation.negative_prompt,
            size=DEFAULT_IMAGE_SIZE,
            endpoint_id=endpoint_id,
        )
        try:
            job_id = TextValidator.validate(job_id, max_length=255, strip=True)
            submitted = await self._generations.update_generation(
                generation.id,
                {
                    "runpod_job_id": job_id,
                    "runpod_endpoint_id": endpoint_id,
                    "status": GenerationStatus.QUEUED,
                },
            )
            if submitted is None:
                raise GenerationNotFoundError(generation.id)
        except BaseException:
            try:
                await self._runpod.cancel(job_id, endpoint_id=endpoint_id)
            except Exception as exc:
                logger.warning(
                    "Cannot cancel submitted RunPod job %s (%s)",
                    job_id,
                    type(exc).__name__,
                )
            raise
        # The existing recovery worker schedules polling after the caller commits.
        return submitted

    async def get_user_generation(
        self, user_id: UUID, generation_id: UUID
    ) -> Generation:
        await self._require_user(user_id)
        generation = await self._generations.get_for_user(user_id, generation_id)
        if generation is None:
            raise GenerationNotFoundError(generation_id)
        return generation

    async def get_user_generations(
        self, user_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Generation]:
        self._validate_pagination(limit, offset)
        await self._require_user(user_id)
        return await self._generations.list_for_user(
            user_id, limit=limit, offset=offset
        )

    async def delete_user_generation(self, user_id: UUID, generation_id: UUID) -> bool:
        generation = await self.get_user_generation(user_id, generation_id)
        await self._cancel_active(generation)
        return await self._generations.delete_for_user(user_id, generation_id)

    async def _require_user(self, user_id: UUID) -> None:
        if not isinstance(user_id, UUID):
            raise InvalidGenerationStateError("user_id must be a UUID")
        user = await self._users.get_user(user_id)
        if user is None:
            raise InvalidCredentialsError("Unknown user")
        if user.is_blocked:
            raise UserBlockedError("User is blocked")

    async def _prepare(self, generation: Generation) -> tuple[Generation, Workflow]:
        if not isinstance(generation.user_id, UUID) or not isinstance(
            generation.workflow_id, UUID
        ):
            raise InvalidGenerationStateError("user_id and workflow_id must be UUIDs")
        if generation.id is not None and not isinstance(generation.id, UUID):
            raise InvalidGenerationStateError("generation id must be a UUID")
        prompt = TextValidator.validate(generation.prompt, max_length=8192, strip=True)
        negative_prompt = TextValidator.validate(
            generation.negative_prompt, min_length=0, max_length=8192, strip=True
        )
        uploaded_images = NumberValidator.validate_integer(
            generation.uploaded_images, min_value=0, max_value=32767
        )
        seed = NumberValidator.validate_integer(
            generation.seed, min_value=0, max_value=2**63 - 1, nullable=True
        )
        credits_spent = NumberValidator.validate_integer(
            generation.credits_spent, min_value=0, max_value=2**31 - 1, nullable=True
        )
        try:
            status = GenerationStatus(generation.status)
        except (ValueError, TypeError) as exc:
            raise InvalidGenerationStateError("unknown generation status") from exc
        error = TextValidator.validate(
            generation.error, min_length=0, max_length=4096, nullable=True
        )
        job_id = TextValidator.validate(
            generation.runpod_job_id, max_length=255, strip=True, nullable=True
        )
        endpoint_id = TextValidator.validate(
            generation.runpod_endpoint_id, max_length=255, strip=True, nullable=True
        )
        if generation.completed_at is not None and not isinstance(
            generation.completed_at, datetime
        ):
            raise InvalidGenerationStateError("completed_at must be a datetime")
        if not isinstance(generation.loras_strength, Mapping):
            raise InvalidLoraStrengthsError("expected LoRA UUIDs mapped to strengths")
        strengths = {}
        for lora_id, strength in generation.loras_strength.items():
            if not isinstance(lora_id, UUID):
                raise InvalidLoraStrengthsError("keys must be LoRA UUIDs")
            strengths[lora_id] = validate_lora_strength(strength)
        workflow = await self._workflows.get_workflow(generation.workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(generation.workflow_id)
        allowed = {lora.id for lora in workflow.loras}
        for lora_id in strengths:
            if lora_id not in allowed:
                raise LoraNotInWorkflowError(lora_id, workflow.id)
        return replace(
            generation,
            id=generation.id or uuid7(),
            prompt=prompt,
            negative_prompt=negative_prompt,
            uploaded_images=uploaded_images,
            seed=seed,
            status=status,
            loras_strength=strengths,
            credits_spent=credits_spent,
            error=error,
            runpod_job_id=job_id,
            runpod_endpoint_id=endpoint_id,
        ), workflow

    async def _cancel_active(self, generation: Generation) -> None:
        if (
            generation.runpod_job_id is not None
            and generation.status in ACTIVE_STATUSES
        ):
            status = await self._runpod.cancel(
                generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
            )
            if status in ACTIVE_STATUSES:
                raise InvalidGenerationStateError("RunPod job is still active")

    @staticmethod
    def _validate_pagination(limit: int, offset: int) -> None:
        NumberValidator.validate_integer(limit, min_value=1, max_value=100)
        NumberValidator.validate_integer(offset, min_value=0)

    @staticmethod
    def _validate_images(images: Sequence[str]) -> list[str]:
        if isinstance(images, (str, bytes)) or not isinstance(images, Sequence):
            raise InvalidGenerationImagesError()
        if len(images) > MAX_REFERENCE_IMAGES:
            raise TooManyReferenceImagesError(MAX_REFERENCE_IMAGES)
        NumberValidator.validate_integer(len(images), min_value=0)
        result = list(images)
        for image in result:
            try:
                if not isinstance(image, str) or not base64.b64decode(
                    image, validate=True
                ):
                    raise InvalidGenerationImagesError()
            except ValueError as exc:
                raise InvalidGenerationImagesError() from exc
        return result

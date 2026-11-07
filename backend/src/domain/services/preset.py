from collections.abc import Mapping, Sequence
from uuid import UUID, uuid7

from domain.entities.preset import GenerationPreset
from domain.enums import PresetType
from domain.exceptions import ValidationError
from domain.exceptions.generation import (
    InvalidLoraStrengthsError,
    WorkflowNotFoundError,
)
from domain.exceptions.preset import PresetNotFoundError
from domain.validators import (
    NumberValidator,
    TextValidator,
    validate_lora_strength,
    validate_preview_urls,
)
from ports.repositories.generation import WorkflowRepositoryInterface
from ports.repositories.preset import PresetRepositoryInterface


class PresetService:
    def __init__(
        self,
        presets: PresetRepositoryInterface,
        workflows: WorkflowRepositoryInterface,
    ) -> None:
        self._presets = presets
        self._workflows = workflows

    async def create(
        self,
        user_id: UUID,
        *,
        name: str,
        workflow_id: UUID,
        prompt: str,
        negative_prompt: str = "",
        description: str = "",
        loras_strength: Mapping[UUID, int | float] | None = None,
        seed: int | None = None,
        is_public: bool = False,
        preview_urls: Sequence[str] = (),
    ) -> GenerationPreset:
        if not isinstance(user_id, UUID):
            raise ValidationError("user_id must be a UUID")
        return await self._create(
            user_id,
            PresetType.USER,
            name=name,
            workflow_id=workflow_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            description=description,
            loras_strength=loras_strength,
            seed=seed,
            is_public=is_public,
            preview_urls=preview_urls,
        )

    async def create_admin(
        self,
        *,
        name: str,
        workflow_id: UUID,
        prompt: str,
        negative_prompt: str = "",
        description: str = "",
        loras_strength: Mapping[UUID, int | float] | None = None,
        seed: int | None = None,
        is_public: bool = True,
        preview_urls: Sequence[str] = (),
    ) -> GenerationPreset:
        return await self._create(
            None,
            PresetType.ADMIN,
            name=name,
            workflow_id=workflow_id,
            prompt=prompt,
            negative_prompt=negative_prompt,
            description=description,
            loras_strength=loras_strength,
            seed=seed,
            is_public=is_public,
            preview_urls=preview_urls,
        )

    async def _create(
        self,
        user_id: UUID | None,
        preset_type: PresetType,
        *,
        name: str,
        workflow_id: UUID,
        prompt: str,
        negative_prompt: str,
        description: str,
        loras_strength: Mapping[UUID, int | float] | None,
        seed: int | None,
        is_public: bool,
        preview_urls: Sequence[str],
    ) -> GenerationPreset:
        if preset_type is PresetType.ADMIN and user_id is not None:
            raise ValidationError("Admin presets cannot have an owner")
        if not isinstance(workflow_id, UUID):
            raise WorkflowNotFoundError(workflow_id)
        if not isinstance(is_public, bool):
            raise ValidationError("is_public must be a boolean")
        name = TextValidator.validate(name, max_length=100, strip=True)
        prompt = TextValidator.validate(
            prompt, min_length=0, max_length=8192, strip=True
        )
        negative_prompt = TextValidator.validate(
            negative_prompt, min_length=0, max_length=8192, strip=True
        )
        description = TextValidator.validate(
            description, min_length=0, max_length=1000, strip=True
        )
        seed = NumberValidator.validate_integer(
            seed, min_value=0, max_value=2**63 - 1, nullable=True
        )
        workflow = await self._workflows.get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)

        strengths = self._validate_strengths(loras_strength, workflow)
        previews = validate_preview_urls(preview_urls)

        return await self._presets.create_preset(
            GenerationPreset(
                id=uuid7(),
                user_id=user_id,
                type=preset_type,
                workflow_id=workflow_id,
                name=name,
                prompt=prompt,
                negative_prompt=negative_prompt,
                description=description,
                is_public=is_public,
                preview_urls=previews,
                loras_strength=strengths,
                seed=seed,
            )
        )

    async def update(
        self,
        user_id: UUID,
        preset_id: UUID,
        changes: Mapping[str, object],
    ) -> GenerationPreset:
        if not isinstance(preset_id, UUID):
            raise PresetNotFoundError(preset_id)
        preset = await self._presets.get_for_user(user_id, preset_id)
        if preset is None:
            raise PresetNotFoundError(preset_id)
        updated = await self._update(preset, changes)
        if updated is None:
            raise PresetNotFoundError(preset_id)
        return updated

    async def update_admin(
        self, preset_id: UUID, changes: Mapping[str, object]
    ) -> GenerationPreset:
        if not isinstance(preset_id, UUID):
            raise PresetNotFoundError(preset_id)
        preset = await self._presets.get_any(preset_id)
        if preset is None:
            raise PresetNotFoundError(preset_id)
        updated = await self._update(preset, changes, admin=True)
        if updated is None:
            raise PresetNotFoundError(preset_id)
        return updated

    async def _update(
        self,
        preset: GenerationPreset,
        changes: Mapping[str, object],
        *,
        admin: bool = False,
    ) -> GenerationPreset | None:
        workflow_id = changes.get("workflow_id", preset.workflow_id)
        if not isinstance(workflow_id, UUID):
            raise WorkflowNotFoundError(workflow_id)
        workflow = await self._workflows.get_workflow(workflow_id)
        if workflow is None:
            raise WorkflowNotFoundError(workflow_id)

        values: dict[str, object] = {"workflow_id": workflow_id}
        if "name" in changes:
            values["name"] = TextValidator.validate(
                str(changes["name"]), max_length=100, strip=True
            )
        if "prompt" in changes:
            values["prompt"] = TextValidator.validate(
                str(changes["prompt"]), min_length=0, max_length=8192, strip=True
            )
        if "negative_prompt" in changes:
            values["negative_prompt"] = TextValidator.validate(
                str(changes["negative_prompt"]),
                min_length=0,
                max_length=8192,
                strip=True,
            )
        if "description" in changes:
            values["description"] = TextValidator.validate(
                str(changes["description"]),
                min_length=0,
                max_length=1000,
                strip=True,
            )
        if "seed" in changes:
            values["seed"] = NumberValidator.validate_integer(
                changes["seed"], min_value=0, max_value=2**63 - 1, nullable=True
            )
        if "is_public" in changes:
            if not isinstance(changes["is_public"], bool):
                raise ValidationError("is_public must be a boolean")
            values["is_public"] = changes["is_public"]
        if "preview_urls" in changes:
            raw = changes["preview_urls"]
            values["preview_urls"] = (
                validate_preview_urls(raw) if raw is not None else []
            )

        strengths = (
            changes["loras_strength"]
            if "loras_strength" in changes
            else preset.loras_strength
        )
        validated = self._validate_strengths(strengths, workflow)
        if "loras_strength" in changes or "workflow_id" in changes:
            values["loras_strength"] = {
                str(lora_id): strength for lora_id, strength in validated.items()
            }

        if admin:
            return await self._presets.update_any(preset.id, values)
        return await self._presets.update_for_user(
            preset.user_id, preset.id, values
        )

    @staticmethod
    def _validate_strengths(
        loras_strength: object, workflow: object
    ) -> dict[UUID, int | float]:
        if loras_strength is None:
            return {}
        if not isinstance(loras_strength, Mapping):
            raise InvalidLoraStrengthsError("expected LoRA UUIDs mapped to strengths")
        allowed = {lora.id for lora in workflow.loras}
        strengths: dict[UUID, int | float] = {}
        for lora_id, strength in loras_strength.items():
            if not isinstance(lora_id, UUID):
                raise InvalidLoraStrengthsError("keys must be LoRA UUIDs")
            if lora_id not in allowed:
                raise InvalidLoraStrengthsError(
                    f"LoRA {lora_id} is not available in workflow {workflow.id}"
                )
            strengths[lora_id] = validate_lora_strength(strength)
        return strengths

    async def get_all(
        self, user_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[GenerationPreset]:
        if not isinstance(user_id, UUID):
            raise ValidationError("user_id must be a UUID")
        NumberValidator.validate_integer(limit, min_value=1, max_value=100)
        NumberValidator.validate_integer(offset, min_value=0)
        return await self._presets.list_for_user(user_id, limit=limit, offset=offset)

    async def get_admin(
        self, *, query: str | None = None, limit: int = 100, offset: int = 0
    ) -> tuple[list[GenerationPreset], int]:
        NumberValidator.validate_integer(limit, min_value=1, max_value=100)
        NumberValidator.validate_integer(offset, min_value=0)
        return await self._presets.list_any(query=query, limit=limit, offset=offset)

    async def get_accessible(
        self, user_id: UUID, preset_id: UUID
    ) -> GenerationPreset:
        if not isinstance(preset_id, UUID):
            raise PresetNotFoundError(preset_id)
        preset = await self._presets.get_accessible(user_id, preset_id)
        if preset is None:
            raise PresetNotFoundError(preset_id)
        return preset

    async def favorite(
        self, user_id: UUID, preset_id: UUID
    ) -> tuple[int, bool]:
        preset = await self._presets.get_accessible(user_id, preset_id)
        if preset is None or not preset.is_public:
            raise PresetNotFoundError(preset_id)
        return await self._presets.favorite(user_id, preset_id), True

    async def unfavorite(
        self, user_id: UUID, preset_id: UUID
    ) -> tuple[int, bool]:
        preset = await self._presets.get_accessible(user_id, preset_id)
        if preset is None or not preset.is_public:
            raise PresetNotFoundError(preset_id)
        return await self._presets.unfavorite(user_id, preset_id), False

    async def save(self, user_id: UUID, preset_id: UUID) -> bool:
        preset = await self._presets.get_accessible(user_id, preset_id)
        if preset is None or not preset.is_public:
            raise PresetNotFoundError(preset_id)
        return await self._presets.save(user_id, preset_id)

    async def unsave(self, user_id: UUID, preset_id: UUID) -> bool:
        preset = await self._presets.get_accessible(user_id, preset_id)
        if preset is None or not preset.is_public:
            raise PresetNotFoundError(preset_id)
        return await self._presets.unsave(user_id, preset_id)

    async def delete(self, user_id: UUID, preset_id: UUID) -> bool:
        if not isinstance(preset_id, UUID):
            raise PresetNotFoundError(preset_id)
        deleted = await self._presets.delete_for_user(user_id, preset_id)
        if not deleted:
            raise PresetNotFoundError(preset_id)
        return True

    async def delete_admin(self, preset_id: UUID) -> bool:
        if not isinstance(preset_id, UUID):
            raise PresetNotFoundError(preset_id)
        deleted = await self._presets.delete_any(preset_id)
        if not deleted:
            raise PresetNotFoundError(preset_id)
        return True

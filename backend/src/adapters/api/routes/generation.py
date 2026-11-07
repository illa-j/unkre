from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from adapters.api.dependencies.database import DatabaseManagerDep
from adapters.api.dependencies.generation import GenerationServiceDep, RunPodClientDep
from adapters.api.dependencies.images import ImageStoreDep
from adapters.api.dependencies.user import CurrentUserDep
from adapters.api.schemas.generation import CreateGenerationRequest, GenerationResponse
from adapters.storage import image_media_type
from domain.entities.generation import Generation
from domain.enums import GenerationStatus
from domain.exceptions.generation import GenerationNotFoundError
from domain.exceptions.runpod import RunPodJobNotFoundError

router = APIRouter(prefix="/generations", tags=["generations"])
logger = getLogger(__name__)


@router.post("", response_model=GenerationResponse, status_code=status.HTTP_201_CREATED)
async def create_generation(
    data: CreateGenerationRequest,
    user: CurrentUserDep,
    service: GenerationServiceDep,
    manager: DatabaseManagerDep,
    runpod: RunPodClientDep,
) -> Generation:
    generation = await service.create_generation(
        user.id,
        workflow_id=data.workflow_id,
        prompt=data.prompt,
        negative_prompt=data.negative_prompt,
        images=data.images,
        loras_strength=data.loras_strength,
        seed=data.seed,
    )
    try:
        # Commit while the provider client and returned job ID are still available.
        # session_scope alone cannot compensate a failed commit after this returns.
        await manager.commit()
    except BaseException:
        try:
            await runpod.cancel(
                generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
            )
        except Exception as exc:
            logger.warning(
                "Cannot cancel RunPod job %s after failed commit (%s)",
                generation.runpod_job_id,
                type(exc).__name__,
            )
        raise
    return generation


@router.get("", response_model=list[GenerationResponse])
async def get_generations(
    user: CurrentUserDep,
    service: GenerationServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Generation]:
    return await service.get_user_generations(user.id, limit=limit, offset=offset)


@router.get("/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: UUID, user: CurrentUserDep, service: GenerationServiceDep
) -> Generation:
    return await service.get_user_generation(user.id, generation_id)


@router.get("/{generation_id}/image", response_class=Response)
async def get_generation_image(
    generation_id: UUID,
    user: CurrentUserDep,
    service: GenerationServiceDep,
    runpod: RunPodClientDep,
    images: ImageStoreDep,
) -> Response:
    generation = await service.get_user_generation(user.id, generation_id)
    if generation.status != GenerationStatus.COMPLETED or not generation.runpod_job_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Generation image is unavailable"
        )
    cached = await images.get(generation.id) if images is not None else None
    content = cached[0] if cached is not None else None
    detected = image_media_type(content) if content is not None else None
    if content is None or detected is None:
        try:
            content = await runpod.decode_result(
                generation.runpod_job_id, endpoint_id=generation.runpod_endpoint_id
            )
        except RunPodJobNotFoundError as exc:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Generation image is unavailable"
            ) from exc
        if content is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, "Generation image is unavailable"
            )
        detected = image_media_type(content)
        if detected is None:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Invalid generation image")
        if images is not None:
            await images.put(generation.id, content)
    media_type, extension = detected
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{generation.id}.{extension}"',
        },
    )


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_generation(
    generation_id: UUID,
    user: CurrentUserDep,
    service: GenerationServiceDep,
    images: ImageStoreDep,
) -> None:
    if not await service.delete_user_generation(user.id, generation_id):
        raise GenerationNotFoundError(generation_id)
    if images is not None:
        if not await images.delete(generation_id):
            # Let session_scope roll the row deletion back so it can be retried.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Generation image could not be deleted; retry later",
            )

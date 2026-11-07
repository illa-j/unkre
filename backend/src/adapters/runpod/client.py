import asyncio
import base64
from collections.abc import Mapping, Sequence
from logging import getLogger
from types import TracebackType
from typing import Any, Self
from urllib.parse import quote

import httpx

from adapters.runpod.workflow import build_input
from adapters.settings import RunPodSettings, get_settings
from domain.enums import GenerationStatus
from domain.exceptions.runpod import (
    InvalidRunPodResponseError,
    RunPodJobNotFoundError,
    RunPodNotConfiguredError,
    RunPodRequestError,
)
from domain.validators import TextValidator

API_URL = "https://api.runpod.ai/v2/"
logger = getLogger(__name__)
JOB_STATUSES = {
    "IN_QUEUE": GenerationStatus.QUEUED,
    "IN_PROGRESS": GenerationStatus.PROCESSING,
    "COMPLETED": GenerationStatus.COMPLETED,
    "FAILED": GenerationStatus.FAILED,
    "CANCELLED": GenerationStatus.CANCELLED,
    "TIMED_OUT": GenerationStatus.TIMED_OUT,
}


class RunPodClient:
    def __init__(
        self,
        settings: RunPodSettings | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings or get_settings().RUNPOD_SETTINGS
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient()

    def endpoint_for(self, workflow_name: str | None = None) -> str:
        """Resolve the endpoint of one workflow.

        With RUNPOD_ENDPOINTS configured every workflow is bound to exactly one
        endpoint; a missing entry is an error, never a silent fallback. The legacy
        RUNPOD_ENDPOINT_ID remains the default when no mapping is configured.
        """
        endpoints = self._settings.RUNPOD_ENDPOINTS
        if endpoints:
            if workflow_name is None or not workflow_name.strip():
                raise RunPodNotConfiguredError(
                    "RUNPOD_ENDPOINTS is configured but no workflow was given"
                )
            name = workflow_name.strip()
            endpoint = endpoints.get(name, "").strip()
            if not endpoint:
                raise RunPodNotConfiguredError(
                    f"No RunPod endpoint configured for workflow '{name}'"
                )
            return endpoint
        endpoint = self._settings.RUNPOD_ENDPOINT_ID.strip()
        if not endpoint:
            raise RunPodNotConfiguredError("RUNPOD_ENDPOINT_ID is not configured")
        return endpoint

    def _path(
        self,
        operation: str,
        endpoint_id: str | None,
        workflow_name: str | None = None,
    ) -> str:
        endpoint = (
            self.endpoint_for(workflow_name)
            if endpoint_id is None
            else endpoint_id
        )
        return f"{API_URL}{self._segment(endpoint)}/{operation}"

    @staticmethod
    def _segment(value: str) -> str:
        value = TextValidator.validate(value, max_length=255, strip=True)
        if value in (".", "..") or "/" in value or "\\" in value:
            raise ValueError("Invalid RunPod endpoint or job id")
        return quote(value, safe="")

    async def run(
        self,
        images: Sequence[str],
        seed: int,
        workflow_name: str,
        prompt: str,
        *,
        loras_strength: Mapping[str, int | float] | None = None,
        negative_prompt: str = "",
        size: tuple[int, int] | None = None,
        endpoint_id: str | None = None,
    ) -> str:
        path = self._path("run", endpoint_id, workflow_name)
        decoded = [base64.b64decode(image, validate=True) for image in images]
        payload = await asyncio.to_thread(
            build_input,
            decoded,
            seed,
            workflow_name,
            prompt,
            negative_prompt,
            size,
            loras_strength=loras_strength,
        )
        data = await self._request("POST", path, {"input": payload})
        job_id = data.get("id")
        if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 255:
            raise InvalidRunPodResponseError("RunPod returned no valid job id")
        try:
            self._segment(job_id)
        except ValueError as exc:
            raise InvalidRunPodResponseError(
                "RunPod returned an invalid job id"
            ) from exc
        return job_id

    async def status(
        self, job_id: str, *, endpoint_id: str | None = None
    ) -> GenerationStatus:
        data = await self._status_raw(job_id, endpoint_id=endpoint_id)
        return self._status(data)

    async def error(self, job_id: str, *, endpoint_id: str | None = None) -> str | None:
        data = await self._status_raw(job_id, endpoint_id=endpoint_id)
        error = data.get("error")
        if error is not None and not isinstance(error, str):
            raise InvalidRunPodResponseError("RunPod returned an invalid error")
        return error

    async def decode_result(
        self, job_id: str, *, endpoint_id: str | None = None
    ) -> bytes | None:
        data = await self._status_raw(job_id, endpoint_id=endpoint_id)
        if self._status(data) != GenerationStatus.COMPLETED:
            return None
        output = data.get("output")
        if not isinstance(output, dict):
            return None
        images = output.get("images", [])
        if not isinstance(images, list):
            raise InvalidRunPodResponseError("RunPod returned invalid output images")
        for image in images:
            if not isinstance(image, dict) or image.get("type") != "base64":
                continue
            encoded = image.get("data")
            if not isinstance(encoded, str):
                raise InvalidRunPodResponseError("RunPod returned invalid image data")
            if encoded.startswith("data:"):
                encoded = encoded.partition(",")[2]
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except ValueError as exc:
                raise InvalidRunPodResponseError(
                    "RunPod returned invalid base64"
                ) from exc
            if not decoded:
                raise InvalidRunPodResponseError("RunPod returned an empty image")
            return decoded
        return None

    async def cancel(
        self, job_id: str, *, endpoint_id: str | None = None
    ) -> GenerationStatus:
        path = self._path(f"cancel/{self._segment(job_id)}", endpoint_id)
        data = await self._request("POST", path)
        return self._status(data)

    async def _status_raw(
        self, job_id: str, *, endpoint_id: str | None = None
    ) -> dict[str, Any]:
        path = self._path(f"status/{self._segment(job_id)}", endpoint_id)
        try:
            return await self._request("GET", path)
        except RunPodRequestError as exc:
            cause = exc.__cause__
            if (
                isinstance(cause, httpx.HTTPStatusError)
                and cause.response.status_code == 404
            ):
                raise RunPodJobNotFoundError("RunPod job is unavailable") from exc
            raise

    @staticmethod
    def _status(data: dict[str, Any]) -> GenerationStatus:
        status = data.get("status")
        if not isinstance(status, str) or status not in JOB_STATUSES:
            raise InvalidRunPodResponseError("RunPod returned an unknown job status")
        return JOB_STATUSES[status]

    async def _request(
        self, method: str, url: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not self._settings.RUNPOD_API_KEY.strip():
            raise RunPodNotConfiguredError("RUNPOD_API_KEY is not configured")
        try:
            response = await self._client.request(
                method,
                url,
                headers={
                    "Authorization": f"Bearer {self._settings.RUNPOD_API_KEY.strip()}"
                },
                json=payload,
                timeout=self._settings.RUNPOD_TIMEOUT_SECONDS,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "RunPod %s %s returned HTTP %s",
                method,
                url,
                exc.response.status_code,
            )
            raise RunPodRequestError("RunPod request failed") from exc
        except httpx.HTTPError as exc:
            logger.warning(
                "RunPod %s %s failed (%s)", method, url, type(exc).__name__
            )
            raise RunPodRequestError("RunPod request failed") from exc
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidRunPodResponseError("RunPod returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise InvalidRunPodResponseError("RunPod response must be an object")
        return data

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

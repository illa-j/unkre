from collections.abc import Mapping, Sequence
from typing import Protocol

from domain.enums import GenerationStatus


class GenerationRunnerInterface(Protocol):
    def endpoint_for(self, workflow_name: str | None = None) -> str: ...

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
    ) -> str: ...

    async def cancel(
        self, job_id: str, *, endpoint_id: str | None = None
    ) -> GenerationStatus: ...

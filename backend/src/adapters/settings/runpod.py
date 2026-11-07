import json
from collections.abc import Mapping
from typing import Annotated, Any

from pydantic import Field, field_validator
from pydantic_settings import NoDecode

from adapters.settings.base import BaseAppSettings


class RunPodSettings(BaseAppSettings):
    RUNPOD_API_KEY: str = ""
    # Legacy single-endpoint mode. Used only when RUNPOD_ENDPOINTS is empty.
    RUNPOD_ENDPOINT_ID: str = ""
    # Workflow name -> endpoint id. When set, every workflow must have exactly one
    # entry here and the single RUNPOD_ENDPOINT_ID is ignored. Accepts JSON
    # ({"workflow": "endpoint"}) or a compact list (workflow=endpoint,other=endpoint).
    RUNPOD_ENDPOINTS: Annotated[dict[str, str], NoDecode] = Field(
        default_factory=dict
    )
    RUNPOD_TIMEOUT_SECONDS: float = Field(default=30, gt=0)

    @field_validator("RUNPOD_ENDPOINTS", mode="before")
    @classmethod
    def parse_endpoints(cls, value: Any) -> dict[str, str]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            items = value.items()
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            if raw.startswith("{"):
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise ValueError("RUNPOD_ENDPOINTS JSON must be an object")
                items = parsed.items()
            else:
                items = []
                for pair in raw.split(","):
                    name, separator, endpoint = pair.partition("=")
                    if not separator:
                        raise ValueError(
                            "RUNPOD_ENDPOINTS must use workflow=endpoint pairs"
                        )
                    items.append((name, endpoint))
        else:
            raise ValueError("RUNPOD_ENDPOINTS must be a mapping or a string")

        endpoints: dict[str, str] = {}
        for name, endpoint in items:
            name = str(name).strip()
            endpoint = str(endpoint).strip()
            if not name or not endpoint:
                raise ValueError("RUNPOD_ENDPOINTS cannot contain empty values")
            if name in endpoints:
                raise ValueError(f"Duplicate RUNPOD_ENDPOINTS workflow: {name}")
            endpoints[name] = endpoint
        return endpoints

import base64
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from domain.exceptions.generation import InvalidLoraStrengthsError, InvalidWorkflowError
from domain.validators import NumberValidator, TextValidator

WORKFLOWS_DIR = Path(__file__).parent / "workflows"
PLACEHOLDERS = re.compile(
    r'"\{\{(seed|width|height)\}\}"|\{\{(seed|width|height|prompt|positive_prompt|negative_prompt)\}\}'
)


def image_name(index: int) -> str:
    NumberValidator.validate_integer(index, min_value=0)
    return "input.png" if index == 0 else f"input_{index + 1}.png"


def build_input(
    images: Sequence[bytes],
    seed: int,
    workflow_name: str,
    prompt: str,
    negative_prompt: str = "",
    size: tuple[int, int] | None = None,
    *,
    loras_strength: Mapping[str, int | float] | None = None,
) -> dict[str, Any]:
    seed = NumberValidator.validate_integer(seed, min_value=0, max_value=2**63 - 1)
    prompt = TextValidator.validate(prompt, max_length=8192, strip=True)
    negative_prompt = TextValidator.validate(
        negative_prompt, min_length=0, max_length=8192
    )
    name = TextValidator.validate(workflow_name, max_length=255, strip=True)
    if name in (".", "..") or any(char in name for char in ("/", "\\", "\0")):
        raise InvalidWorkflowError("Invalid workflow name")
    root = WORKFLOWS_DIR.resolve()
    path = (root / (name if name.endswith(".json") else f"{name}.json")).resolve()
    if path.parent != root:
        raise InvalidWorkflowError("Workflow must be inside the workflows directory")
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise InvalidWorkflowError(f"Cannot read workflow '{name}'") from exc

    values: dict[str, int | str] = {
        "seed": seed,
        "prompt": prompt,
        "positive_prompt": prompt,
        "negative_prompt": negative_prompt,
    }
    if size is not None:
        if not isinstance(size, (tuple, list)) or len(size) != 2:
            raise InvalidWorkflowError("Size must contain width and height")
        values["width"] = NumberValidator.validate_integer(size[0], min_value=1)
        values["height"] = NumberValidator.validate_integer(size[1], min_value=1)

    def replace(match: re.Match[str]) -> str:
        key = match.group(1) or match.group(2)
        if key not in values:
            raise InvalidWorkflowError(f"No value supplied for '{key}'")
        value = values[key]
        return str(value) if isinstance(value, int) else json.dumps(value)[1:-1]

    try:
        workflow = json.loads(PLACEHOLDERS.sub(replace, source))
    except (ValueError, TypeError) as exc:
        raise InvalidWorkflowError(f"Invalid workflow JSON: '{name}'") from exc
    if not isinstance(workflow, dict) or not workflow:
        raise InvalidWorkflowError("Expected a non-empty ComfyUI API workflow")
    for node in workflow.values():
        if (
            not isinstance(node, dict)
            or not isinstance(node.get("class_type"), str)
            or not isinstance(node.get("inputs"), dict)
        ):
            raise InvalidWorkflowError("Expected nodes with class_type and inputs")

    uploaded = {}
    for index, image in enumerate(images):
        if not isinstance(image, bytes) or not image:
            raise InvalidWorkflowError("Input images must be non-empty bytes")
        uploaded[image_name(index)] = image
    if not uploaded:
        _drop_reference_images(workflow)
    else:
        _attach_reference_images(workflow, len(images))
    has_seed = "{{seed}}" in source
    for node in workflow.values():
        inputs = node["inputs"]
        for key in ("seed", "noise_seed"):
            if key in inputs and not isinstance(inputs[key], list):
                inputs[key] = seed
                has_seed = True
        if size is not None and node["class_type"] in (
            "EmptyLatentImage",
            "EmptySD3LatentImage",
            "EmptyHunyuanLatentVideo",
        ):
            for key in ("width", "height"):
                if key in inputs:
                    inputs[key] = values[key]
        if node["class_type"] == "LoadImage":
            filename = inputs.get("image")
            if not isinstance(filename, str) or filename not in uploaded:
                raise InvalidWorkflowError(f"Missing input image '{filename}'")
    if not has_seed:
        raise InvalidWorkflowError("Workflow has no seed input or {{seed}} placeholder")
    positive = _text_nodes(workflow, "positive")
    negative = _text_nodes(workflow, "negative")
    if "{{prompt}}" not in source and "{{positive_prompt}}" not in source:
        if not positive:
            raise InvalidWorkflowError("Workflow has no positive prompt input")
        for node_id in positive - negative:
            workflow[node_id]["inputs"]["text"] = prompt
    if "{{negative_prompt}}" not in source:
        for node_id in negative - positive:
            workflow[node_id]["inputs"]["text"] = negative_prompt
    if loras_strength is not None:
        _apply_loras(workflow, loras_strength)
    payload: dict[str, Any] = {"workflow": workflow}
    if uploaded:
        payload["images"] = [
            {"name": name, "image": base64.b64encode(image).decode("ascii")}
            for name, image in uploaded.items()
        ]
    return payload


def _next_node_id(workflow: dict[str, Any]) -> str:
    numbers = [int(node_id) for node_id in workflow if str(node_id).isdigit()]
    candidate = max(numbers, default=0) + 1
    while str(candidate) in workflow:
        candidate += 1
    return str(candidate)


def _attach_reference_images(workflow: dict[str, Any], count: int) -> None:
    """Extend the reference branch with one LoadImage per additional image.

    Qwen Image 2.1 exposes ``images.image_1``..``images.image_3`` on its text
    encoder; graphs that only declare the first slot keep working as before.
    """
    if count <= 1:
        return
    encoder = next(
        (
            node
            for node in workflow.values()
            if "images.image_1" in node["inputs"]
        ),
        None,
    )
    if encoder is None:
        return
    for index in range(1, count):
        key = f"images.image_{index + 1}"
        if key in encoder["inputs"]:
            continue
        node_id = _next_node_id(workflow)
        workflow[node_id] = {
            "class_type": "LoadImage",
            "inputs": {"image": image_name(index)},
        }
        encoder["inputs"][key] = [node_id, 0]


def _drop_reference_images(workflow: dict[str, Any]) -> None:
    """Remove the reference-image branch so a text-only request can reuse the graph."""
    dropped = {
        node_id for node_id, node in workflow.items() if node["class_type"] == "LoadImage"
    }
    while dropped:
        for node_id in dropped:
            workflow.pop(node_id, None)
        dropped = set()
        for node_id, node in workflow.items():
            inputs = node["inputs"]
            for key, value in list(inputs.items()):
                if isinstance(value, list) and len(value) == 2 and value[0] not in workflow:
                    del inputs[key]
            if not node["inputs"]:
                dropped.add(node_id)


def _text_nodes(workflow: dict[str, Any], conditioning: str) -> set[str]:
    pending = []
    for node in workflow.values():
        link = node["inputs"].get(conditioning)
        if isinstance(link, list) and len(link) == 2 and isinstance(link[0], str):
            pending.append(link[0])
    found = set()
    visited = set()
    while pending:
        node_id = pending.pop()
        if node_id in visited or node_id not in workflow:
            continue
        visited.add(node_id)
        inputs = workflow[node_id]["inputs"]
        if isinstance(inputs.get("text"), str):
            found.add(node_id)
            continue
        for value in inputs.values():
            if (
                isinstance(value, list)
                and len(value) == 2
                and isinstance(value[0], str)
            ):
                pending.append(value[0])
    return found


def _apply_loras(
    workflow: dict[str, Any], strengths: Mapping[str, int | float]
) -> None:
    if not isinstance(strengths, Mapping):
        raise InvalidLoraStrengthsError("expected LoRA names mapped to strengths")
    requested = {}
    for name, strength in strengths.items():
        name = TextValidator.validate(name, max_length=255)
        requested[name] = NumberValidator.validate(strength)
    found = set()
    for node in workflow.values():
        inputs = node["inputs"]
        name = inputs.get("lora_name")
        if not isinstance(name, str):
            continue
        keys = (
            "strength_lora", "strength_model", "strength_clip", "strength"
        )
        editable = [key for key in keys if key in inputs]
        if editable:
            for key in editable:
                inputs[key] = requested.get(name, 0)
            found.add(name)
    missing = requested.keys() - found
    if missing:
        raise InvalidLoraStrengthsError(
            f"workflow has no editable LoRA named {', '.join(sorted(missing))}"
        )

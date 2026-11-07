"""Generate the Krea 2 Turbo workflow in both ComfyUI formats.

Produces two files in ``src/adapters/runpod/workflows``:

* ``krea2_turbo_all_api.json`` - API graph (``{node_id: {class_type, inputs}}``),
  the only format ``adapters.runpod.workflow.build_input`` can execute;
* ``krea2_turbo_all_ui.json`` - the same graph in the ComfyUI editor format
  (``nodes`` + ``links``), for manual import and tweaking.

Both contain every catalog LoRA, chained after the UNET loader and written with
``strength_model: 0``, so a generation enables only the LoRAs it asks for.

Run from the backend directory:

    .venv/bin/python scripts/generate_krea2_workflows.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
WORKFLOWS_DIR = BACKEND_ROOT / "src" / "adapters" / "runpod" / "workflows"
CATALOG_PATH = SCRIPT_DIR / "krea2_loras.json"
MANIFEST_PATH = SCRIPT_DIR / "krea2_turbo_manifest.json"

# Strongest Krea 2 Turbo build (BF16, 26.3 GB). Swap for krea2_turbo_fp8_scaled
# or krea2_turbo_int8_convrot only when VRAM is the constraint.
UNET_NAME = "krea2_turbo_bf16.safetensors"
# Full BF16 abliterated (uncensored) Qwen3-VL-4B, the encoder Krea 2 runs on.
CLIP_NAME = "qwen3-vl-4b-heretic.safetensors"
CLIP_TYPE = "krea2"
# Qwen Image VAE is the only VAE Krea 2 uses; it has no censored variant.
VAE_NAME = "qwen_image_vae.safetensors"
STEPS = 8
CFG = 1
SAMPLER = "er_sde"
SCHEDULER = "simple"

API_NAME = "krea2_turbo_all_api"
UI_NAME = "krea2_turbo_all_ui"
FIRST_LORA_NODE = 10
DEFAULT_PROMPT = "a photograph of a woman, natural skin texture, soft daylight"

UNET_ID, CLIP_ID, VAE_ID = 1, 2, 3
TEXT_ID, ZERO_ID, LATENT_ID = 4, 5, 6
SAMPLER_ID, DECODE_ID, SAVE_ID = 7, 8, 9


def build_api_graph(loras: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a Krea 2 Turbo graph in the ComfyUI API format."""
    graph: dict[str, Any] = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": UNET_NAME, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": CLIP_NAME, "type": CLIP_TYPE, "device": "default"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE_NAME}},
        "4": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "{{prompt}}", "clip": ["2", 0]},
        },
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": "{{width}}", "height": "{{height}}", "batch_size": 1},
        },
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": "{{seed}}",
                "steps": STEPS,
                "cfg": CFG,
                "sampler_name": SAMPLER,
                "scheduler": SCHEDULER,
                "denoise": 1,
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {
            "class_type": "SaveImage",
            "inputs": {"images": ["8", 0], "filename_prefix": API_NAME},
        },
    }
    model_link: list[Any] = ["1", 0]
    for index, lora in enumerate(loras):
        node_id = str(FIRST_LORA_NODE + index)
        graph[node_id] = {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": model_link,
                "lora_name": lora["lora_name"],
                "strength_model": 0,
            },
        }
        model_link = [node_id, 0]
    graph["7"]["inputs"]["model"] = model_link
    return graph


def _in(name: str, kind: str, link: int | None = None, *, widget: bool = False) -> dict[str, Any]:
    """Editor-format input socket."""
    socket: dict[str, Any] = {
        "localized_name": name,
        "name": name,
        "type": kind,
        "link": link,
    }
    if widget:
        socket["widget"] = {"name": name}
    return socket


def _out(name: str, kind: str, links: list[int]) -> dict[str, Any]:
    """Editor-format output socket: outgoing connections live in ``links``."""
    return {"localized_name": name, "name": name, "type": kind, "links": links}


def _node(
    node_id: int,
    node_type: str,
    pos: list[int],
    size: list[int],
    order: int,
    widgets: list[Any],
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": node_type,
        "pos": pos,
        "size": size,
        "flags": {},
        "order": order,
        "mode": 0,
        "inputs": inputs or [],
        "outputs": outputs or [],
        "properties": {"Node name for S&R": node_type},
        "widgets_values": widgets,
    }


def build_ui_graph(loras: list[dict[str, Any]]) -> dict[str, Any]:
    """Return the same Krea 2 Turbo graph in the ComfyUI editor format."""
    lora_ids = [FIRST_LORA_NODE + index for index in range(len(loras))]
    model_targets = [UNET_ID, *lora_ids]
    model_sources = [*lora_ids, SAMPLER_ID]

    links: list[list[Any]] = []

    def add_link(origin: int, slot: int, target: int, target_slot: int, kind: str) -> int:
        links.append([len(links) + 1, origin, slot, target, target_slot, kind])
        return len(links)

    model_links = [
        add_link(source, 0, target, 0, "MODEL")
        for source, target in zip(model_targets, model_sources)
    ]
    clip_link = add_link(CLIP_ID, 0, TEXT_ID, 0, "CLIP")
    zero_link = add_link(TEXT_ID, 0, ZERO_ID, 0, "CONDITIONING")
    positive_link = add_link(TEXT_ID, 0, SAMPLER_ID, 1, "CONDITIONING")
    negative_link = add_link(ZERO_ID, 0, SAMPLER_ID, 2, "CONDITIONING")
    latent_link = add_link(LATENT_ID, 0, SAMPLER_ID, 3, "LATENT")
    sample_link = add_link(SAMPLER_ID, 0, DECODE_ID, 0, "LATENT")
    vae_link = add_link(VAE_ID, 0, DECODE_ID, 1, "VAE")
    image_link = add_link(DECODE_ID, 0, SAVE_ID, 0, "IMAGE")

    nodes: list[dict[str, Any]] = [
        _node(
            UNET_ID,
            "UNETLoader",
            [40, 60],
            [330, 106],
            0,
            [UNET_NAME, "default"],
            [_in("unet_name", "COMBO", widget=True), _in("weight_dtype", "COMBO", widget=True)],
            [_out("MODEL", "MODEL", [model_links[0]])],
        ),
        _node(
            CLIP_ID,
            "CLIPLoader",
            [40, 210],
            [330, 130],
            1,
            [CLIP_NAME, CLIP_TYPE, "default"],
            [
                _in("clip_name", "COMBO", widget=True),
                _in("type", "COMBO", widget=True),
                _in("device", "COMBO", widget=True),
            ],
            [_out("CLIP", "CLIP", [clip_link])],
        ),
        _node(
            VAE_ID,
            "VAELoader",
            [40, 380],
            [330, 79],
            2,
            [VAE_NAME],
            [_in("vae_name", "COMBO", widget=True)],
            [_out("VAE", "VAE", [vae_link])],
        ),
        _node(
            TEXT_ID,
            "CLIPTextEncode",
            [440, 60],
            [420, 200],
            3,
            [DEFAULT_PROMPT],
            [_in("clip", "CLIP", clip_link), _in("text", "STRING", widget=True)],
            [_out("CONDITIONING", "CONDITIONING", [zero_link, positive_link])],
        ),
        _node(
            ZERO_ID,
            "ConditioningZeroOut",
            [440, 300],
            [300, 60],
            4,
            [],
            [_in("conditioning", "CONDITIONING", zero_link)],
            [_out("CONDITIONING", "CONDITIONING", [negative_link])],
        ),
        _node(
            LATENT_ID,
            "EmptyLatentImage",
            [440, 400],
            [330, 130],
            5,
            [832, 1248, 1],
            [
                _in("width", "INT", widget=True),
                _in("height", "INT", widget=True),
                _in("batch_size", "INT", widget=True),
            ],
            [_out("LATENT", "LATENT", [latent_link])],
        ),
        _node(
            SAMPLER_ID,
            "KSampler",
            [900, 60],
            [330, 340],
            6 + len(loras),
            [0, "fixed", STEPS, CFG, SAMPLER, SCHEDULER, 1],
            [
                _in("model", "MODEL", model_links[-1]),
                _in("positive", "CONDITIONING", positive_link),
                _in("negative", "CONDITIONING", negative_link),
                _in("latent_image", "LATENT", latent_link),
                _in("seed", "INT", widget=True),
                _in("steps", "INT", widget=True),
                _in("cfg", "FLOAT", widget=True),
                _in("sampler_name", "COMBO", widget=True),
                _in("scheduler", "COMBO", widget=True),
                _in("denoise", "FLOAT", widget=True),
            ],
            [_out("LATENT", "LATENT", [sample_link])],
        ),
        _node(
            DECODE_ID,
            "VAEDecode",
            [1280, 60],
            [240, 70],
            7 + len(loras),
            [],
            [
                _in("samples", "LATENT", sample_link),
                _in("vae", "VAE", vae_link),
            ],
            [_out("IMAGE", "IMAGE", [image_link])],
        ),
        _node(
            SAVE_ID,
            "SaveImage",
            [1280, 180],
            [420, 460],
            8 + len(loras),
            [API_NAME],
            [_in("images", "IMAGE", image_link)],
        ),
    ]

    for index, (lora, node_id) in enumerate(zip(loras, lora_ids)):
        x = 40 if index % 2 == 0 else 210
        y = 500 + (index // 2) * 130
        nodes.append(
            _node(
                node_id,
                "LoraLoaderModelOnly",
                [x, y],
                [300, 80],
                9 + index,
                [lora["lora_name"], 0],
                [_in("model", "MODEL", model_links[index])],
                [_out("MODEL", "MODEL", [model_links[index + 1]])],
            )
        )

    return {
        "last_node_id": max(node["id"] for node in nodes),
        "last_link_id": len(links),
        "nodes": nodes,
        "links": links,
        "groups": [],
        "config": {},
        "extra": {},
        "version": 0.4,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def load_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = json.loads(CATALOG_PATH.read_text("utf-8"))
    unique: dict[str, dict[str, Any]] = {}
    for entry in catalog:
        unique.setdefault(str(entry["id"]), entry)
    return [
        {**entry, "lora_name": f"{entry['slug']}.safetensors"}
        for entry in unique.values()
    ]


def main() -> None:
    loras = load_catalog()
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)

    expected = {f"{API_NAME}.json", f"{UI_NAME}.json"}
    removed = []
    for path in WORKFLOWS_DIR.glob("krea2_turbo*.json"):
        if path.name not in expected:
            path.unlink()
            removed.append(path.name)

    write_json(WORKFLOWS_DIR / f"{API_NAME}.json", build_api_graph(loras))
    write_json(WORKFLOWS_DIR / f"{UI_NAME}.json", build_ui_graph(loras))

    manifest = [
        {
            "node": str(FIRST_LORA_NODE + index),
            "lora_name": lora["lora_name"],
            "title": lora["title"],
            "civitai_id": str(lora["id"]),
            "category": lora["category"],
            "recommended_strength": float(lora.get("strength", 1.0)),
            "workflows": [API_NAME, UI_NAME],
            "source": f"https://civitai.red/models/{lora['id']}",
        }
        for index, lora in enumerate(loras)
    ]
    write_json(MANIFEST_PATH, manifest)
    print(f"loras: {len(loras)}")
    print(f"removed: {', '.join(removed) or 'none'}")
    print(f"files: {API_NAME}.json (api), {UI_NAME}.json (ui)")
    print(f"manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()

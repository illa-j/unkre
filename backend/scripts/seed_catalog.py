"""Seed every workflow and LoRA catalog into the database.

Reads the manifests that mirror the workflow graphs in
``src/adapters/runpod/workflows`` and upserts:

* one ``workflows`` row per executable API graph;
* one ``loras`` row per ``lora_name`` (shared across workflows when the name is
  identical);
* the exact ``workflow_loras`` links declared by each manifest.

The script is idempotent: UUIDs are derived from names, so reruns update the same
rows instead of creating duplicates. Links not present in a manifest are removed
for that workflow, which keeps the seeded catalog authoritative.

Run from the backend directory:

    PYTHONPATH=src .venv/bin/python scripts/seed_catalog.py
    PYTHONPATH=src .venv/bin/python scripts/seed_catalog.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError

from adapters.database import session_scope
from adapters.database.models import LoraModel, WorkflowModel, workflow_loras

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_ROOT = SCRIPT_DIR.parent
WORKFLOWS_DIR = BACKEND_ROOT / "src" / "adapters" / "runpod" / "workflows"
NAMESPACE = uuid.NAMESPACE_URL

CATALOG: tuple[dict[str, Any], ...] = (
    {
        "name": "krea2_turbo_all_api",
        "manifest": "krea2_turbo_manifest.json",
        "description": (
            "Krea 2 Turbo: 8-step distilled model for fast, photorealistic images."
        ),
        "credits": 1,
    },
    {
        "name": "Qwen Image 2.1",
        "manifest": "qwen_image21_manifest.json",
        "description": "Qwen Image 2.1: text prompts and reference photos.",
        "credits": 1,
    },
)


def ident(kind: str, name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, f"unkre:{kind}:{name}")


def graph_loras(workflow_name: str) -> set[str]:
    path = WORKFLOWS_DIR / f"{workflow_name}.json"
    if not path.is_file():
        raise SystemExit(f"Missing workflow graph: {path}")
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(graph, dict):
        raise SystemExit(f"Expected an API graph object: {path}")
    return {
        node["inputs"]["lora_name"]
        for node in graph.values()
        if isinstance(node, dict)
        and node.get("class_type") == "LoraLoaderModelOnly"
        and isinstance(node.get("inputs"), dict)
        and isinstance(node["inputs"].get("lora_name"), str)
    }


def load_catalog() -> list[tuple[dict[str, str], list[dict[str, Any]]]]:
    catalog = []
    for spec in CATALOG:
        manifest_path = SCRIPT_DIR / spec["manifest"]
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or not entries:
            raise SystemExit(f"Expected a non-empty manifest: {manifest_path}")
        names = [str(entry["lora_name"]) for entry in entries]
        if len(names) != len(set(names)):
            raise SystemExit(f"Duplicate LoRA names in {manifest_path}")
        declared = set(names)
        used = graph_loras(spec["name"])
        missing = declared - used
        unused = used - declared
        if missing or unused:
            raise SystemExit(
                f"Manifest does not match {spec['name']}.json: "
                f"in manifest only={sorted(missing)}, in graph only={sorted(unused)}"
            )
        catalog.append((spec, entries))
    return catalog


def summarize(catalog: list[tuple[dict[str, str], list[dict[str, Any]]]]) -> None:
    all_names: set[str] = set()
    for spec, entries in catalog:
        names = {str(entry["lora_name"]) for entry in entries}
        all_names |= names
        print(f"  {spec['name']}: {len(entries)} LoRA")
    print(
        f"workflows: {len(catalog)}, LoRA rows: {len(all_names)} "
        f"(shared names are stored once)"
    )


async def seed(catalog: list[tuple[dict[str, str], list[dict[str, Any]]]]) -> None:
    async with session_scope() as session:
        workflows = {
            row.name: row
            for row in (await session.scalars(select(WorkflowModel))).all()
        }
        loras = {
            row.name: row for row in (await session.scalars(select(LoraModel))).all()
        }
        created_workflows = created_loras = updated_links = 0

        for spec, entries in catalog:
            workflow = workflows.get(spec["name"])
            if workflow is None:
                workflow = WorkflowModel(
                    id=ident("workflow", spec["name"]),
                    name=spec["name"],
                    description=spec["description"],
                    generation_credits=spec["credits"],
                )
                session.add(workflow)
                workflows[spec["name"]] = workflow
                created_workflows += 1
            else:
                workflow.description = spec["description"]

            ordered = []
            for entry in entries:
                name = str(entry["lora_name"])
                lora = loras.get(name)
                if lora is None:
                    lora = LoraModel(
                        id=ident("lora", name),
                        name=name,
                        description=entry.get("title") or None,
                        preview_urls=[],
                        is_nsfw=entry.get("category") == "nsfw",
                    )
                    session.add(lora)
                    loras[name] = lora
                    created_loras += 1
                else:
                    if entry.get("title"):
                        lora.description = entry["title"]
                    lora.is_nsfw = entry.get("category") == "nsfw"
                ordered.append(lora)

            current = {lora.name for lora in workflow.loras}
            wanted = {lora.name for lora in ordered}
            if current != wanted:
                workflow.loras = ordered
                updated_links += 1

        await session.flush()
        # Strength is per workflow-lora link: the same file can recommend
        # different values for Turbo and Raw.
        for spec, entries in catalog:
            workflow = workflows[spec["name"]]
            by_name = {lora.name: lora for lora in workflow.loras}
            for entry in entries:
                lora = by_name.get(str(entry["lora_name"]))
                if lora is None:
                    continue
                strength = entry.get("recommended_strength")
                await session.execute(
                    update(workflow_loras)
                    .where(
                        workflow_loras.c.workflow_id == workflow.id,
                        workflow_loras.c.lora_id == lora.id,
                    )
                    .values(
                        recommended_strength=float(strength)
                        if strength is not None
                        else None
                    )
                )
        print(
            f"seeded: {created_workflows} new workflows, {created_loras} new LoRA, "
            f"{updated_links} workflows relinked"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate manifests against graphs and print the plan without writing",
    )
    args = parser.parse_args()
    catalog = load_catalog()
    summarize(catalog)
    if args.dry_run:
        print("dry run: no database writes")
        return
    try:
        asyncio.run(seed(catalog))
    except (OSError, OperationalError) as exc:
        raise SystemExit(
            "Cannot connect to Postgres. The production Compose stack does not "
            "publish the database port; run the seeder inside the stack instead:\n"
            "  docker compose --profile tools run --rm seed\n"
            "For a local database, set POSTGRES_HOST/POSTGRES_DB_PORT in backend/.env."
        ) from exc


if __name__ == "__main__":
    main()

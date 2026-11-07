import base64
import json

import pytest

from adapters.runpod import workflow as workflow_module
from adapters.runpod.workflow import build_input
from domain.exceptions import (
    InvalidLoraStrengthsError,
    InvalidWorkflowError,
    ValidationError,
)


@pytest.fixture
def graph():
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": "model.safetensors"},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "original positive", "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "original negative", "clip": ["1", 1]},
        },
        "4": {
            "class_type": "KSampler",
            "inputs": {
                "seed": 1,
                "positive": ["2", 0],
                "negative": ["3", 0],
                "model": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "5": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": 512, "height": 512, "batch_size": 1},
        },
        "7": {
            "class_type": "LoraLoaderModelOnly",
            "inputs": {
                "model": ["1", 0],
                "lora_name": "style.safetensors",
                "strength_model": 0.8,
            },
        },
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "output"}},
    }


@pytest.fixture
def save_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_module, "WORKFLOWS_DIR", tmp_path)

    def save(graph, name="portrait"):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(graph), encoding="utf-8")
        return path

    return save


def test_standard_api_graph_updates_seed_conditioning_and_size(graph, save_workflow):
    path = save_workflow(graph)
    original = path.read_bytes()
    result = build_input(
        [],
        42,
        "portrait",
        'new "prompt" \\ line\n{{seed}}',
        "new negative",
        (768, 1024),
    )
    nodes = result["workflow"]
    assert nodes["4"]["inputs"]["seed"] == 42
    assert nodes["2"]["inputs"]["text"] == 'new "prompt" \\ line\n{{seed}}'
    assert nodes["3"]["inputs"]["text"] == "new negative"
    assert nodes["5"]["inputs"]["width"] == 768
    assert nodes["5"]["inputs"]["height"] == 1024
    assert nodes["8"]["inputs"]["filename_prefix"] == "output"
    assert "images" not in result
    assert path.read_bytes() == original


def test_workflow_name_with_extension(graph, save_workflow):
    save_workflow(graph)
    assert (
        build_input([], 0, "portrait.json", "test")["workflow"]["4"]["inputs"]["seed"]
        == 0
    )


def test_template_substitution_preserves_json_types_and_prompt_text(save_workflow):
    save_workflow(
        {
            "1": {
                "class_type": "Custom",
                "inputs": {
                    "seed": "{{seed}}",
                    "width": "{{width}}",
                    "height": "{{height}}",
                    "text": "prefix {{prompt}} suffix",
                    "negative": "{{negative_prompt}}",
                },
            }
        }
    )
    result = build_input(
        [], 2**63 - 1, "portrait", 'text " \\ \n {{width}}', size=(640, 768)
    )
    inputs = result["workflow"]["1"]["inputs"]
    assert inputs["seed"] == 2**63 - 1
    assert inputs["width"] == 640 and inputs["height"] == 768
    assert inputs["text"] == 'prefix text " \\ \n {{width}} suffix'
    assert inputs["negative"] == ""


def test_unquoted_numeric_template(save_workflow):
    path = save_workflow(
        {
            "1": {
                "class_type": "Custom",
                "inputs": {"seed": "{{seed}}", "text": "{{prompt}}"},
            }
        }
    )
    path.write_text(path.read_text().replace('"{{seed}}"', "{{seed}}"))
    assert (
        build_input([], 9, "portrait", "test")["workflow"]["1"]["inputs"]["seed"] == 9
    )


def test_positive_conditioning_chain(graph, save_workflow):
    graph["6"] = {
        "class_type": "ConditioningSetArea",
        "inputs": {"conditioning": ["2", 0]},
    }
    graph["4"]["inputs"]["positive"] = ["6", 0]
    save_workflow(graph)
    nodes = build_input([], 4, "portrait", "new")["workflow"]
    assert nodes["2"]["inputs"]["text"] == "new"
    assert nodes["3"]["inputs"]["text"] == ""


@pytest.mark.parametrize("field", ["strength_lora", "strength_model", "strength"])
def test_lora_is_selected_by_name_and_uses_only_existing_weight(
    field, graph, save_workflow
):
    inputs = graph["7"]["inputs"]
    del inputs["strength_model"]
    inputs[field] = 0.8
    original_keys = set(inputs)
    save_workflow(graph)
    output = build_input(
        [], 4, "portrait", "test", loras_strength={"style.safetensors": -0.25}
    )
    assert output["workflow"]["7"]["inputs"][field] == -0.25
    assert set(output["workflow"]["7"]["inputs"]) == original_keys


def test_unselected_loras_are_disabled(graph, save_workflow):
    graph["9"] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"lora_name": "other.safetensors", "strength_model": 1},
    }
    save_workflow(graph)
    output = build_input(
        [], 1, "portrait", "test", loras_strength={"style.safetensors": 0.5}
    )["workflow"]
    assert output["7"]["inputs"]["strength_model"] == 0.5
    assert output["9"]["inputs"]["strength_model"] == 0
    empty = build_input([], 1, "portrait", "test", loras_strength={})["workflow"]
    assert empty["7"]["inputs"]["strength_model"] == 0


def test_unknown_lora_is_rejected(graph, save_workflow):
    save_workflow(graph)
    with pytest.raises(InvalidLoraStrengthsError):
        build_input(
            [], 1, "portrait", "test", loras_strength={"missing.safetensors": 1}
        )


@pytest.mark.parametrize("value", [True, "1", float("nan"), float("inf")])
def test_invalid_lora_strength_is_rejected(value, graph, save_workflow):
    save_workflow(graph)
    with pytest.raises(ValidationError):
        build_input(
            [], 1, "portrait", "test", loras_strength={"style.safetensors": value}
        )


def test_text_only_request_drops_the_reference_branch(graph, save_workflow):
    graph["9"] = {"class_type": "LoadImage", "inputs": {"image": "input.png"}}
    graph["2"]["inputs"]["images.image_1"] = ["9", 0]
    graph["10"] = {
        "class_type": "ConditioningZeroOut",
        "inputs": {"conditioning": ["9", 0]},
    }
    save_workflow(graph)
    nodes = build_input([], 7, "portrait", "new")["workflow"]
    assert "9" not in nodes and "10" not in nodes
    assert "images.image_1" not in nodes["2"]["inputs"]
    assert nodes["2"]["inputs"]["text"] == "new" and nodes["4"]["inputs"]["seed"] == 7


def test_extra_reference_slots_are_created_for_the_encoder(graph, save_workflow):
    graph["9"] = {"class_type": "LoadImage", "inputs": {"image": "input.png"}}
    graph["2"]["inputs"]["images.image_1"] = ["9", 0]
    save_workflow(graph)

    payload = build_input([b"first", b"second", b"third"], 1, "portrait", "test")

    nodes = payload["workflow"]
    assert nodes["2"]["inputs"]["images.image_2"] == ["10", 0]
    assert nodes["2"]["inputs"]["images.image_3"] == ["11", 0]
    assert nodes["10"] == {
        "class_type": "LoadImage",
        "inputs": {"image": "input_2.png"},
    }
    assert [item["name"] for item in payload["images"]] == [
        "input.png",
        "input_2.png",
        "input_3.png",
    ]


def test_multiple_input_images(graph, save_workflow):
    for node_id, filename in (("9", "input.png"), ("10", "input_2.png")):
        graph[node_id] = {"class_type": "LoadImage", "inputs": {"image": filename}}
    save_workflow(graph)
    payload = build_input([b"first", b"second"], 1, "portrait", "test")
    assert payload["images"] == [
        {"name": "input.png", "image": base64.b64encode(b"first").decode()},
        {"name": "input_2.png", "image": base64.b64encode(b"second").decode()},
    ]
    with pytest.raises(InvalidWorkflowError, match="input_2.png"):
        build_input([b"first"], 1, "portrait", "test")


@pytest.mark.parametrize(
    "name", ["../outside", "/outside", "folder/name", "folder\\name", ".", ".."]
)
def test_path_traversal_is_rejected(name, save_workflow):
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, name, "test")


def test_symlink_outside_workflows_is_rejected(tmp_path, save_workflow):
    outside = tmp_path.parent / "outside.json"
    outside.write_text("{}")
    (tmp_path / "portrait.json").symlink_to(outside)
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, "portrait", "test")


@pytest.mark.parametrize("seed", [True, -1, 2**63, 1.5])
def test_seed_matches_generation_constraints(seed, graph, save_workflow):
    save_workflow(graph)
    with pytest.raises(ValidationError):
        build_input([], seed, "portrait", "test")


@pytest.mark.parametrize(
    "graph", [{}, [], {"nodes": []}, {"1": {"class_type": "Test"}}]
)
def test_non_api_graph_is_rejected(graph, save_workflow):
    save_workflow(graph)
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, "portrait", "test")


def test_invalid_json_and_missing_workflow(save_workflow):
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, "portrait", "test")
    path = save_workflow({})
    path.write_text("invalid json")
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, "portrait", "test")


def test_missing_template_dimension_is_rejected(save_workflow):
    save_workflow(
        {
            "1": {
                "class_type": "Custom",
                "inputs": {
                    "seed": "{{seed}}",
                    "text": "{{prompt}}",
                    "width": "{{width}}",
                },
            }
        }
    )
    with pytest.raises(InvalidWorkflowError):
        build_input([], 1, "portrait", "test")


@pytest.mark.parametrize(
    "strengths,expected",
    [({}, 0), ({"style.safetensors": 0}, 0), ({"style.safetensors": 0.5}, 0.5)],
)
def test_lora_model_and_clip_weights_are_applied_together(
    graph, save_workflow, strengths, expected
):
    graph["7"]["class_type"] = "LoraLoader"
    graph["7"]["inputs"].update(clip=["1", 1], strength_clip=0.8)
    save_workflow(graph)
    inputs = build_input([], 1, "portrait", "test", loras_strength=strengths)[
        "workflow"
    ]["7"]["inputs"]
    assert inputs["strength_model"] == inputs["strength_clip"] == expected
    assert inputs["clip"] == ["1", 1]

import base64
import json
from types import SimpleNamespace

import httpx
import pytest

from adapters.runpod import RunPodClient
from adapters.runpod import workflow as workflow_module
from adapters.settings import RunPodSettings
from domain.enums import GenerationStatus
from domain.exceptions import (
    InvalidRunPodResponseError,
    RunPodNotConfiguredError,
    RunPodRequestError,
)


@pytest.fixture
async def runpod(tmp_path, monkeypatch):
    monkeypatch.setattr(workflow_module, "WORKFLOWS_DIR", tmp_path)
    (tmp_path / "portrait.json").write_text(
        json.dumps(
            {
                "1": {
                    "class_type": "Custom",
                    "inputs": {
                        "seed": "{{seed}}",
                        "text": "{{prompt}}",
                    },
                }
            }
        )
    )
    state = SimpleNamespace(
        payload={"id": "job-1", "status": "IN_QUEUE"},
        status=200,
        requests=[],
        error=None,
        text=None,
    )

    def handler(request):
        state.requests.append(request)
        if state.error:
            raise state.error
        if state.text is not None:
            return httpx.Response(state.status, text=state.text)
        return httpx.Response(state.status, json=state.payload)

    settings = RunPodSettings(
        RUNPOD_API_KEY="test-key",
        RUNPOD_ENDPOINT_ID="endpoint-1",
        RUNPOD_TIMEOUT_SECONDS=4,
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        state.client = RunPodClient(settings, http)
        state.http = http
        state.settings = settings
        yield state


async def test_submit_uses_project_settings_and_comfyui_payload(runpod):
    job_id = await runpod.client.run([], 42, "portrait", 'a "portrait"')
    assert job_id == "job-1" and len(runpod.requests) == 1
    request = runpod.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.runpod.ai/v2/endpoint-1/run"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content)["input"]["workflow"]["1"]["inputs"] == {
        "seed": 42,
        "text": 'a "portrait"',
    }
    assert request.extensions["timeout"]["read"] == 4


async def test_uploaded_base64_is_validated_before_http(runpod):
    with pytest.raises(ValueError):
        await runpod.client.run(["not-base64"], 1, "portrait", "test")
    assert not runpod.requests


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("IN_QUEUE", GenerationStatus.QUEUED),
        ("IN_PROGRESS", GenerationStatus.PROCESSING),
        ("COMPLETED", GenerationStatus.COMPLETED),
        ("FAILED", GenerationStatus.FAILED),
        ("CANCELLED", GenerationStatus.CANCELLED),
        ("TIMED_OUT", GenerationStatus.TIMED_OUT),
    ],
)
async def test_status_maps_to_generation_enum(runpod, raw, expected):
    runpod.payload = {"status": raw}
    assert await runpod.client.status("job-1") == expected
    assert str(runpod.requests[0].url).endswith("/endpoint-1/status/job-1")


@pytest.mark.parametrize("status", [None, "UNKNOWN", 1, []])
async def test_unknown_status_is_rejected(runpod, status):
    runpod.payload = {"status": status}
    with pytest.raises(InvalidRunPodResponseError):
        await runpod.client.status("job-1")


async def test_saved_endpoint_is_used_for_job_operations(runpod):
    runpod.settings.RUNPOD_ENDPOINT_ID = ""
    await runpod.client.status("job-1", endpoint_id="saved-endpoint")
    assert "/saved-endpoint/status/job-1" in str(runpod.requests[-1].url)
    runpod.payload = {"status": "CANCELLED"}
    assert (
        await runpod.client.cancel("job-1", endpoint_id="saved-endpoint")
        == GenerationStatus.CANCELLED
    )
    assert runpod.requests[-1].method == "POST"
    assert "/saved-endpoint/cancel/job-1" in str(runpod.requests[-1].url)
    with pytest.raises(RunPodNotConfiguredError):
        await runpod.client.status("job-1")


async def test_submit_can_override_default_endpoint(runpod):
    await runpod.client.run([], 1, "portrait", "test", endpoint_id="other-endpoint")
    assert str(runpod.requests[-1].url).endswith("/other-endpoint/run")


def test_workflow_endpoints_parse_from_compact_and_json():
    compact = RunPodSettings(
        RUNPOD_ENDPOINTS="krea2_turbo_all_api=ep-turbo, krea2_raw_t2image_api=ep-raw"
    )
    assert compact.RUNPOD_ENDPOINTS == {
        "krea2_turbo_all_api": "ep-turbo",
        "krea2_raw_t2image_api": "ep-raw",
    }
    as_json = RunPodSettings(RUNPOD_ENDPOINTS='{"Qwen Image 2.1": "ep-qwen"}')
    assert as_json.RUNPOD_ENDPOINTS == {"Qwen Image 2.1": "ep-qwen"}
    assert RunPodSettings(RUNPOD_ENDPOINTS="").RUNPOD_ENDPOINTS == {}


def test_workflow_endpoints_reject_duplicates_and_empty_pairs():
    from pydantic import ValidationError

    for value in ("a=ep1,a=ep2", "a=", "=ep", "a"):
        with pytest.raises(ValidationError):
            RunPodSettings(RUNPOD_ENDPOINTS=value)


async def test_each_workflow_uses_its_own_endpoint(runpod):
    runpod.settings.RUNPOD_ENDPOINTS = {
        "portrait": "ep-portrait",
        "other": "ep-other",
    }
    assert runpod.client.endpoint_for("portrait") == "ep-portrait"
    await runpod.client.run([], 1, "portrait", "test")
    assert str(runpod.requests[-1].url) == ("https://api.runpod.ai/v2/ep-portrait/run")
    assert runpod.client.endpoint_for("other") == "ep-other"
    with pytest.raises(RunPodNotConfiguredError):
        runpod.client.endpoint_for("missing")
    with pytest.raises(RunPodNotConfiguredError):
        runpod.client.endpoint_for("")


async def test_error_is_returned(runpod):
    runpod.payload = {"status": "FAILED", "error": "Worker failed"}
    assert await runpod.client.error("job-1") == "Worker failed"


async def test_result_decodes_inline_media_without_fetching_urls(runpod):
    raw = b"\x89PNG\r\n\x1a\nimage-data"
    runpod.payload = {
        "status": "COMPLETED",
        "output": {
            "images": [
                {"type": "s3_url", "data": "https://external.example/image.png"},
                {"type": "base64", "data": base64.b64encode(raw).decode()},
            ]
        },
    }
    assert await runpod.client.decode_result("job-1") == raw
    assert len(runpod.requests) == 1


async def test_result_accepts_base64_data_uri(runpod):
    runpod.payload = {
        "status": "COMPLETED",
        "output": {
            "images": [
                {
                    "type": "base64",
                    "data": "data:image/png;base64,"
                    + base64.b64encode(b"image").decode(),
                },
            ]
        },
    }
    assert await runpod.client.decode_result("job-1") == b"image"


@pytest.mark.parametrize(
    "status,output",
    [
        ("IN_QUEUE", None),
        ("IN_PROGRESS", None),
        ("FAILED", None),
        (
            "COMPLETED",
            {
                "images": [
                    {"type": "s3_url", "data": "https://external.example/image.png"}
                ]
            },
        ),
    ],
)
async def test_no_inline_result_returns_none(runpod, status, output):
    runpod.payload = {"status": status, "output": output}
    assert await runpod.client.decode_result("job-1") is None
    assert len(runpod.requests) == 1


@pytest.mark.parametrize("data", ["bad-base64", "", None])
async def test_invalid_result_is_rejected(runpod, data):
    runpod.payload = {
        "status": "COMPLETED",
        "output": {"images": [{"type": "base64", "data": data}]},
    }
    with pytest.raises(InvalidRunPodResponseError):
        await runpod.client.decode_result("job-1")


@pytest.mark.parametrize("code", [301, 400, 401, 429, 500])
async def test_http_failures_are_not_retried(runpod, code):
    runpod.status = code
    with pytest.raises(RunPodRequestError):
        await runpod.client.run([], 1, "portrait", "test")
    assert len(runpod.requests) == 1


async def test_timeout_is_wrapped_without_retry(runpod):
    runpod.error = httpx.ReadTimeout("timed out")
    with pytest.raises(RunPodRequestError):
        await runpod.client.run([], 1, "portrait", "test")
    assert len(runpod.requests) == 1


@pytest.mark.parametrize("payload", [None, [], "not-an-object"])
async def test_invalid_response_shape(runpod, payload):
    runpod.payload = payload
    with pytest.raises(InvalidRunPodResponseError):
        await runpod.client.status("job-1")


async def test_invalid_json_is_rejected(runpod):
    runpod.text = "not-json"
    with pytest.raises(InvalidRunPodResponseError):
        await runpod.client.status("job-1")


@pytest.mark.parametrize("job_id", [None, "", " ", 1, "../other", "x" * 256])
async def test_invalid_submission_job_id(runpod, job_id):
    runpod.payload = {"id": job_id}
    with pytest.raises(InvalidRunPodResponseError):
        await runpod.client.run([], 1, "portrait", "test")


async def test_external_client_is_not_closed(runpod):
    await runpod.client.close()
    assert not runpod.http.is_closed


async def test_owned_client_is_closed_by_context_manager():
    client = RunPodClient(RunPodSettings(RUNPOD_API_KEY="test-key"))
    async with client:
        assert not client._client.is_closed
    assert client._client.is_closed


async def test_empty_api_key_is_rejected_before_http(runpod):
    runpod.settings.RUNPOD_API_KEY = ""
    with pytest.raises(RunPodNotConfiguredError):
        await runpod.client.status("job-1")
    assert not runpod.requests


async def test_missing_job_has_a_specific_error_but_submission_failure_does_not(runpod):
    from domain.exceptions.runpod import RunPodJobNotFoundError

    runpod.status = 404
    with pytest.raises(RunPodJobNotFoundError):
        await runpod.client.decode_result("expired-job")
    with pytest.raises(RunPodRequestError) as error:
        await runpod.client.run([], 1, "portrait", "test")
    assert not isinstance(error.value, RunPodJobNotFoundError)

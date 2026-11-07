import uuid

import pytest
from sqlalchemy import String, create_engine, event, update
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from adapters.database.models import (
    Base,
    GenerationModel,
    LoraModel,
    UserModel,
    WorkflowModel,
)
from domain.exceptions import ValidationError
from domain.exceptions.generation import (
    InvalidLoraStrengthsError,
    InvalidPreviewUrlsError,
    LoraNotFoundError,
    LoraNotInWorkflowError,
    WorkflowMismatchError,
    WorkflowNotFoundError,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    try:
        with Session(engine, expire_on_commit=False) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def data(session):
    lora = LoraModel(name="Style", preview_urls=["https://example.com/style.png"])
    other = LoraModel(name="Other")
    workflow = WorkflowModel(name="Portrait", loras=[lora])
    user = UserModel(first_name="Test")
    session.add_all([workflow, other, user])
    session.commit()
    return workflow, lora, other, user


def generation(data, **kwargs):
    workflow, lora, other, user = data
    values = dict(user=user, workflow=workflow, prompt="Portrait", seed=42)
    values.update(kwargs)
    return GenerationModel(**values)


def test_round_trip(session, data):
    workflow, lora, _, _ = data
    item = generation(data, loras_strength={str(lora.id): 0.75})
    session.add(item)
    session.commit()
    item_id = item.id
    session.expunge_all()
    saved = session.get(GenerationModel, item_id)
    assert saved.prompt == "Portrait"
    assert saved.seed == 42
    assert saved.workflow.name == "Portrait"
    assert saved.loras_strength == {str(lora.id): 0.75}
    assert saved.workflow.loras[0].preview_urls == ["https://example.com/style.png"]
    for obj in (saved, saved.workflow, saved.workflow.loras[0]):
        assert obj.created_at is not None
        assert obj.updated_at is not None


def test_no_loras_required(session, data):
    item = generation(data)
    session.add(item)
    session.commit()
    assert item.loras_strength == {}


@pytest.mark.parametrize("exists", [False, True])
def test_reject_unknown_or_unavailable_lora(session, data, exists):
    lora_id = data[2].id if exists else uuid.uuid7()
    session.add(generation(data, loras_strength={str(lora_id): 1}))
    with pytest.raises(LoraNotInWorkflowError if exists else LoraNotFoundError):
        session.flush()


@pytest.mark.parametrize("value", [None, [], {"bad": 1}, {1: 1}])
def test_reject_invalid_json(value):
    with pytest.raises(InvalidLoraStrengthsError):
        GenerationModel(loras_strength=value)


@pytest.mark.parametrize("value", [None, True, "1", float("nan"), float("inf")])
def test_reject_invalid_strength(value):
    with pytest.raises(ValidationError):
        GenerationModel(loras_strength={str(uuid.uuid7()): value})


def test_mutation_is_validated_and_persisted(session, data):
    key = str(data[1].id)
    item = generation(data, loras_strength={key: 1})
    session.add(item)
    session.commit()
    item.loras_strength[key] = 0.5
    session.commit()
    session.refresh(item)
    assert item.loras_strength == {key: 0.5}
    item.loras_strength[str(data[2].id)] = 1
    with pytest.raises(LoraNotInWorkflowError):
        session.flush()


def test_mutation_rejects_invalid_numeric_value(session, data):
    key = str(data[1].id)
    item = generation(data, loras_strength={key: 1})
    session.add(item)
    session.commit()
    item.loras_strength[key] = True
    with pytest.raises(ValidationError):
        session.flush()


@pytest.mark.parametrize("via_fk", [False, True])
def test_workflow_change_revalidates_loras(session, data, via_fk):
    item = generation(data, loras_strength={str(data[1].id): 1})
    new_workflow = WorkflowModel(name="Empty")
    session.add_all([item, new_workflow])
    session.commit()
    if via_fk:
        item.workflow_id = new_workflow.id
    else:
        item.workflow = new_workflow
    with pytest.raises(LoraNotInWorkflowError):
        session.flush()


def test_removing_lora_from_workflow_revalidates_generations(session, data):
    item = generation(data, loras_strength={str(data[1].id): 1})
    session.add(item)
    session.commit()
    session.expunge_all()
    workflow = session.get(WorkflowModel, data[0].id)
    workflow.loras.clear()
    with pytest.raises(LoraNotInWorkflowError):
        session.flush()


def test_deleting_lora_revalidates_generations(session, data):
    item = generation(data, loras_strength={str(data[1].id): 1})
    session.add(item)
    session.commit()
    session.delete(data[1])
    with pytest.raises(LoraNotFoundError):
        session.flush()


def test_accept_pending_workflow_and_lora(session):
    lora = LoraModel(id=uuid.uuid7(), name="Style")
    workflow = WorkflowModel(name="New", loras=[lora])
    item = GenerationModel(
        user=UserModel(first_name="Test"),
        workflow=workflow,
        prompt="Portrait",
        loras_strength={str(lora.id): 1},
    )
    session.add(item)
    session.commit()
    assert item.workflow_id == workflow.id


def test_unknown_workflow(session, data):
    item = generation(data)
    item.workflow = None
    item.workflow_id = uuid.uuid7()
    session.add(item)
    with pytest.raises(WorkflowNotFoundError):
        session.flush()


def test_conflicting_workflow_and_id(session, data):
    other = WorkflowModel(name="Other")
    session.add(other)
    session.commit()
    session.add(generation(data, workflow_id=other.id))
    with pytest.raises(WorkflowMismatchError):
        session.flush()


@pytest.mark.parametrize("value", [None, "url", [None], [""], [" "]])
def test_invalid_preview_urls(value):
    with pytest.raises(InvalidPreviewUrlsError):
        LoraModel(preview_urls=value)


def test_preview_mutation(session, data):
    data[1].preview_urls.append(123)
    with pytest.raises(InvalidPreviewUrlsError):
        session.flush()


def test_postgres_schema_uses_jsonb():
    ddl = str(
        CreateTable(GenerationModel.__table__).compile(dialect=postgresql.dialect())
    )
    assert "loras_strength JSONB NOT NULL" in ddl
    assert "REFERENCES workflows (id) ON DELETE RESTRICT" in ddl
    assert "preview_urls JSONB NOT NULL" in str(
        CreateTable(LoraModel.__table__).compile(dialect=postgresql.dialect())
    )


@pytest.mark.parametrize("value", [None, "", "  ", 42])
def test_invalid_prompt(value):
    with pytest.raises(ValidationError):
        GenerationModel(prompt=value)


@pytest.mark.parametrize("value", [-1, 2**63, True, 1.5])
def test_invalid_seed(value):
    with pytest.raises(ValidationError):
        GenerationModel(seed=value)


def test_existing_workflow_by_id(session, data):
    item = GenerationModel(
        user=data[3],
        workflow_id=data[0].id,
        prompt="Portrait",
        loras_strength={str(data[1].id): 0},
    )
    session.add(item)
    session.commit()
    assert item.workflow.id == data[0].id


def test_multiple_workflows_share_lora(session, data):
    second = WorkflowModel(name="Second", loras=[data[1]])
    item = generation(data, workflow=second, loras_strength={str(data[1].id): -0.5})
    session.add(item)
    session.commit()
    assert len(data[1].workflows) == 2


@pytest.mark.parametrize("via_fk", [False, True])
def test_workflow_change_with_compatible_loras(session, data, via_fk):
    second = WorkflowModel(name="Second", loras=[data[1]])
    item = generation(data, loras_strength={str(data[1].id): 0.5})
    session.add_all([item, second])
    session.commit()
    if via_fk:
        item.workflow_id = second.id
    else:
        item.workflow = second
    session.commit()
    assert item.workflow_id == second.id
    assert item.workflow is second


def test_clearing_workflow_id_is_rejected(session, data):
    item = generation(data)
    session.add(item)
    session.commit()
    item.workflow_id = None
    with pytest.raises(WorkflowNotFoundError):
        session.flush()


@pytest.mark.parametrize(
    ("model", "field", "value"),
    [
        (WorkflowModel, "name", ""),
        (WorkflowModel, "name", "   "),
        (WorkflowModel, "name", "x" * 256),
        (WorkflowModel, "description", "x" * 4097),
        (LoraModel, "name", ""),
        (LoraModel, "name", "x" * 256),
        (LoraModel, "description", "x" * 4097),
        (LoraModel, "preview_urls", {}),
        (GenerationModel, "prompt", ""),
        (GenerationModel, "prompt", "   "),
        (GenerationModel, "prompt", "x" * 8193),
        (GenerationModel, "error", "x" * 4097),
        (GenerationModel, "runpod_job_id", ""),
        (GenerationModel, "runpod_job_id", "x" * 256),
        (GenerationModel, "runpod_endpoint_id", "x" * 256),
        (GenerationModel, "seed", -1),
        (GenerationModel, "uploaded_images", -1),
        (GenerationModel, "uploaded_images", 32768),
        (GenerationModel, "credits_spent", -1),
        (GenerationModel, "credits_spent", 2**31),
        (GenerationModel, "loras_strength", []),
        (GenerationModel, "status", "invalid"),
    ],
)
def test_database_rejects_invalid_values_without_orm_validation(
    session, data, model, field, value
):
    session.add(generation(data))
    session.commit()
    with pytest.raises(IntegrityError):
        session.execute(update(model.__table__).values({field: value}))


def test_all_string_columns_have_explicit_lengths():
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, String):
                assert column.type.length is not None, f"{table.name}.{column.name}"


@pytest.mark.parametrize("model", [WorkflowModel, LoraModel])
def test_description_limits_match_database(session, model):
    item = model(name="Valid", description="x" * 4096)
    session.add(item)
    session.commit()
    with pytest.raises(ValidationError):
        item.description = "x" * 4097


def test_prompt_limit_matches_database(session, data):
    item = generation(data, prompt="x" * 8192)
    session.add(item)
    session.commit()
    with pytest.raises(ValidationError):
        item.prompt = "x" * 8193

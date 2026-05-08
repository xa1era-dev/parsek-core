from pydantic import BaseModel

from core.schemas.orchestrator.types_ import EnvValues, NestedDict


class SimpleConfBody(BaseModel):
    conf: NestedDict[EnvValues]


class ModuleBody(SimpleConfBody):
    file: str


class CreateTaskBody(BaseModel):
    parser: ModuleBody
    task: SimpleConfBody
    in_pipes: list[ModuleBody]
    out_pipes: list[ModuleBody]
    group_tag: str | None = None

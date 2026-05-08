import uuid as _uuid_lib

from core.modelier import BaseModel


class Query(BaseModel):
    type: str | None = None
    value: str

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.uuid: str = str(_uuid_lib.uuid4())


class Result[T: BaseModel](BaseModel):
    success: bool = False
    query: Query

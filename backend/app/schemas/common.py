from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

T = TypeVar("T")


class ORMSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None
    request_id: str = Field(default="req_placeholder", examples=["req_01J8Z6K9YQ6M2H"])


class ErrorResponse(BaseModel):
    code: str
    message: str
    data: None = None
    details: dict[str, Any] | None = None
    request_id: str


class PaginatedData(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    total: int = Field(default=0, ge=0)
    has_next: bool = False

    @model_validator(mode="after")
    def _set_has_next(self) -> "PaginatedData[T]":
        self.has_next = self.page * self.page_size < self.total
        return self

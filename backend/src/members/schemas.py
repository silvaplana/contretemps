from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class FieldIn(BaseModel):
    label: str = ""
    required: bool = False
    format: str = "short_text"
    choices: list[str] | None = None
    group_id: int | None = None
    multiple: bool = False
    member_sees: bool = False
    member_edits: bool = False
    others_see: bool = False
    for_group_id: int | None = None


class FieldPatch(BaseModel):
    label: str | None = None
    required: bool | None = None
    format: str | None = None
    choices: list[str] | None = None
    group_id: int | None = None
    multiple: bool | None = None
    member_sees: bool | None = None
    member_edits: bool | None = None
    others_see: bool | None = None
    for_group_id: int | None = None


class FieldOut(FieldIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: int


class GroupChoice(BaseModel):
    id: int
    name: str
    children: list[dict] = []


class Choices(BaseModel):
    # « Parmi les groupes de » (format Groupe) et « Pour qui ».
    parents: list[GroupChoice]
    audiences: list[GroupChoice]


class AnswerIn(BaseModel):
    value: Any = None


class AnswerOut(BaseModel):
    field: FieldOut
    value: Any = None


class ColumnIn(BaseModel):
    key: str
    shown: bool = True


class ColumnOut(ColumnIn):
    model_config = ConfigDict(from_attributes=True)

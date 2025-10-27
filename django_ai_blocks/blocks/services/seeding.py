"""Utilities to seed Block and BlockColumnConfig (table setting) records."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Mapping

from django.contrib.auth import get_user_model
from django.db import transaction

from django_ai_blocks.blocks.models.block import Block
from django_ai_blocks.blocks.models.block_column_config import BlockColumnConfig

UserModel = get_user_model()


@transaction.atomic
def create_or_update_blocks(
    definitions: Iterable[Mapping[str, Any]]
) -> list[Block]:
    """Create or update ``Block`` records using the provided definitions.

    Each definition must provide at least a ``code`` field. All other fields are
    passed directly to :meth:`~django.db.models.query.QuerySet.update_or_create`
    as defaults.
    """

    blocks: list[Block] = []

    for payload in definitions:
        data = _validate_mapping(payload, "Block definitions must be mappings.")
        code = data.pop("code", None)
        if not code:
            raise ValueError("Block definition requires a 'code'.")

        block, _ = Block.objects.update_or_create(code=code, defaults=data)
        blocks.append(block)

    return blocks


@transaction.atomic
def create_or_update_block_column_configs(
    definitions: Iterable[Mapping[str, Any]]
) -> list[BlockColumnConfig]:
    """Create or update ``BlockColumnConfig`` records from ``definitions``."""

    configs: list[BlockColumnConfig] = []

    for payload in definitions:
        data = _validate_mapping(
            payload, "Table setting definitions must be mappings."
        )

        block_identifier = data.pop("block", None)
        if block_identifier is None:
            raise ValueError("Table setting definition requires a 'block'.")

        user_identifier = data.pop("user", None)
        if user_identifier is None:
            raise ValueError("Table setting definition requires a 'user'.")

        name = data.pop("name", None)
        if not name:
            raise ValueError("Table setting definition requires a 'name'.")

        fields = data.get("fields")
        if fields is not None:
            data["fields"] = _normalise_fields(fields)

        block = _resolve_block(block_identifier)
        user = _resolve_user(user_identifier)

        config, _ = BlockColumnConfig.objects.update_or_create(
            block=block,
            user=user,
            name=name,
            defaults=data,
        )
        configs.append(config)

    return configs


def _validate_mapping(payload: Mapping[str, Any] | Any, error_message: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError(error_message)
    return dict(payload)


def _normalise_fields(fields: Any) -> list[str]:
    if not fields:
        return []
    if isinstance(fields, Iterable) and not isinstance(fields, (str, bytes)):
        return [str(field) for field in fields]
    raise ValueError("'fields' must be an iterable of field names.")


def _resolve_block(identifier: Any) -> Block:
    if isinstance(identifier, Block):
        return identifier

    lookup: dict[str, Any]
    if isinstance(identifier, int):
        lookup = {"pk": identifier}
    else:
        lookup = {"code": identifier}

    try:
        return Block.objects.get(**lookup)
    except Block.DoesNotExist as exc:  # pragma: no cover - simple guard
        raise ValueError(f"Block '{identifier}' does not exist.") from exc


def _resolve_user(identifier: Any):
    if isinstance(identifier, UserModel):
        return identifier

    lookup: dict[str, Any]
    if isinstance(identifier, int):
        lookup = {"pk": identifier}
    else:
        lookup = {UserModel.USERNAME_FIELD: identifier}

    try:
        return UserModel.objects.get(**lookup)
    except UserModel.DoesNotExist as exc:  # pragma: no cover - simple guard
        raise ValueError(f"User '{identifier}' does not exist.") from exc


__all__ = [
    "create_or_update_blocks",
    "create_or_update_block_column_configs",
]

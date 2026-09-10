from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class Actor:
    id: str
    roles: frozenset[str]


def get_actor(
    settings: Annotated[Settings, Depends(get_settings)],
    actor_id: Annotated[str | None, Header(alias="X-Actor-ID")] = None,
    actor_roles: Annotated[str | None, Header(alias="X-Actor-Roles")] = None,
) -> Actor:
    if settings.environment != "development":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator authentication is not configured",
        )
    if not actor_id or not actor_roles:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Development actor headers are required",
        )
    return Actor(
        id=actor_id,
        roles=frozenset(role.strip() for role in actor_roles.split(",") if role.strip()),
    )


def require_operator(actor: Annotated[Actor, Depends(get_actor)]) -> Actor:
    if "operator" not in actor.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )
    return actor

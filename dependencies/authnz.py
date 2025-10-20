from dependencies.authn import authenticated_user
from fastapi import Depends, HTTPException, status
from typing import Annotated, Any


def has_roles(*allowed_roles: str):
    """
    Dependency that restricts access based on user roles.

    Example:
        @router.post("/admin", dependencies=[Depends(has_roles("admin"))])
    """
    def check_roles(user: Annotated[Any, Depends(authenticated_user)]):
        user_role = user.get("role")

        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Allowed roles: {', '.join(allowed_roles)}",
            )

        return user  # ✅ return the user for downstream use if needed

    return check_roles

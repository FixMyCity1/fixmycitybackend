import os
from typing import Annotated, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from db import users_collection
from bson.objectid import ObjectId


security = HTTPBearer()


def is_authenticated(
    authorization: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> Dict[str, Any]:
    """
    Validates JWT and returns the decoded payload.
    """
    jwt_secret = os.getenv("JWT_SECRET_KEY")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")

    if not jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT secret key not configured",
        )

    try:
        payload = jwt.decode(
            jwt=authorization.credentials,
            key=jwt_secret,
            algorithms=[jwt_algorithm],
        )
        # ✅ Expect both 'id' and 'role' to exist in payload
        if "id" not in payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user ID missing",
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def authenticated_user(
    payload: Annotated[Dict[str, Any], Depends(is_authenticated)]
) -> Dict[str, Any]:
    """
    Retrieves the authenticated user's record from the database.
    Returns a dict with id, email, role, and username.
    """
    user_id = payload["id"]

    if not ObjectId.is_valid(user_id):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID in token",
        )

    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user not found in database",
        )

    # Convert ObjectId to string for frontend compatibility
    user["id"] = str(user["_id"])
    del user["_id"]

    # Merge role from DB with JWT (in case of DB role change)
    user["role"] = user.get("role", payload.get("role", "user"))

    return user

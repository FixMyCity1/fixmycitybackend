from fastapi import APIRouter, Form, HTTPException, status
from typing import Annotated
from pydantic import EmailStr
from db import users_collection
import bcrypt
import jwt
import os
from enum import Enum
from datetime import timezone, timedelta, datetime


# --- Define Public User Roles ---
class UserRole(str, Enum):
    AUTHORITIES = "authorities"
    USER = "user"


# --- Create Users Router ---
users_router = APIRouter()


# --- REGISTER USER ENDPOINT ---
@users_router.post("/users/register", tags=["Users"])
def register_user(
    username: Annotated[str, Form()],
    email: Annotated[EmailStr, Form()],
    password: Annotated[str, Form(min_length=8)],
    role: Annotated[UserRole, Form()] = UserRole.USER,  # only 'user' or 'authorities'
):
    """
    Registers a new user (only 'user' or 'authorities').
    Admin accounts cannot be created or used.
    """

    # Check if user already exists
    if users_collection.count_documents({"email": email}) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists",
        )

    # Hash password
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Insert user into DB
    users_collection.insert_one(
        {
            "username": username,
            "email": email,
            "password": hashed_password,
            "role": role.value,  # either 'user' or 'authorities'
            "created_at": datetime.now(tz=timezone.utc),
        }
    )

    return {"message": f"{role.value.capitalize()} registered successfully"}


# --- LOGIN USER ENDPOINT ---
@users_router.post("/users/login", tags=["Users"])
def login_user(
    email: EmailStr = Form(...),
    password: str = Form(...),
):
    user = users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    # Ensure user has a valid role ('user' or 'authorities')
    if user["role"] not in [UserRole.USER.value, UserRole.AUTHORITIES.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: only 'user' or 'authorities' accounts are allowed"
        )

    # Verify password
    if not bcrypt.checkpw(password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    jwt_secret = os.getenv("JWT_SECRET_KEY", "secret123")
    token_expiry = datetime.now(tz=timezone.utc) + timedelta(days=60)

    token = jwt.encode(
        {"id": str(user["_id"]), "role": user["role"], "exp": token_expiry},
        jwt_secret,
        algorithm="HS256",
    )

    return {
        "message": f"{user['role'].capitalize()} logged in successfully",
        "access_token": token,
        "role": user["role"],
    }

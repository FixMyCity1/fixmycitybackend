from fastapi import Form, File, UploadFile, APIRouter, status,HTTPException, Depends
from db import issues_collection
from bson.objectid import ObjectId
from utils import replace_mongo_id
from typing import Annotated
import cloudinary
import cloudinary.uploader
from dependencies.authn import is_authenticated
from dependencies.authnz import has_roles


# --- Create Issues Router ---
issues_router = APIRouter()


# --- Get All Issues ---
@issues_router.get("/issues")
def get_issues(title: str = "", description: str = "", limit: int = 10, skip: int = 0):
    """
    Retrieve all issues with optional search filters.
    """
    issues = issues_collection.find(
        {
            "$or": [
                {"title": {"$regex": title, "$options": "i"}},
                {"description": {"$regex": description, "$options": "i"}},
            ]
        }
    ).skip(int(skip)).limit(int(limit))

    return {"data": [replace_mongo_id(issue) for issue in issues]}


# --- Report Issue (USER can create) ---
@issues_router.post(
    "/issues",
    dependencies=[Depends(has_roles("user"))],
)
def post_issue(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    flyer: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(is_authenticated)],
):
    """
    Allows users to report new issues.
    """
    # Check if same user already created issue with same title
    issues_count = issues_collection.count_documents(
        {"title": title, "owner": user_id}
    )
    if issues_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issue with title '{title}' already exists for this user."
        )

    # Upload flyer to Cloudinary
    upload_result = cloudinary.uploader.upload(flyer.file)

    # Save issue to DB
    issues_collection.insert_one(
        {
            "title": title,
            "description": description,
            "flyer": upload_result["secure_url"],
            "owner": user_id,
        }
    )

    return {"message": "Issue reported successfully"}


# --- Get Issue by ID (Public) ---
@issues_router.get("/issues/{issue_id}")
def get_issue_by_id(issue_id: str):
    """
    Retrieve a single issue by ID.
    """
    if not ObjectId.is_valid(issue_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid issue ID")

    issue = issues_collection.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")

    return {"data": replace_mongo_id(issue)}


# --- Update Issue (AUTHORITIES only) ---
@issues_router.put(
    "/issues/{issue_id}",
    dependencies=[Depends(has_roles("authorities"))],
)
def update_issue(
    issue_id: str,
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    flyer: Annotated[UploadFile, File()] = None,
):
    """
    Allows authorities to edit/update issues.
    """
    if not ObjectId.is_valid(issue_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid issue ID")

    update_data = {"title": title, "description": description}

    # If new flyer is provided, upload it to Cloudinary
    if flyer:
        upload_result = cloudinary.uploader.upload(flyer.file)
        update_data["flyer"] = upload_result["secure_url"]

    result = issues_collection.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": update_data}
    )

    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")

    return {"message": "Issue updated successfully"}

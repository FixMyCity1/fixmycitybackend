from fastapi import Form, File, UploadFile, APIRouter, status, HTTPException, Depends
from db import issues_collection
from bson.objectid import ObjectId
from utils import replace_mongo_id
from typing import Annotated, Optional
import cloudinary
import cloudinary.uploader
from dependencies.authn import is_authenticated
from dependencies.authnz import has_roles


# --- Create Issues Router ---
issues_router = APIRouter()


# --- Get All Issues ---
# --- Get All Issues ---
@issues_router.get("/issues")
def get_issues(
    title: str = "",
    description: str = "",
    region: str = "",
    category: str = "",
    status: str = "",   
    limit: int = 10,
    skip: int = 0,
):
    """
    Retrieve all issues with optional search filters, including status.
    """
    # --- Base query ---
    query = {"$and": []}

    # Add text-based filters (regex for partial matches)
    if title or description or region or category:
        query["$and"].append({
            "$or": [
                {"title": {"$regex": title, "$options": "i"}},
                {"description": {"$regex": description, "$options": "i"}},
                {"region": {"$regex": region, "$options": "i"}},
                {"category": {"$regex": category, "$options": "i"}},
            ]
        })

    # Add status filter if provided (exact match)
    if status:
        query["$and"].append({"status": status})

    # If no filters at all, default to empty query
    if not query["$and"]:
        query = {}

    # Fetch issues with pagination
    issues = issues_collection.find(query).skip(int(skip)).limit(int(limit))

    return {"data": [replace_mongo_id(issue) for issue in issues]}

#user can only view his changes
@issues_router.get(
    "/my-issues",
    dependencies=[Depends(has_roles("user"))],
)
def get_my_issues(user_id: Annotated[str, Depends(is_authenticated)]):
    """
    Retrieve all issues created by the currently authenticated user.
    """
    # Fetch all issues where owner == current user
    issues = issues_collection.find({"owner": user_id})

    user_issues = [replace_mongo_id(issue) for issue in issues]

    if not user_issues:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="You have not reported any issues yet."
        )

    return {"data": user_issues}


@issues_router.post(
    "/issues",
    dependencies=[Depends(has_roles("user"))],
)
def post_issue(
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    region: Annotated[str, Form()],
    gps_location: Annotated[str, Form()],
    flyer: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(is_authenticated)],
    category: Annotated[str, Form()],
):
    """
    Allows users to report new issues with region and a single GPS location field.
    """
    existing_issue = issues_collection.count_documents({"title": title, "owner": user_id})
    if existing_issue > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Issue with title '{title}' already exists for this user."
        )

    upload_result = cloudinary.uploader.upload(flyer.file)

    issues_collection.insert_one(
        {
            "title": title,
            "description": description,
            "region": region,
            "gps_location": gps_location,
            "flyer": upload_result["secure_url"],
            "owner": user_id,
            "category": category,
            "status": "pending",  # 👈 new field
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
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid issue ID"
        )

    issue = issues_collection.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )

    return {"data": replace_mongo_id(issue)}


@issues_router.put(
    "/issues/{issue_id}",
    dependencies=[Depends(has_roles("authorities"))],
)
def update_issue_status(
    issue_id: str,
    status_value: Annotated[str, Form(...)],
):
    """
    Allows authorities to update ONLY the status of an issue.
    """
    # --- Validate issue ID ---
    if not ObjectId.is_valid(issue_id):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid issue ID"
        )

    # --- Validate status options ---
    valid_statuses = ["pending", "in-progress", "completed", "rejected"]
    if status_value not in valid_statuses:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Allowed values: {valid_statuses}"
        )

    # --- Check if the issue exists ---
    issue = issues_collection.find_one({"_id": ObjectId(issue_id)})
    if not issue:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )

    # --- Update status only ---
    result = issues_collection.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": {"status": status_value}}
    )

    if result.modified_count == 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No changes made to the issue"
        )

    return {
        "message": f"Issue updated successfully — status set to '{status_value}'",
        "updated_data": {"status": status_value}
    }


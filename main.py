from fastapi import FastAPI
import os
import cloudinary
from routes.issues import issues_router
from routes.users import users_router
from dotenv import load_dotenv


load_dotenv()

# configure cloudinary
cloudinary.config(
    cloud_name = os.getenv("CLOUD_NAME"),
    api_key = os.getenv("API_KEY"),
    api_secret = os.getenv("API_SECRET"),
)



app = FastAPI()


@app.get("/")
def get_home():
    return {"message": "You are on home page"}

# include routes

app.include_router(issues_router)
app.include_router(users_router)

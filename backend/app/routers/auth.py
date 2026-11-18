"""POST /auth/login and POST /auth/logout (contract endpoints).

Prototype behaviour (semester 1, see app/auth.py): `email` also accepts the usernames
1-4, and the password is not checked.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth
from app.routers.me import StudentOut, load_profile

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320, description="An email, or 1-4 for the prototype users")
    password: str = Field(default="", max_length=200, description="Not checked in the prototype")


@router.post("/login", response_model=StudentOut)
def login(body: LoginRequest, response: Response):
    student_id = auth.find_student_id(auth.login_email(body.email))
    if student_id is None:
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})
    token = auth.create_session(student_id)
    response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", path="/")
    return load_profile(student_id)


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    auth.end_session(request.cookies.get(auth.SESSION_COOKIE))
    response = Response(status_code=204)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response

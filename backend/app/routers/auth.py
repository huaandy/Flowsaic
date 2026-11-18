"""POST /auth/login and POST /auth/logout (contract endpoints).

Prototype behaviour (semester 1, see app/auth.py): `email` also accepts the usernames
1-5, and the password is not checked. User 5 (New Student) is emptied when they sign in
and when they sign out, so they are a first-time student every time.
"""

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app import auth, demo_seed
from app.routers.me import StudentOut, load_profile

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=320, description="An email, or 1-5 for the prototype users")
    password: str = Field(default="", max_length=200, description="Not checked in the prototype")


@router.post("/login", response_model=StudentOut)
def login(body: LoginRequest, response: Response):
    email = auth.login_email(body.email)
    student_id = auth.find_student_id(email)
    if student_id is None:
        return JSONResponse(status_code=401, content={"error": "invalid_credentials"})
    if email == demo_seed.NEW_STUDENT_EMAIL:
        demo_seed.clear_new_student(only_if=student_id)
    token = auth.create_session(student_id)
    response.set_cookie(auth.SESSION_COOKIE, token, httponly=True, samesite="lax", path="/")
    return load_profile(student_id)


@router.post("/logout", status_code=204)
def logout(request: Request) -> Response:
    student_id = auth.end_session(request.cookies.get(auth.SESSION_COOKIE))
    if student_id is not None:
        demo_seed.clear_new_student(only_if=student_id)  # only empties user 5
    response = Response(status_code=204)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response

from http import HTTPStatus

from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError
from django.http.request import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.auth import JWTAccessAuth
from apps.accounts.schemas import (
    LoginIn,
    LogoutIn,
    RefreshIn,
    SignupIn,
    TokenOut,
    UserOut,
)
from apps.accounts.tokens import (
    create_token_pair,
    decode_token,
    revoke_refresh_token,
    rotate_token_pair,
)

User = get_user_model()

router = Router(tags=["Authentication"])
jwt_access_auth = JWTAccessAuth()


@router.post("/signup", response={HTTPStatus.CREATED: UserOut}, auth=None)
def signup(request: HttpRequest, data: SignupIn):
    try:
        user = User.objects.create_user(
            email=data.email,
            password=data.password,
        )
    except IntegrityError as exc:
        raise HttpError(HTTPStatus.CONFLICT, "이미 사용 중인 이메일입니다.") from exc

    return HTTPStatus.CREATED, user


@router.post("/login", response=TokenOut, auth=None)
def login(request: HttpRequest, data: LoginIn):
    authenticated_user = authenticate(request, email=data.email, password=data.password)

    if authenticated_user is None:
        raise HttpError(
            HTTPStatus.CONFLICT, "이메일 또는 비밀번호가 올바르지 않습니다."
        )

    return create_token_pair(authenticated_user)


@router.post("/refresh", response=TokenOut, auth=None)
def refresh(request: HttpRequest, data: RefreshIn):
    claims = decode_token(data.refresh, "refresh")

    if claims is None:
        raise HttpError(
            HTTPStatus.UNAUTHORIZED, "유효하지 않거나 만료된 Refresh Token입니다."
        )

    user_id = int(claims["sub"])
    user = User.objects.filter(pk=user_id, is_active=True).first()

    if user is None:
        raise HttpError(
            HTTPStatus.UNAUTHORIZED, "사용자를 찾을 수 없거나 비활성화된 계정입니다."
        )

    token_pair = rotate_token_pair(user, claims["jti"])

    if token_pair is None:
        raise HttpError(
            HTTPStatus.UNAUTHORIZED, "이미 사용되었거나 폐기된 Refresh Token입니다."
        )

    return token_pair


@router.post("/logout", auth=None)
def logout(request: HttpRequest, data: LogoutIn):
    claims = decode_token(data.refresh, "refresh")

    if claims is not None:
        user_id = int(claims["sub"])
        revoke_refresh_token(
            user_id=user_id,
            jti=claims["jti"],
        )

    return {"detail": "로그아웃되었습니다."}


@router.get("/me", response=UserOut, auth=jwt_access_auth)
def me(request: HttpRequest):
    return request.auth

import secrets
from datetime import timedelta, datetime
from typing import Literal, TypedDict

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RefreshSession

User = get_user_model()

TokenType = Literal["access", "refresh"]
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=2)


class TokenClaims(TypedDict):
    sub: str
    type: TokenType
    jti: str
    iat: int
    exp: int


class TokenPair(TypedDict):
    access: str
    refresh: str


def _create_jti() -> str:
    return secrets.token_hex(16)


def _encode_token(
    user: User,
    token_type: TokenType,
    lifetime: timedelta,
) -> tuple[str, str, int]:
    now = timezone.now()
    expires_at = now + lifetime
    jti = _create_jti()

    payload: TokenClaims = {
        "sub": str(user.pk),
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token, jti, int(expires_at.timestamp())


def _create_access_token(user: User) -> str:
    token, _, _ = _encode_token(user, "access", ACCESS_TOKEN_TTL)
    return token


def _create_refresh_token(user: User) -> tuple[str, str, datetime]:
    token, jti, expires_timestamp = _encode_token(user, "refresh", REFRESH_TOKEN_TTL)
    expires_at = datetime.fromtimestamp(
        expires_timestamp,
        tz=timezone.get_current_timezone(),
    )
    return token, jti, expires_at


def decode_token(token: str, expected_type: TokenType) -> TokenClaims | None:
    """서명, 만료 시간, 필수 Claim, 토큰 종류를 검증한다."""
    try:
        decoded: dict[str, object] = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=["HS256"],
            options={
                "require": ["sub", "type", "jti", "iat", "exp"],
            },
        )
    except jwt.InvalidTokenError:
        return None

    sub: str | object = decoded.get("sub")
    token_type: object = decoded.get("type")
    jti: object = decoded.get("jti")
    issued_at: object = decoded.get("iat")
    expires_at: object = decoded.get("exp")

    if not isinstance(sub, str) or not sub.isdigit():
        return None
    if token_type != expected_type:
        return None
    if not isinstance(jti, str) or len(jti) != 32:
        return None
    if type(issued_at) is not int or type(expires_at) is not int:
        return None
    if expires_at <= issued_at:
        return None

    return TokenClaims(**decoded)


@transaction.atomic
def create_token_pair(user: User) -> TokenPair:
    """로그인 시 토큰 쌍을 발급하고 Refresh Session을 저장한다."""
    access_token = _create_access_token(user)
    refresh_token, refresh_jti, refresh_expires_at = _create_refresh_token(user)

    RefreshSession.objects.create(
        user=user,
        jti=refresh_jti,
        expires_at=refresh_expires_at,
    )

    return TokenPair(access=access_token, refresh=refresh_token)


@transaction.atomic
def rotate_token_pair(user: User, old_jti: str) -> TokenPair | None:
    """이전 Refresh Token을 한 번만 소비하고 새 토큰 쌍을 발급한다."""
    now = timezone.now()

    session = (
        RefreshSession.objects.select_for_update()
        .filter(
            user=user,
            jti=old_jti,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
        .first()
    )

    if session is None:
        return None

    # 이 행의 잠금을 획득한 요청만 기존 토큰을 소비할 수 있다.
    session.revoked_at = now
    session.save(update_fields=["revoked_at"])

    access_token = _create_access_token(user)
    refresh_token, new_jti, new_expires_at = _create_refresh_token(user)

    RefreshSession.objects.create(
        user=user,
        jti=new_jti,
        expires_at=new_expires_at,
    )

    return TokenPair(access=access_token, refresh=refresh_token)


def revoke_refresh_token(user_id: int, jti: str) -> bool:
    """Refresh Token을 폐기한다. 이미 폐기된 경우에도 안전하게 처리된다."""
    updated_count = RefreshSession.objects.filter(
        user_id=user_id,
        jti=jti,
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())

    return updated_count == 1

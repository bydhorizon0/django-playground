from django.contrib.auth import get_user_model
from django.http import HttpRequest
from ninja.security import HttpBearer

from apps.accounts.tokens import TokenClaims, decode_token

User = get_user_model()


# HttpBearer는 Authorization: Bearer <token> 헤더를 처리한다.
# 인증에 성공하면 반환한 User 객체가 request.auth에 들어간다.
class JWTAccessAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str) -> User | None:
        claims: TokenClaims | None = decode_token(token, "access")

        if claims is None:
            return None

        try:
            user_id = int(claims["sub"])
        except (TypeError, ValueError):
            return None

        return User.objects.filter(
            pk=user_id,
            is_active=True,
        ).first()

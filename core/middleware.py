# core/middleware.py
import jwt
from django.conf import settings
from django.http import JsonResponse


PROTECTED_PATH_PREFIXES = ("/api/",)


class WordPressJWTMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # Only protect API routes
        if request.path.startswith(PROTECTED_PATH_PREFIXES):

            token = self._extract_token(request)

            if not token:
                return JsonResponse(
                    {"detail": "Authentication credentials were not provided."},
                    status=401
                )

            try:
                payload = jwt.decode(
                    token,
                    settings.WP_JWT_SECRET,
                    algorithms=["HS256"]
                )
            except jwt.ExpiredSignatureError:
                return JsonResponse(
                    {"detail": "Token has expired."},
                    status=401
                )
            except jwt.InvalidTokenError:
                return JsonResponse(
                    {"detail": "Invalid authentication token."},
                    status=403
                )

            tenant_id = payload.get("tenant_id")

            if not tenant_id:
                return JsonResponse(
                    {"detail": "Invalid token payload."},
                    status=403
                )

            # 🔐 SINGLE SOURCE OF TRUTH
            request.tenant_id = tenant_id
            request.wp_user = payload

        return self.get_response(request)

    def _extract_token(self, request):
        """
        Priority:
        1. Authorization: Bearer <token>
        2. ?token=<token> (WordPress redirect)
        """

        auth_header = request.headers.get("Authorization", "")

        if auth_header.startswith("Bearer "):
            return auth_header.replace("Bearer ", "").strip()

        return request.GET.get("token")

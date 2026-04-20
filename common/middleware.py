from __future__ import annotations


class StaticMediaCacheControlMiddleware:
    """
    Adds long-lived caching headers for static/media payloads when missing.
    """

    LONG_CACHE = "public, max-age=31536000, immutable"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path or ""
        if "Cache-Control" in response:
            return response
        if path.startswith("/static/") or path.startswith("/media/"):
            response["Cache-Control"] = self.LONG_CACHE
        return response


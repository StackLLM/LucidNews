"""Accounts for the web app: e-mail and password, or Google (OAuth 2.0 authorization code + PKCE).

Optional: ``auth.enabled`` in ``config.json``. Off, the API behaves as before. On, every
``/api/*`` route except ``/api/auth/*`` needs a session cookie. There is no e-mail
verification step (by design), which shapes how accounts are linked: see ``service.py``.
"""

from .service import AuthService, build_auth_service

__all__ = ["AuthService", "build_auth_service"]

from starlette.types import ASGIApp, Receive, Scope, Send


class OmitRefererMiddleware:
    """Drop unused navigation metadata before guard's SSRF detection.

    guard-core 4.4 scans Referer URLs as potential fetch targets, rejecting
    normal localhost/private-network browsers. This API never fetches or
    authorizes against Referer; CSRF validates Origin and a signed token.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            scope = {
                **scope,
                "headers": [
                    (name, value)
                    for name, value in scope["headers"]
                    if name.lower() != b"referer"
                ],
            }
        await self.app(scope, receive, send)

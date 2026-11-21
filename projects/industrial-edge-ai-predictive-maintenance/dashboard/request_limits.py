"""Bound actual request bytes before JSON parsing, including chunked requests."""
import re

from starlette.responses import JSONResponse

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
        "base-uri 'none'; form-action 'self'"),
}


class RequestBodyLimit:
    def __init__(self, app, max_bytes=8192):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['method'] not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return await self.app(scope, receive, send)

        async def reject(status, detail):
            await JSONResponse({'detail': detail}, status_code=status,
                               headers=SECURITY_HEADERS)(scope, receive, send)

        lengths = [v for k, v in scope.get('headers', []) if k.lower() == b'content-length']
        if lengths and (len(lengths) != 1 or len(lengths[0]) > 16
                        or not re.fullmatch(rb'[0-9]+', lengths[0])):
            return await reject(400, 'Invalid Content-Length')
        if lengths and int(lengths[0]) > self.max_bytes:
            return await reject(413, 'Request too large')
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            chunk = message.get('body', b'')
            if len(body) + len(chunk) > self.max_bytes:
                return await reject(413, 'Request too large')
            body.extend(chunk)
            if not message.get('more_body', False):
                break
        replayed = False

        async def bounded_receive():
            nonlocal replayed
            if not replayed:
                replayed = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()

        await self.app(scope, bounded_receive, send)

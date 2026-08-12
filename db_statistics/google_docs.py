import base64
import json
import time
from datetime import UTC, datetime
from urllib import parse, request

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_DOCS_API_URL = "https://docs.googleapis.com/v1/documents"
GOOGLE_DOCS_SCOPE = "https://www.googleapis.com/auth/documents"


def _base64url(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _service_account_token(service_account):
    now = int(time.time())
    header = _base64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    claims = _base64url(json.dumps({"iss": service_account["client_email"], "scope": GOOGLE_DOCS_SCOPE, "aud": service_account.get("token_uri", GOOGLE_OAUTH_TOKEN_URL), "iat": now, "exp": now + 3600}, separators=(",", ":")).encode())
    signing_input = f"{header}.{claims}".encode("ascii")
    private_key = serialization.load_pem_private_key(service_account["private_key"].encode(), password=None)
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{header}.{claims}.{_base64url(signature)}"
    body = parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}).encode()
    token_request = request.Request(service_account.get("token_uri", GOOGLE_OAUTH_TOKEN_URL), data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with request.urlopen(token_request, timeout=settings.GOOGLE_DOCS_TIMEOUT_SECONDS) as response:
        return json.load(response)["access_token"]


def _authorized_json(url, token, *, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Authorization": f"Bearer {token}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    api_request = request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    with request.urlopen(api_request, timeout=settings.GOOGLE_DOCS_TIMEOUT_SECONDS) as response:
        return json.load(response)


def _connection_text(connection, db_user):
    fields = [
        ("Дата", datetime.now(UTC).isoformat(timespec="seconds")),
        ("Название", connection.name),
        ("Тип БД", connection.db_type),
        ("Хост", connection.host),
        ("Порт", connection.port),
        ("База данных", connection.database),
        ("Пользователь БД", connection.username),
        ("Сохранил", db_user.login if db_user else "Неизвестный пользователь"),
    ]
    return "\nНовое подключение\n" + "\n".join(f"{label}: {value}" for label, value in fields) + "\n"


def export_connection_to_google_doc(connection, db_user=None):
    """Добавляет параметры подключения в Google Doc, не экспортируя секреты."""
    if not settings.GOOGLE_DOCS_EXPORT_ENABLED:
        return False

    with open(settings.GOOGLE_SERVICE_ACCOUNT_FILE, encoding="utf-8") as credentials_file:
        service_account = json.load(credentials_file)
    token = _service_account_token(service_account)
    document_url = f"{GOOGLE_DOCS_API_URL}/{settings.GOOGLE_DOCS_DOCUMENT_ID}"
    document = _authorized_json(document_url, token)
    content = document.get("body", {}).get("content", [])
    end_index = max((item.get("endIndex", 1) for item in content), default=1)
    payload = {"requests": [{"insertText": {"location": {"index": max(1, end_index - 1)}, "text": _connection_text(connection, db_user)}}]}
    _authorized_json(f"{document_url}:batchUpdate", token, payload=payload)
    return True

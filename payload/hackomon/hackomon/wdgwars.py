"""Original client for the public WDGWars multipart discovery API."""

import json
from email.utils import parsedate_to_datetime
import re
import time
import urllib.error
import urllib.request
import uuid

from .exploration import export_csv
from . import __version__


ENDPOINT = "https://wdgwars.pl/api/upload-csv"
ACCOUNT_ENDPOINT = "https://wdgwars.pl/api/me"


class UploadError(RuntimeError):
    def __init__(self, message, kind="rejected", retry_after=0, job_id=""):
        super().__init__(message)
        self.kind = kind
        self.retry_after = retry_after
        self.job_id = job_id


def validate_key(api_key):
    if not isinstance(api_key, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", api_key):
        raise UploadError("Defina a chave WDGWars no config.json local", "credentials")


def _retry_seconds(headers):
    value = str(headers.get("Retry-After", "60")) if headers else "60"
    try:
        return max(1, min(604800, int(value)))
    except ValueError:
        try:
            return max(1, min(604800, int(parsedate_to_datetime(value).timestamp() - time.time())))
        except (ValueError, TypeError, OverflowError):
            return 60


def _request(request, opener=None):
    client = opener or urllib.request.build_opener(NoRedirect())
    try:
        with client.open(request, timeout=15) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("response too large")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("unknown response")
            if response.status == 202:
                job = str(result.get("job_id", ""))
                job = job[:128] if re.fullmatch(r"[A-Za-z0-9_-]*", job) else ""
                raise UploadError("Servidor enfileirou o lote; importacao nao confirmada", "pending_remote", job_id=job)
            if response.status != 200:
                raise ValueError("unconfirmed status")
            return result
    except urllib.error.HTTPError as error:
        if error.code == 429:
            delay = _retry_seconds(error.headers)
            raise UploadError("Limite do WDGWars; aguarde %ds" % delay, "rate_limited", delay) from None
        if error.code in (401, 403):
            raise UploadError("Chave WDGWars invalida ou sem permissao", "credentials") from None
        kind = "uncertain" if error.code >= 500 else "rejected"
        raise UploadError("WDGWars HTTP %d; dados preservados" % error.code, kind) from None
    except (OSError, ValueError):
        raise UploadError("Sem confirmacao do servidor; dados preservados", "uncertain") from None


def account(api_key, opener=None):
    validate_key(api_key)
    request = urllib.request.Request(ACCOUNT_ENDPOINT, method="GET", headers={
        "X-API-Key": api_key, "User-Agent": "Hackomon/" + __version__,
    })
    result = _request(request, opener)
    if result.get("ok") is not True or not isinstance(result.get("username"), str):
        raise UploadError("Conta nao confirmada pelo WDGWars", "credentials")
    username = "".join(char for char in result["username"] if char.isprintable())[:64]
    if not username:
        raise UploadError("Conta sem identificacao valida", "credentials")
    clean = {"username": username}
    for key in ("wifi", "ble", "total"):
        value = result.get(key)
        if type(value) is int and value >= 0:
            clean[key] = value
    return clean


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect must never forward the account key to another host.
        return None


def upload_payload(data, api_key, opener=None):
    validate_key(api_key)
    if len(data) > 1024 * 1024:
        raise RuntimeError("Lote excede 1 MB")
    boundary = "hackomon" + uuid.uuid4().hex
    body = ('--%s\r\nContent-Disposition: form-data; name="file"; '
            'filename="hackomon.csv"\r\nContent-Type: text/csv\r\n\r\n' % boundary).encode()
    body += data + ("\r\n--%s--\r\n" % boundary).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "X-API-Key": api_key, "User-Agent": "Hackomon/" + __version__,
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    })
    result = _request(request, opener)
    counters = {key: result[key] for key in ("imported", "captured", "merged_samples", "no_gps", "bad_rows")
                if type(result.get(key)) is int and result[key] >= 0}
    explicit_error = result.get("ok") is False or result.get("success") is False or bool(result.get("error"))
    accepted = result.get("ok") is True or result.get("success") is True or any(
        key in counters for key in ("imported", "captured", "merged_samples"))
    if explicit_error:
        raise UploadError("Servidor recusou o lote; dados preservados", "rejected")
    if not accepted:
        raise UploadError("Resposta desconhecida; recebimento nao confirmado", "uncertain")
    return counters


def upload(observations, api_key, opener=None):
    if not observations:
        raise RuntimeError("Fila vazia")
    upload_payload(export_csv(observations), api_key, opener)
    return len(observations)

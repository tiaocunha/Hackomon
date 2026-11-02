"""Original client for the public WDGWars multipart discovery API."""

import json
import re
import urllib.error
import urllib.request
import uuid

from .exploration import export_csv


ENDPOINT = "https://wdgwars.pl/api/upload-csv"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A redirect must never forward the account key to another host.
        return None


def upload(observations, api_key, opener=None):
    if not re.fullmatch(r"[0-9a-fA-F]{64}", api_key):
        raise RuntimeError("Defina a chave WDGWars no config.json local")
    if not observations:
        raise RuntimeError("Fila vazia")
    data = export_csv(observations)
    if len(data) > 1024 * 1024:
        raise RuntimeError("Lote excede 1 MB")
    boundary = "hackomon" + uuid.uuid4().hex
    body = ('--%s\r\nContent-Disposition: form-data; name="file"; '
            'filename="hackomon.csv"\r\nContent-Type: text/csv\r\n\r\n' % boundary).encode()
    body += data + ("\r\n--%s--\r\n" % boundary).encode()
    request = urllib.request.Request(ENDPOINT, data=body, method="POST", headers={
        "X-API-Key": api_key, "User-Agent": "Hackomon/0.4.0",
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    })
    client = opener or urllib.request.build_opener(NoRedirect())
    try:
        with client.open(request, timeout=15) as response:
            raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError("response too large")
            result = json.loads(raw)
            if response.status != 200 or not isinstance(result, dict):
                raise ValueError("unconfirmed response")
            if result.get("ok") is not True and result.get("success") is not True:
                raise ValueError("unconfirmed import")
    except urllib.error.HTTPError as error:
        raise RuntimeError("WDGWars HTTP %d; fila preservada" % error.code) from None
    except (OSError, ValueError):
        raise RuntimeError("Envio sem confirmacao; fila preservada") from None
    return len(observations)

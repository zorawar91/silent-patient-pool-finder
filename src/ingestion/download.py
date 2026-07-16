from __future__ import annotations
"""
Shared HTTP download helper for all SPPF ingestion pipelines.

Every ingest script fetches public data files over HTTPS. This module gives
them one hardened entry point:

  - TLS certificate verification is ALWAYS on, using the certifi CA bundle
    (fixes macOS LibreSSL issues without disabling verification).
  - If a host's certificate genuinely cannot be verified, the insecure retry
    only happens when the operator explicitly opts in by setting
    SPPF_ALLOW_INSECURE_SSL=1 — and it logs loudly when it does.
"""

import logging
import os

import requests

log = logging.getLogger(__name__)


def _allow_insecure() -> bool:
    return os.environ.get("SPPF_ALLOW_INSECURE_SSL") == "1"


def _ca_bundle():
    try:
        import certifi
        return certifi.where()
    except ImportError:
        return True  # fall back to the system default bundle


def fetch(
    url: str,
    *,
    timeout: float = 60,
    stream: bool = False,
    headers: dict | None = None,
) -> requests.Response:
    """
    GET `url` with TLS verification (certifi CA bundle).

    On SSLError, retries once WITHOUT verification only if the
    SPPF_ALLOW_INSECURE_SSL=1 env var is set; otherwise the error propagates.
    """
    try:
        return requests.get(
            url, timeout=timeout, stream=stream, headers=headers,
            verify=_ca_bundle(),
        )
    except requests.exceptions.SSLError:
        if not _allow_insecure():
            log.error(
                "TLS verification failed for %s. If you trust this network and "
                "must proceed, set SPPF_ALLOW_INSECURE_SSL=1 (not recommended).",
                url,
            )
            raise
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log.warning(
            "TLS verification failed for %s — retrying WITHOUT verification "
            "because SPPF_ALLOW_INSECURE_SSL=1.", url,
        )
        return requests.get(
            url, timeout=timeout, stream=stream, headers=headers, verify=False,
        )

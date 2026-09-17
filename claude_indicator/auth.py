"""OAuth token access for the Claude usage endpoint.

Reads the token that Claude Code already stores on this machine and refreshes
it when expired, using the same public OAuth client Claude Code uses. The
refreshed tokens are written back to the credentials file atomically so that
Claude Code and this indicator always share the latest (rotated) token.

The token is never logged or printed.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

# Public OAuth client id used by Claude Code, and its token endpoint.
CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
# Cloudflare fronts the token endpoint and blocks unknown/library UAs; a
# standard browser UA reaches the real OAuth handler.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)

# Refresh a bit early so a request never races the expiry boundary.
EXPIRY_SKEW_MS = 60_000


class AuthError(Exception):
    """Raised when no usable token can be obtained."""


@dataclass
class Credentials:
    access_token: str
    refresh_token: str
    expires_at: int  # epoch milliseconds
    subscription_type: str | None = None


def _candidate_paths() -> list[str]:
    """Credential locations to consider, most-preferred first.

    CLAUDE_CONFIG_DIR (if set) then ~/.claude. A standalone exe launched from
    the Startup folder may not inherit CLAUDE_CONFIG_DIR, and the two files can
    differ (one may lack a refresh token), so we consider both.
    """
    paths: list[str] = []
    base = os.environ.get("CLAUDE_CONFIG_DIR")
    if base:
        paths.append(os.path.join(base, ".credentials.json"))
    paths.append(os.path.join(os.path.expanduser("~"), ".claude", ".credentials.json"))
    seen: set[str] = set()
    out: list[str] = []
    for p in paths:
        ap = os.path.abspath(p)
        if ap not in seen:
            seen.add(ap)
            out.append(p)
    return out


def credentials_path() -> str:
    """Pick the best credentials file: one with a refresh token and the latest
    expiry wins, so we never get stuck on a file whose refresh token is empty."""
    candidates = _candidate_paths()
    best: str | None = None
    best_score: tuple[int, int] | None = None
    for p in candidates:
        try:
            with open(p, "r", encoding="utf-8") as fh:
                oauth = json.load(fh).get("claudeAiOauth") or {}
        except (OSError, json.JSONDecodeError):
            continue
        if not oauth.get("accessToken"):
            continue
        score = (1 if oauth.get("refreshToken") else 0, int(oauth.get("expiresAt", 0)))
        if best_score is None or score > best_score:
            best_score = score
            best = p
    return best or candidates[0]


def _read_file(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError as exc:
        raise AuthError(
            f"Credentials not found at {path}. Sign in with Claude Code first."
        ) from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise AuthError(f"Could not read credentials: {exc}") from exc


def load_credentials(path: str | None = None) -> Credentials:
    path = path or credentials_path()
    data = _read_file(path)
    oauth = data.get("claudeAiOauth")
    if not oauth or "accessToken" not in oauth:
        raise AuthError("Credentials file has no claudeAiOauth token block.")
    return Credentials(
        access_token=oauth["accessToken"],
        refresh_token=oauth.get("refreshToken", ""),
        expires_at=int(oauth.get("expiresAt", 0)),
        subscription_type=oauth.get("subscriptionType"),
    )


def _is_expired(creds: Credentials) -> bool:
    now_ms = int(time.time() * 1000)
    return creds.expires_at <= now_ms + EXPIRY_SKEW_MS


def _persist(path: str, tokens: dict) -> None:
    """Write refreshed tokens back into the credentials file atomically.

    Preserves any other keys already in the file (e.g. mcpOAuth).
    """
    try:
        data = _read_file(path)
    except AuthError:
        data = {}
    oauth = data.get("claudeAiOauth", {})
    oauth["accessToken"] = tokens["access_token"]
    if tokens.get("refresh_token"):
        oauth["refreshToken"] = tokens["refresh_token"]
    oauth["expiresAt"] = tokens["expires_at"]
    data["claudeAiOauth"] = oauth

    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".cred", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _refresh(refresh_token: str) -> dict:
    if not refresh_token:
        raise AuthError("No refresh token available; re-authenticate in Claude Code.")
    payload = json.dumps(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CLIENT_ID,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            # A real User-Agent is required: the endpoint sits behind
            # Cloudflare, which blocks urllib's default UA (error 1010).
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise AuthError(f"Token refresh failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise AuthError(f"Token refresh network error: {exc.reason}") from exc

    access = body.get("access_token")
    if not access:
        raise AuthError("Refresh response missing access_token.")
    expires_in = int(body.get("expires_in", 0))
    return {
        "access_token": access,
        "refresh_token": body.get("refresh_token", ""),
        "expires_at": int(time.time() * 1000) + expires_in * 1000,
    }


def get_valid_token(path: str | None = None) -> str:
    """Return a currently-valid access token, refreshing + persisting if needed."""
    path = path or credentials_path()
    creds = load_credentials(path)
    if not _is_expired(creds):
        return creds.access_token
    tokens = _refresh(creds.refresh_token)
    _persist(path, tokens)
    return tokens["access_token"]


def force_refresh(path: str | None = None) -> str:
    """Refresh regardless of local expiry (used when a request returns 401)."""
    path = path or credentials_path()
    creds = load_credentials(path)
    tokens = _refresh(creds.refresh_token)
    _persist(path, tokens)
    return tokens["access_token"]

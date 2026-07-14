"""Netpulse-Client fuer die Studio-Auslastung (Live Capacity).

Per HTTPS-Mitschnitt der 7stark-App verifiziert (2026-07-14):
- Login: POST {brand-host}/np/exerciser/login, FORM-encoded username+password.
  Antwort-JSON hat homeClubUuid + chainUuid; Session per Set-Cookie (JSESSIONID).
  WICHTIG: brand-spezifischer Host (7stark.netpulse.com), sonst 401
  "StandardizedFlows not enabled for current brand".
- Capacity: GET /np/locations/v1.0/gym-chains/{chainUuid}/location-details ->
  Liste von Studios, jedes mit utilization:{gymLocationId,totalCapacity,usedCapacity}.
  Prozent wie in der App: round(usedCapacity / totalCapacity * 100).
- Header: X-NP-API-Version 1.5, X-NP-APP-Version, X-NP-User-Agent (applicationName=7stark).
"""
from __future__ import annotations

import json
import logging

import aiohttp

from .const import (
    NP_LOGIN, NP_LOCATION_DETAILS, NP_BRAND_DESC,
    NP_API_VERSION, NP_APP_VERSION, NP_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


def _headers_base() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "X-NP-API-Version": NP_API_VERSION,
        "X-NP-APP-Version": NP_APP_VERSION,
        "X-NP-User-Agent": NP_USER_AGENT,
    }


async def detect_host(session: aiohttp.ClientSession, alias: str | None) -> str | None:
    """Leitet den Brand-Host aus dem eGym-Studio-Alias ab und validiert ihn.

    Netpulse-Host = {chainAlias}.netpulse.com, und chainAlias == eGym-Studio-Alias
    (verifiziert fuer 7stark). Prueft per unauth GET /np/brand/description, dass der
    Host existiert und derselbe Alias zurueckkommt. None, wenn nicht ableitbar.
    """
    slug = "".join(c for c in (alias or "").lower() if c.isalnum())
    if not slug:
        return None
    host = f"{slug}.netpulse.com"
    try:
        async with session.get(f"https://{host}{NP_BRAND_DESC}",
                               headers=_headers_base()) as r:
            if r.status == 200 and (await r.json()).get("chainAlias"):
                return host
    except Exception as err:  # noqa: BLE001 – Netz/DNS: nicht ableitbar
        _LOGGER.debug("Netpulse-Host-Erkennung fuer %r fehlgeschlagen: %s", host, err)
    return None


class NetpulseCapacityClient:
    """Loggt sich bei Netpulse ein und liest die Auslastung des Heimstudios."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str,
                 host: str) -> None:
        self._s = session
        self._email = email
        self._password = password
        self._base = f"https://{host}"  # brand-spezifischer Netpulse-Host

    def _headers(self, cookie: str | None = None) -> dict[str, str]:
        h = _headers_base()
        if cookie:
            h["Cookie"] = cookie
        return h

    async def _login(self) -> tuple[str, str, str]:
        """Gibt (chainUuid, homeClubUuid, JSESSIONID-Cookie). Wirft bei !=200/Netzfehler."""
        # data=... -> FormBody (application/x-www-form-urlencoded), wie die App.
        async with self._s.post(
            self._base + NP_LOGIN,
            data={"username": self._email, "password": self._password},
            headers=self._headers(),
        ) as r:
            body = await r.text()
            if r.status != 200:
                # Body enthaelt "cause"/"message" (NoSuchUser, external service, locked, ...)
                raise NetpulseError(f"Login HTTP {r.status}: {body[:300]}", status=r.status)
            data = json.loads(body)
            cookie = None
            for raw in r.headers.getall("Set-Cookie", []):
                if raw.startswith("JSESSIONID="):
                    cookie = raw.split(";", 1)[0]  # "JSESSIONID=<wert>"
                    break
        chain, home = data.get("chainUuid"), data.get("homeClubUuid")
        if not chain or not home or not cookie:
            raise NetpulseError(
                f"Login ok, aber chainUuid/homeClubUuid/Session fehlt "
                f"(chain={chain!r}, home={home!r})")
        return chain, home, cookie

    async def get_capacity(self) -> dict | None:
        """{'percent','used','total'} oder None (Studio ohne Auslastungsdaten)."""
        chain, home, cookie = await self._login()
        async with self._s.get(self._base + NP_LOCATION_DETAILS % chain,
                               headers=self._headers(cookie)) as r:
            r.raise_for_status()
            locations = await r.json()

        util = _utilization_for(locations, home)
        if not util:
            return None
        used, total = util.get("usedCapacity"), util.get("totalCapacity")
        if used is None or not total:  # not total -> auch 0 abfangen (Div/0)
            return None
        return {"percent": round(used / total * 100), "used": used, "total": total}


def _utilization_for(locations, home_club_uuid) -> dict | None:
    """utilization-Objekt des Heimstudios aus location-details (Liste)."""
    if not isinstance(locations, list):
        return None
    match = None
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if loc.get("uuid") == home_club_uuid:
            return loc.get("utilization")
        if match is None and loc.get("utilization"):
            match = loc.get("utilization")  # Fallback: erstes Studio mit Daten
    return match


class NetpulseError(Exception):
    """Netpulse-Fehler. status gesetzt bei HTTP-Fehlern (401/403 = Auth abgelehnt)."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status

"""Netpulse-Client fuer die Studio-Auslastung (Live Capacity).

Aus dem APK (com.netpulse.mobile.sevenstark) per jadx verifiziert:
- Login: POST /np/exerciser/login, FORM-encoded username+password (kein JSON!).
  Antwort-JSON enthaelt homeClubUuid; Session kommt per Set-Cookie (JSESSIONID).
- Capacity: GET /np/companies/{homeClubUuid} -> Company mit
  capacity:{totalCapacity, usedCapacity}. Prozent wie in der App:
  round(usedCapacity / totalCapacity * 100)  (Company.getCapacityInPercent()).
- Header: X-NP-API-Version 1.5 + X-NP-APP-Version + X-NP-User-Agent (HeadersInterceptor).
"""
from __future__ import annotations

import logging

import aiohttp

from .const import (
    NP_BASE, NP_LOGIN, NP_COMPANY,
    NP_API_VERSION, NP_APP_VERSION, NP_USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


class NetpulseCapacityClient:
    """Loggt sich bei Netpulse ein und liest die Auslastung des Heimstudios."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str,
                 device_uuid: str) -> None:
        self._s = session
        self._email = email
        self._password = password
        self._device_uuid = device_uuid

    def _headers(self, cookie: str | None = None) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "X-NP-API-Version": NP_API_VERSION,
            "X-NP-APP-Version": NP_APP_VERSION,
            "X-NP-User-Agent": NP_USER_AGENT.format(uuid=self._device_uuid),
        }
        if cookie:
            h["Cookie"] = cookie
        return h

    async def _login(self) -> tuple[str, str]:
        """Gibt (homeClubUuid, jsessionid-Cookie) zurueck. Wirft bei 4xx/Netzfehler."""
        # data=... -> FormBody (application/x-www-form-urlencoded), wie die App.
        async with self._s.post(
            NP_BASE + NP_LOGIN,
            data={"username": self._email, "password": self._password},
            headers=self._headers(),
        ) as r:
            r.raise_for_status()
            data = await r.json()
            # Set-Cookie kann mehrfach vorkommen; nur JSESSIONID interessiert.
            cookie = None
            for raw in r.headers.getall("Set-Cookie", []):
                if raw.startswith("JSESSIONID="):
                    cookie = raw.split(";", 1)[0]  # "JSESSIONID=<wert>"
                    break
        home = data.get("homeClubUuid")
        if not home or not cookie:
            raise NetpulseError(f"Login ok, aber homeClubUuid/Session fehlt (home={home!r})")
        return home, cookie

    async def get_capacity(self) -> dict | None:
        """{'percent','used','total'} oder None (kein capacity-Objekt am Studio)."""
        home, cookie = await self._login()
        async with self._s.get(NP_BASE + NP_COMPANY % home,
                               headers=self._headers(cookie)) as r:
            r.raise_for_status()
            company = await r.json()

        cap = company.get("capacity") or {}
        used, total = cap.get("usedCapacity"), cap.get("totalCapacity")
        if used is None or not total:  # not total -> auch 0 abfangen (Div/0)
            return None
        return {"percent": round(used / total * 100), "used": used, "total": total}


class NetpulseError(Exception):
    """Unerwartete Netpulse-Antwort (Login ok, aber Daten fehlen)."""

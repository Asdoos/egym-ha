"""Netpulse-Client fuer Live Capacity (Studio-Auslastung).

Ohne Proxy statisch aus dem APK rekonstruiert (Dex-Analyse):
- Auslastung = `ClubCapacity` im Company-Objekt (api.netpulse.com), nicht in eGym-MWA.
- Felder (bestaetigt im Dex): capacityInPercent, currentCapacity, maxCapacity,
  usedCapacity, waitlistCapacity, webCapacity, totalCapacity.

WARNUNG (Architektur §13): Blind-Login-Versuche haben eine Konto-Sperre ausgeloest.
Deshalb macht der Coordinator GENAU EINEN Versuch und deaktiviert bei Ablehnung (4xx)
dauerhaft (self-disable).

BEKANNTE LUECKE (Live-Probing 2026-07-14): Fuer eGym-Brands wie 7stark bietet Netpulse
KEINEN Username/Passwort-Login an -> POST /np/exerciser/login antwortet mit
"StandardizedFlows not enabled" (form) bzw. "Required parameters are missing" (json),
BEVOR das Passwort geprueft wird. Die Netpulse-Session der App kommt ueber eGym-SSO
(passwordless / magic-link, siehe §4.2), NICHT ueber diesen Login. Der Code unten ist
daher lauffaehig, wird aber real 4xx -> self-disable liefern, bis der eGym->Netpulse-
Handshake einmal mitgeschnitten (Proxy) und hier ersetzt ist. ponytail: bewusst so
belassen statt eGym-Bridge blind zu raten - unverifizierbar ohne Mitschnitt.
"""
from __future__ import annotations

import logging

import aiohttp

from .const import (
    NP_BASE, NP_LOGIN, NP_CLUB,
    NP_CLIENT_TYPE, NP_BRAND_NAMES, NP_API_VERSION, NP_APP_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class NetpulseAuthRejected(Exception):
    """Server hat den Login abgelehnt (4xx) -> Rekonstruktion falsch, self-disable."""


class NetpulseCapacityClient:
    """Loggt sich einmalig bei Netpulse ein und liest die Club-Auslastung.

    Kein Auto-Retry, kein Auto-Refresh: der Coordinator ruft hoechstens 1x pro Poll
    und schaltet bei NetpulseAuthRejected dauerhaft ab.
    """

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str,
                 device_uuid: str) -> None:
        self._s = session
        self._email = email
        self._password = password
        self._device_uuid = device_uuid

    def _headers(self) -> dict[str, str]:
        # ponytail: X-NP-User-Agent wird in der App zur Laufzeit gebaut (kein Literal
        # im Dex). Plausibler Ersatz; war in §13 NICHT der Blocker (Login kam durch,
        # scheiterte an der Brand-Policy). Falsch -> hoechstens 4xx -> self-disable.
        return {
            "X-NP-API-Version": NP_API_VERSION,
            "X-NP-APP-Version": NP_APP_VERSION,
            "X-NP-User-Agent": f"{NP_APP_VERSION} (Linux; Android 14) sevenstark",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _login(self) -> None:
        # Feld-NAMEN im Dex bestaetigt; brandName/clientType-WERTE geraten (const.py).
        # Beide Brand-Keys nacheinander; erst wenn ALLE 4xx liefern -> self-disable.
        last = None
        for brand in NP_BRAND_NAMES:
            body = {
                "username": self._email,
                "password": self._password,
                "clientType": NP_CLIENT_TYPE,
                "deviceUuid": self._device_uuid,
                "brandName": brand,
            }
            async with self._s.post(NP_BASE + NP_LOGIN, json=body,
                                    headers=self._headers()) as r:
                if 400 <= r.status < 500:
                    last = f"{r.status} (brand={brand}): {(await r.text())[:150]}"
                    continue
                r.raise_for_status()
                return  # Session laeuft ueber den JSESSIONID-Cookie (aiohttp CookieJar) mit.
        raise NetpulseAuthRejected(last or "alle brandName-Varianten abgelehnt")

    async def get_capacity(self) -> dict | None:
        """{'percent','current','max','used','waitlist','web'} oder None.

        Wirft NetpulseAuthRejected nur bei 4xx im Login (-> Coordinator disabled).
        Transiente Fehler (Netz/5xx) propagieren als normale Exception (-> None-Poll).
        """
        await self._login()
        async with self._s.get(NP_BASE + NP_CLUB, headers=self._headers()) as r:
            r.raise_for_status()
            data = await r.json()

        cap = _extract_capacity(data)
        if not cap:
            return None
        return {
            "percent": cap.get("capacityInPercent"),
            "current": cap.get("currentCapacity") or cap.get("usedCapacity"),
            "max": cap.get("maxCapacity") or cap.get("totalCapacity"),
            "used": cap.get("usedCapacity"),
            "waitlist": cap.get("waitlistCapacity"),
            "web": cap.get("webCapacity"),
        }


def _extract_capacity(data) -> dict | None:
    """Findet das ClubCapacity-Objekt egal ob /club/ ein Company oder eine Liste liefert."""
    if isinstance(data, list):
        for item in data:
            cap = _extract_capacity(item)
            if cap:
                return cap
        return None
    if isinstance(data, dict):
        cap = data.get("capacity") or data.get("clubCapacity")
        if isinstance(cap, dict) and cap.get("capacityInPercent") is not None:
            return cap
    return None

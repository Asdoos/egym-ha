"""Netpulse-Client: Studio-Auslastung + Activity-Level, Challenges, Kurse, Club-Infos.

Per HTTPS-Mitschnitt der 7stark-App verifiziert (2026-07-14):
- Login: POST {brand-host}/np/exerciser/login, FORM-encoded username+password.
  Antwort-JSON hat uuid (exerciser), homeClubUuid, chainUuid; Session per Set-Cookie
  (JSESSIONID). Brand-spezifischer Host noetig, sonst 401 "StandardizedFlows...".
- Dieselbe JSESSIONID gilt fuer 7stark.netpulse.com UND mobile-api.int.api.egym.com
  (im Mitschnitt identischer Cookie-Wert) -> ein Login, alle Daten:
  * Capacity : GET {host}/np/locations/v1.0/gym-chains/{chainUuid}/location-details
               -> [{uuid, utilization:{totalCapacity,usedCapacity}}]
  * Kurse    : GET {host}/np/company/{clubUuid}/classes -> [{brief:{name,startDateTime,...}}]
  * Club-Info: GET {host}/np/company/{clubUuid}/topics  -> {total, items:[{title,...}]}
  * Activity : GET mobile-api/analysis/api/v1.0/exercisers/{uuid}/activitylevels
               -> {points,goal,daysLeft,level,maintainPoints}
  * Challenges: GET mobile-api/challenges/api/v1.0/exercisers/{uuid}/machine-challenges
               -> {challenges:[{name,userRanking,totalParticipants,...}]}
"""
from __future__ import annotations

import json
import logging
import re

import aiohttp

from .const import (
    NP_LOGIN, NP_LOCATION_DETAILS, NP_BRAND_DESC, NP_CLASSES, NP_TOPICS,
    EGYM_MOBILE_BASE, NP_ACTIVITY, NP_MACHINE_CHALLENGES,
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


def _host_candidates(alias: str | None) -> list[str]:
    """Kandidaten-Slugs aus dem eGym-Studio-Alias (z. B. '7stark Wendlingen').

    Der Netpulse-Host ist {chainAlias}.netpulse.com; der Studio-Alias enthaelt aber
    Chain + Ort. Daher: erst das erste Wort (Chain, '7stark'), dann Zusammenschreibung.
    """
    words = re.findall(r"[a-z0-9]+", (alias or "").lower())
    if not words:
        return []
    cands = [words[0], "".join(words)]
    return list(dict.fromkeys(c for c in cands if c))  # dedupe, Reihenfolge erhalten


async def detect_host(session: aiohttp.ClientSession, alias: str | None) -> str | None:
    """Leitet den Brand-Host aus dem eGym-Studio-Alias ab und validiert ihn.

    Probiert die Kandidaten gegen den unauth GET /np/brand/description und nimmt den
    ersten, der 200 + chainAlias liefert. None, wenn keiner passt (-> manuell/aus).
    """
    for slug in _host_candidates(alias):
        host = f"{slug}.netpulse.com"
        try:
            async with session.get(f"https://{host}{NP_BRAND_DESC}",
                                   headers=_headers_base()) as r:
                if r.status == 200 and (await r.json()).get("chainAlias"):
                    return host
        except Exception as err:  # noqa: BLE001 – Netz/DNS: Kandidat existiert nicht
            _LOGGER.debug("Netpulse-Host-Kandidat %r verworfen: %s", host, err)
    return None


class NetpulseClient:
    """Loggt sich EINMAL bei Netpulse ein und holt alle Cookie-basierten Daten."""

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

    async def _login(self) -> tuple[str, str, str, str]:
        """(uuid, chainUuid, homeClubUuid, JSESSIONID-Cookie). Wirft bei !=200/Netzfehler."""
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
        uuid, chain, home = data.get("uuid"), data.get("chainUuid"), data.get("homeClubUuid")
        if not uuid or not chain or not home or not cookie:
            raise NetpulseError(
                f"Login ok, aber uuid/chainUuid/homeClubUuid/Session fehlt "
                f"(uuid={uuid!r}, chain={chain!r}, home={home!r})")
        return uuid, chain, home, cookie

    async def fetch(self) -> dict:
        """Login + alle Endpunkte. Einzelne Fehler -> None fuer das Feld, kein Abbruch.

        Login-Fehler propagieren (Coordinator pausiert bei 401/403).
        """
        uuid, chain, home, cookie = await self._login()
        capacity = await self._safe(self._capacity(chain, home, cookie))
        activity = await self._safe(self._json(EGYM_MOBILE_BASE + NP_ACTIVITY % uuid, cookie))
        chal = await self._safe(self._json(EGYM_MOBILE_BASE + NP_MACHINE_CHALLENGES % uuid, cookie))
        classes = await self._safe(self._json(self._base + NP_CLASSES % home, cookie))
        topics = await self._safe(self._json(self._base + NP_TOPICS % home, cookie))
        return {
            "capacity": capacity,
            "activity": activity if isinstance(activity, dict) else None,
            "challenges": (chal or {}).get("challenges") if isinstance(chal, dict) else None,
            "classes": classes if isinstance(classes, list) else None,
            "topics": topics if isinstance(topics, dict) else None,
        }

    async def _json(self, url: str, cookie: str):
        async with self._s.get(url, headers=self._headers(cookie)) as r:
            r.raise_for_status()
            return await r.json()

    async def _capacity(self, chain: str, home: str, cookie: str) -> dict | None:
        """{'percent','used','total'} oder None (Studio ohne Auslastungsdaten)."""
        locations = await self._json(self._base + NP_LOCATION_DETAILS % chain, cookie)
        util = _utilization_for(locations, home)
        if not util:
            return None
        used, total = util.get("usedCapacity"), util.get("totalCapacity")
        if used is None or not total:  # not total -> auch 0 abfangen (Div/0)
            return None
        return {"percent": round(used / total * 100), "used": used, "total": total}

    async def _safe(self, coro):
        try:
            return await coro
        except Exception as err:  # noqa: BLE001 – Einzel-Endpunkt: nur dieses Feld None
            _LOGGER.debug("Netpulse-Teilabruf fehlgeschlagen: %s", err)
            return None


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

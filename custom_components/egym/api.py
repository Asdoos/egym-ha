"""Async-Client fuer die eGym-MWA-API (Firebase-Token, 1h TTL, Auto-Refresh)."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL, CLIENT_ID, PARTNER_LOCATION_ID,
    EP_AUTH, EP_REFRESH, EP_PROFILE, EP_BIOAGE, EP_BODY_METRICS,
    EP_WORKOUTS, EP_MUSCLE_IMBALANCES, EP_MEMBERSHIP,
    EP_CHECKIN_GYMS, EP_MOST_VISITED,
    LOCALE, MEASUREMENT_SYSTEM, HISTORY_START, STUDIO_SEARCH_RADIUS,
)

_LOGGER = logging.getLogger(__name__)

HEADERS = {"Content-Type": "application/json", "Accept": "application/json",
           "mwaProtocolVersion": "1.0"}


class AuthError(Exception):
    """Login fehlgeschlagen (falsche Zugangsdaten)."""


class EgymApi:
    """Meldet sich an, haelt Tokens, erneuert sie bei 401 automatisch."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str,
                 access_token: str | None = None, refresh_token: str | None = None) -> None:
        self._s = session
        self._email = email
        self._password = password
        self._access = access_token
        self._refresh = refresh_token

    @property
    def tokens(self) -> tuple[str | None, str | None]:
        return self._access, self._refresh

    @property
    def session(self) -> aiohttp.ClientSession:
        return self._s

    async def authenticate(self) -> None:
        """Vollstaendiger Login mit E-Mail/Passwort."""
        body = {"email": self._email, "password": self._password,
                "clientId": CLIENT_ID, "partnerLocationId": PARTNER_LOCATION_ID}
        async with self._s.post(BASE_URL + EP_AUTH, json=body, headers=HEADERS) as r:
            if r.status in (400, 401):
                raise AuthError(await r.text())
            r.raise_for_status()
            self._store(await r.json())

    async def _do_refresh(self) -> bool:
        if not self._refresh:
            return False
        async with self._s.post(BASE_URL + EP_REFRESH, json={"refreshToken": self._refresh},
                                headers=HEADERS) as r:
            if r.status == 200:
                self._store(await r.json())
                return True
        return False

    def _store(self, data: dict[str, Any]) -> None:
        self._access = data["accessToken"]
        self._refresh = data.get("refreshToken", self._refresh)

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET mit Bearer; bei 401 einmal refreshen, sonst neu einloggen."""
        if not self._access:
            await self.authenticate()
        for attempt in range(2):
            headers = {**HEADERS, "Authorization": f"Bearer {self._access}"}
            async with self._s.get(BASE_URL + path, params=params, headers=headers) as r:
                if r.status == 401 and attempt == 0:
                    if not await self._do_refresh():
                        await self.authenticate()
                    continue
                r.raise_for_status()
                return await r.json()

    async def get_profile(self) -> dict:
        return await self._get(EP_PROFILE)

    async def get_bioage(self) -> dict:
        return await self._get(EP_BIOAGE)

    async def get_body_metrics(self) -> list[dict]:
        return await self._get(EP_BODY_METRICS)

    async def get_most_visited_gym(self) -> dict | None:
        """Meistbesuchtes Studio des Users (Heimstudio) oder None."""
        try:
            data = await self._get(EP_MOST_VISITED, {"from": HISTORY_START})
            return data.get("gym")
        except aiohttp.ClientResponseError:
            return None

    async def search_gyms(self, latitude: float, longitude: float) -> list[dict]:
        """Studios im Umkreis (fuer die Auswahl im Config-Flow)."""
        return await self._get(EP_CHECKIN_GYMS, {
            "latitude": str(latitude), "longitude": str(longitude),
            "radius": str(STUDIO_SEARCH_RADIUS), "mapBounds": "false",
        })

    async def get_workouts(self, gym_location_id: str, completed_before: str) -> list[dict]:
        """Trainingshistorie (Sessions mit completedAt), neueste zuerst."""
        return await self._get(EP_WORKOUTS, {
            "gymLocationId": gym_location_id,
            "completedAfter": HISTORY_START,
            "completedBefore": completed_before,
            "measurementSystem": MEASUREMENT_SYSTEM,
            "locale": LOCALE,
        })

    async def get_muscle_imbalances(self, zone_id: str) -> dict:
        return await self._get(EP_MUSCLE_IMBALANCES, {"zoneId": zone_id})

    async def get_membership(self) -> list[dict]:
        return await self._get(EP_MEMBERSHIP)

"""DataUpdateCoordinator – holt BioAge, Body-Metrics und Profil in einem Poll."""
from __future__ import annotations

import logging

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .api import EgymApi
from .const import CONF_STUDIO_ID, DOMAIN, SCAN_INTERVAL
from .netpulse_api import NetpulseCapacityClient

_LOGGER = logging.getLogger(__name__)


class EgymCoordinator(DataUpdateCoordinator):
    """Ein Poll/Stunde. data = {profile, bioage, metrics(dict type->value)}."""

    def __init__(self, hass: HomeAssistant, api: EgymApi, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api
        self.entry = entry
        # Pausiert den Netpulse-Login nach einer Auth-Ablehnung (401/403), damit ein
        # falsch konfiguriertes Passwort nicht stuendlich neu probiert -> Konto-Sperre.
        # In-memory: Reload/Neustart der Integration hebt die Pause auf.
        self._np_paused = False

    async def _async_update_data(self) -> dict:
        try:
            profile = await self.api.get_profile()
            bioage = await self.api.get_bioage()
            metrics_raw = await self.api.get_body_metrics()
            # gewaehltes Studio (Config-Flow); Historie ist ohnehin global am egymAccountId
            gym_id = self.entry.data[CONF_STUDIO_ID]
            before = (dt_util.utcnow() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            workouts = await self.api.get_workouts(gym_id, before)
        except Exception as err:  # Netz/Auth -> Coordinator meldet Entities als unavailable
            raise UpdateFailed(str(err)) from err

        # Optionale Endpunkte: ein 404/leer darf nicht den ganzen Poll kippen
        zone = self.hass.config.time_zone or "UTC"
        imbalances = await self._optional(self.api.get_muscle_imbalances(zone))
        membership = await self._optional(self.api.get_membership())
        capacity = await self._capacity()

        # rotierte Tokens persistieren -> Neustart ohne Re-Login
        access, refresh = self.api.tokens
        new_data = {**self.entry.data, "access_token": access, "refresh_token": refresh}
        if new_data != dict(self.entry.data):
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)

        metrics = {m["type"]: m for m in metrics_raw if m.get("value") is not None}
        return {"profile": profile, "bioage": bioage, "metrics": metrics,
                "workouts": workouts, "imbalances": imbalances, "membership": membership,
                "capacity": capacity}

    async def _capacity(self) -> dict | None:
        """Netpulse Studio-Auslastung. Auth-Ablehnung pausiert bis Reload."""
        if self._np_paused:
            return None
        client = NetpulseCapacityClient(
            self.api.session,
            self.entry.data[CONF_EMAIL], self.entry.data[CONF_PASSWORD],
            device_uuid=self.entry.entry_id,
        )
        try:
            cap = await client.get_capacity()
        except Exception as err:  # noqa: BLE001 – Login/Netz: nur diesen Poll ueberspringen
            if getattr(err, "status", None) in (401, 403):  # Auth abgelehnt -> nicht hammern
                self._np_paused = True
                _LOGGER.warning("Studio-Auslastung: Login abgelehnt (%s). Pausiert bis zum "
                                "Neuladen der Integration (Lockout-Schutz).", err)
            else:
                _LOGGER.warning("Studio-Auslastung: Netpulse-Abruf fehlgeschlagen: %s", err)
            return None
        if cap is None:
            _LOGGER.debug("Studio-Auslastung: Studio liefert kein capacity-Objekt")
        return cap

    async def _optional(self, coro):
        """Wrapper fuer nicht-kritische Endpunkte -> None statt UpdateFailed."""
        try:
            return await coro
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Optionaler Endpunkt fehlgeschlagen: %s", err)
            return None

"""Config-Flow (White-Label): 1) Login  2) Studio auswählen."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthError, EgymApi
from .const import (
    CONF_NP_HOST, CONF_STUDIO_ID, CONF_STUDIO_NAME, DOMAIN, NP_HOST_DEFAULT,
)

LOGIN_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str})


class EgymConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._api: EgymApi | None = None
        self._studios: dict[str, str] = {}

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()

            api = EgymApi(async_get_clientsession(self.hass), email,
                                user_input[CONF_PASSWORD])
            try:
                await api.authenticate()
            except AuthError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                access, refresh = api.tokens
                self._api = api
                self._data = {CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD],
                              "access_token": access, "refresh_token": refresh}
                return await self.async_step_studio()
        return self.async_show_form(step_id="user", data_schema=LOGIN_SCHEMA, errors=errors)

    async def async_step_studio(self, user_input=None) -> ConfigFlowResult:
        """Studioliste (Heimstudio + Studios nahe HA-Standort) zur Auswahl anbieten."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._studios.get(user_input[CONF_STUDIO_ID], self._data[CONF_EMAIL]),
                data={**self._data, CONF_STUDIO_ID: user_input[CONF_STUDIO_ID],
                      CONF_STUDIO_NAME: self._studios.get(user_input[CONF_STUDIO_ID], ""),
                      CONF_NP_HOST: user_input.get(CONF_NP_HOST, NP_HOST_DEFAULT).strip()},
            )

        # Optionen sammeln: Heimstudio zuerst, dann Umkreis um HA-Standort
        self._studios = {}
        home = await self._api.get_most_visited_gym()
        if home and home.get("gymUUID"):
            self._studios[home["gymUUID"]] = f"⭐ {home.get('alias') or home['gymUUID']}"
        try:
            gyms = await self._api.search_gyms(self.hass.config.latitude,
                                               self.hass.config.longitude)
        except Exception:  # noqa: BLE001
            gyms = []
        for g in gyms:
            gid = g.get("id")
            if gid and gid not in self._studios:
                self._studios[gid] = g.get("name") or gid

        studio_field = str if not self._studios else vol.In(self._studios)
        schema = vol.Schema({
            vol.Required(CONF_STUDIO_ID): studio_field,
            # Netpulse-Host der Marke (Auslastungs-Sensor). Andere Brands: hier anpassen.
            vol.Optional(CONF_NP_HOST, default=NP_HOST_DEFAULT): str,
        })
        return self.async_show_form(step_id="studio", data_schema=schema)

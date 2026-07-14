"""eGym / Netpulse Studio Integration (White-Label)."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import EgymApi
from .const import DOMAIN
from .coordinator import EgymCoordinator, NetpulseCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    api = EgymApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        entry.data.get("access_token"),
        entry.data.get("refresh_token"),
    )
    coordinator = EgymCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    # Netpulse teilt sich die (bereits authentifizierte) eGym-Session, laeuft aber im
    # 5-Min-Takt. Optional -> async_refresh (wirft nicht), blockiert Setup nicht.
    netpulse = NetpulseCoordinator(hass, api, entry)
    await netpulse.async_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "egym": coordinator, "netpulse": netpulse,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        return True
    return False

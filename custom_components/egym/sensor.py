"""Sensor-Entities: BioAge-Werte + Koerperzusammensetzung."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_STUDIO_NAME, DOMAIN, LOCALE
from .coordinator import EgymCoordinator

NAME_KEY = LOCALE.split("_")[0]  # "de_DE" -> "de"


def _num(v):
    """BioAge-Felder sind mal {value:X}, mal direkt X, mal null."""
    if isinstance(v, dict):
        v = v.get("value")
    return v


# key, Name, Extraktor(bioage)->Wert, Einheit, device_class, icon
BIOAGE_SENSORS: list[tuple[str, str, Callable[[dict], object], str | None, str | None, str]] = [
    ("total_bio_age", "Biologisches Alter",
     lambda b: _num(b.get("totalDetails", {}).get("totalBioAge")), "a", None, "mdi:calendar-heart"),
    ("metabolic_age", "Stoffwechselalter",
     lambda b: _num(b.get("metabolicDetails", {}).get("metabolicAge")), "a", None, "mdi:fire"),
    ("flexibility_age", "Beweglichkeitsalter",
     lambda b: _num(b.get("flexibilityDetails", {}).get("flexibilityAge")), "a", None, "mdi:yoga"),
    ("cardio_age", "Kardio-Alter",
     lambda b: _num(b.get("cardioBioAgeDetails", {}).get("cardioAge")), "a", None, "mdi:heart-pulse"),
    ("muscle_bio_age", "Kraft-Alter (gesamt)",
     lambda b: _num(b.get("strengthBioAgeDetails", {}).get("muscleBioAge")), "a", None, "mdi:arm-flex"),
    ("upper_body_age", "Oberkoerper-Alter",
     lambda b: _num(b.get("strengthBioAgeDetails", {}).get("upperBodyAge")), "a", None, "mdi:weight-lifter"),
    ("core_age", "Rumpf-Alter",
     lambda b: _num(b.get("strengthBioAgeDetails", {}).get("coreAge")), "a", None, "mdi:human-handsup"),
    ("lower_body_age", "Unterkoerper-Alter",
     lambda b: _num(b.get("strengthBioAgeDetails", {}).get("lowerBodyAge")), "a", None, "mdi:run"),
    ("bmi", "BMI",
     lambda b: _num(b.get("metabolicDetails", {}).get("bmi")), None, None, "mdi:human"),
    ("body_fat", "Koerperfett",
     lambda b: _num(b.get("metabolicDetails", {}).get("bodyFat")), PERCENTAGE, None, "mdi:water-percent"),
    ("resting_heart_rate", "Ruhepuls",
     lambda b: _num(b.get("cardioBioAgeDetails", {}).get("restingHeartRate")), "bpm", None, "mdi:heart"),
    ("vo2max", "VO2max",
     lambda b: _num(b.get("cardioBioAgeDetails", {}).get("vo2max")), "ml/kg/min", None, "mdi:lungs"),
]

# type (aus latest-body-metrics) -> Name, Einheit, device_class, icon
METRIC_SENSORS: dict[str, tuple[str, str, str | None, str]] = {
    "SKELETAL_MUSCLE_MASS_KG": ("Skelettmuskelmasse", UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT, "mdi:arm-flex"),
    "BODY_FAT_MASS_MID_KG": ("Koerperfettmasse", UnitOfMass.KILOGRAMS, SensorDeviceClass.WEIGHT, "mdi:scale-bathroom"),
    "BODY_WATER_PERCENTS": ("Koerperwasser", PERCENTAGE, None, "mdi:water"),
    "BODY_WATER_MAX_LITER": ("Koerperwasser (Volumen)", UnitOfVolume.LITERS, None, "mdi:cup-water"),
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry,
                            add_entities: AddEntitiesCallback) -> None:
    coordinator: EgymCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        EgymBioAgeSensor(coordinator, entry, *cfg) for cfg in BIOAGE_SENSORS
    ]
    # nur Metriken anlegen, die die API auch liefert
    for mtype, cfg in METRIC_SENSORS.items():
        if mtype in coordinator.data.get("metrics", {}):
            entities.append(EgymMetricSensor(coordinator, entry, mtype, *cfg))
    entities.append(EgymLastWorkoutSensor(coordinator, entry))
    entities.append(EgymWorkoutCountSensor(coordinator, entry))
    if coordinator.data.get("imbalances") is not None:
        entities.append(EgymImbalanceSensor(coordinator, entry))
    if coordinator.data.get("membership"):
        entities.append(EgymMembershipSensor(coordinator, entry))
    # Immer anlegen: sonst verschwindet der Sensor dauerhaft, wenn der erste
    # Netpulse-Abruf (Login/Studio ohne capacity) scheitert. Ohne Daten -> "unbekannt".
    entities.append(EgymCapacitySensor(coordinator, entry))
    # Weitere Netpulse-Daten nur, wenn der Login sie geliefert hat.
    if coordinator.data.get("activity"):
        entities.append(EgymActivityLevelSensor(coordinator, entry))
        entities.append(EgymActivityPointsSensor(coordinator, entry))
    if coordinator.data.get("challenges") is not None:
        entities.append(EgymChallengesSensor(coordinator, entry))
    if coordinator.data.get("classes"):
        entities.append(EgymNextClassSensor(coordinator, entry))
    if coordinator.data.get("topics"):
        entities.append(EgymClubInfoSensor(coordinator, entry))
    add_entities(entities)


class _Base(CoordinatorEntity[EgymCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: EgymCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        p = coordinator.data.get("profile", {})
        who = " ".join(filter(None, [p.get("firstName"), p.get("lastName")])) or "Mitglied"
        studio = entry.data.get(CONF_STUDIO_NAME, "").lstrip("⭐ ").strip() or "eGym"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"{studio} ({who})",
            manufacturer="eGym / Netpulse",
            model=studio,
        )


class EgymBioAgeSensor(_Base):
    def __init__(self, coordinator, entry, key, name, extractor, unit, device_class, icon) -> None:
        super().__init__(coordinator, entry, key)
        self._extractor = extractor
        self._attr_translation_key = key
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon

    @property
    def native_value(self):
        return self._extractor(self.coordinator.data.get("bioage", {}))


class EgymMetricSensor(_Base):
    def __init__(self, coordinator, entry, mtype, name, unit, device_class, icon) -> None:
        super().__init__(coordinator, entry, mtype.lower())
        self._mtype = mtype
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon

    @property
    def native_value(self):
        m = self.coordinator.data.get("metrics", {}).get(self._mtype)
        return m.get("value") if m else None

    @property
    def extra_state_attributes(self):
        m = self.coordinator.data.get("metrics", {}).get(self._mtype) or {}
        return {"created_at": m.get("createdAt"), "source": m.get("source")}


def _first_workout(coordinator) -> dict | None:
    w = coordinator.data.get("workouts") or []
    return w[0] if w else None  # API liefert neueste zuerst


class EgymLastWorkoutSensor(_Base):
    """Zeitpunkt des letzten abgeschlossenen Trainings."""
    _attr_state_class = None
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "last_workout")
        self._attr_name = "Letztes Training"

    @property
    def native_value(self):
        w = _first_workout(self.coordinator)
        if not w or not w.get("completedAt"):
            return None
        dt = dt_util.parse_datetime(w["completedAt"])
        if dt is None:
            return None
        if dt.tzinfo is None:  # naives Datum + separates timezone-Feld
            tz = dt_util.get_time_zone(w.get("timezone", "UTC")) or dt_util.UTC
            dt = dt.replace(tzinfo=tz)
        return dt

    @property
    def extra_state_attributes(self):
        w = _first_workout(self.coordinator) or {}
        exercises = w.get("exercises") or []
        return {
            "plan": w.get("workoutPlanName"),
            "exercise_count": len(exercises),
            "exercises": [e.get("label") for e in exercises],
        }


class EgymWorkoutCountSensor(_Base):
    """Anzahl abgeschlossener Trainings (gesamte Historie)."""
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:counter"
    _attr_native_unit_of_measurement = "Trainings"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "workout_count")
        self._attr_name = "Trainings gesamt"

    @property
    def native_value(self):
        return len(self.coordinator.data.get("workouts") or [])


class EgymImbalanceSensor(_Base):
    """Anzahl erkannter Muskel-Dysbalancen."""
    _attr_icon = "mdi:scale-unbalanced"
    _attr_native_unit_of_measurement = "Dysbalancen"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "muscle_imbalances")
        self._attr_name = "Muskel-Dysbalancen"

    def _items(self) -> list[dict]:
        d = self.coordinator.data.get("imbalances") or {}
        return d.get("muscleImbalances") or []

    @property
    def native_value(self):
        return len(self._items())

    @property
    def extra_state_attributes(self):
        return {"pairs": [f"{i.get('agonistMuscle')}/{i.get('antagonistMuscle')}"
                          for i in self._items()]}


class EgymCapacitySensor(_Base):
    """Live-Auslastung des Studios in % (Netpulse ClubCapacity)."""
    _attr_icon = "mdi:account-group"
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "studio_auslastung")
        self._attr_name = "Studio-Auslastung"

    @property
    def native_value(self):
        return (self.coordinator.data.get("capacity") or {}).get("percent")

    @property
    def extra_state_attributes(self):
        c = self.coordinator.data.get("capacity") or {}
        return {"used": c.get("used"), "total": c.get("total")}


class EgymMembershipSensor(_Base):
    """Mitglied seit (Beginn der Mitgliedschaft)."""
    _attr_state_class = None
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:card-account-details"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "membership_since")
        self._attr_name = "Mitglied seit"

    def _membership(self) -> dict:
        m = self.coordinator.data.get("membership") or []
        return (m[0].get("membership") if m else {}) or {}

    @property
    def native_value(self):
        ts = self._membership().get("membershipStartTimestamp")
        return dt_util.parse_datetime(ts) if ts else None

    @property
    def extra_state_attributes(self):
        m = self._membership()
        return {"uuid": m.get("uuid"),
                "end": m.get("membershipEndTimestamp"),
                "next_billing": m.get("nextBillingTimestamp")}


class EgymActivityLevelSensor(_Base):
    """eGym Activity Level (wood/steel/... )."""
    _attr_state_class = None
    _attr_icon = "mdi:medal"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "activity_level")
        self._attr_name = "Aktivitätslevel"

    @property
    def native_value(self):
        return (self.coordinator.data.get("activity") or {}).get("level")

    @property
    def extra_state_attributes(self):
        a = self.coordinator.data.get("activity") or {}
        return {"points": a.get("points"), "goal": a.get("goal"),
                "days_left": a.get("daysLeft"), "maintain_points": a.get("maintainPoints")}


class EgymActivityPointsSensor(_Base):
    """Aktivitätspunkte der laufenden Periode (Ziel als Attribut)."""
    _attr_icon = "mdi:star-four-points"
    _attr_native_unit_of_measurement = "Punkte"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "activity_points")
        self._attr_name = "Aktivitätspunkte"

    @property
    def native_value(self):
        return (self.coordinator.data.get("activity") or {}).get("points")

    @property
    def extra_state_attributes(self):
        a = self.coordinator.data.get("activity") or {}
        return {"goal": a.get("goal"), "days_left": a.get("daysLeft")}


class EgymChallengesSensor(_Base):
    """Anzahl aktiver Maschinen-Challenges (eGym Gameday etc.)."""
    _attr_icon = "mdi:trophy"
    _attr_native_unit_of_measurement = "Challenges"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "active_challenges")
        self._attr_name = "Aktive Challenges"

    def _items(self) -> list[dict]:
        return self.coordinator.data.get("challenges") or []

    @property
    def native_value(self):
        return len(self._items())

    @property
    def extra_state_attributes(self):
        items = self._items()
        return {"joined": sum(1 for c in items if c.get("userJoined")),
                "challenges": [c.get("name") for c in items]}


def _next_class(coordinator) -> dict | None:
    """Naechster noch nicht begonnener Kurs (kleinste startDateTime >= jetzt)."""
    now_ms = dt_util.utcnow().timestamp() * 1000
    briefs = [c.get("brief") or {} for c in (coordinator.data.get("classes") or [])]
    upcoming = [b for b in briefs if b.get("startDateTime") and b["startDateTime"] >= now_ms]
    return min(upcoming, key=lambda b: b["startDateTime"]) if upcoming else None


class EgymNextClassSensor(_Base):
    """Startzeitpunkt des naechsten Kurses im Heimstudio."""
    _attr_state_class = None
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "next_class")
        self._attr_name = "Nächster Kurs"

    @property
    def native_value(self):
        b = _next_class(self.coordinator)
        return dt_util.utc_from_timestamp(b["startDateTime"] / 1000) if b else None

    @property
    def extra_state_attributes(self):
        b = _next_class(self.coordinator) or {}
        maxc, booked = b.get("maxCapacity"), b.get("totalBooked")
        free = maxc - booked if maxc is not None and booked is not None else None
        return {"name": b.get("name"),
                "free_spots": free,
                "booked": b.get("booked"),
                "upcoming_count": sum(
                    1 for c in (self.coordinator.data.get("classes") or [])
                    if (c.get("brief") or {}).get("startDateTime", 0) >= dt_util.utcnow().timestamp() * 1000)}


class EgymClubInfoSensor(_Base):
    """Anzahl der Club-Info-Themen (Netpulse topics)."""
    _attr_icon = "mdi:bulletin-board"
    _attr_native_unit_of_measurement = "Themen"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "club_info")
        self._attr_name = "Club-Infos"

    def _topics(self) -> dict:
        return self.coordinator.data.get("topics") or {}

    @property
    def native_value(self):
        t = self._topics()
        return t.get("total") if t.get("total") is not None else len(t.get("items") or [])

    @property
    def extra_state_attributes(self):
        return {"titles": [i.get("title") for i in (self._topics().get("items") or [])]}

# eGym / Wellpass Studio — Home Assistant Integration

[![HACS: Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Integration](https://img.shields.io/badge/Home%20Assistant-Integration-03A9F4.svg)](https://www.home-assistant.io/)
[![Version](https://img.shields.io/badge/version-0.1.0-brightgreen.svg)](https://github.com/Asdoos/egym-ha/releases)
[![iot_class](https://img.shields.io/badge/iot__class-cloud__polling-orange.svg)](https://developers.home-assistant.io/docs/creating_integration_manifest/#iot-class)

White-Label-Integration für Fitnessstudios auf der **eGym/Netpulse**-Plattform
(z. B. 7stark, EGYM Wellpass u. a.). Sie liest deine Fitness- und Körperdaten über die
eGym-MWA-API und die Live-Studioauslastung über die Netpulse-API — als ~20 Sensoren
direkt in Home Assistant.

> ⚠️ Inoffizielle, reverse-engineerte Integration. Nutzung nur mit deinem **eigenen**
> Account und moderatem Polling. Die API kann sich jederzeit ändern.

---

## Inhalt

- [Funktionen](#funktionen)
- [Installation](#installation)
- [Einrichtung](#einrichtung)
- [Sensoren](#sensoren)
- [Funktionsweise](#funktionsweise)
- [Hinweise & Grenzen](#hinweise--grenzen)
- [Fehlerbehebung](#fehlerbehebung)

---

## Funktionen

- 🧬 **BioAge & Körperwerte** — Biologisches Alter, BMI, Körperfett, Muskelmasse u. v. m.
- 🏋️ **Trainingsdaten** — letztes Training, Trainings gesamt, Muskel-Dysbalancen.
- 📊 **Live-Studioauslastung** — aktueller Auslastungsgrad deines Heimstudios (alle 5 min).
- 🗓️ **Studio-Kontext** — Aktivitätslevel, Challenges, nächster Kurs, Club-Infos.
- 🔒 **Privat** — kein Tracking, keine Telemetrie, keine externen Python-Abhängigkeiten.

---

## Installation

### HACS (empfohlen)

1. HACS → ⋮ → **Custom repositories** → `https://github.com/Asdoos/egym-ha`, Kategorie **Integration**.
2. „eGym / Wellpass Studio" installieren und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „eGym / Wellpass Studio"**.

### Manuell

1. Ordner `custom_components/egym/` nach `<HA-config>/custom_components/` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „eGym / Wellpass Studio"**.

---

## Einrichtung

Zwei Schritte im Config-Flow:

1. **Login** — E-Mail + Passwort deiner **eGym-ID**.
2. **Studio wählen** — ⭐ markiert dein meistbesuchtes Studio; darunter Studios im Umkreis
   (50 km) deines HA-Standorts (`homeassistant:` → `latitude` / `longitude`). Ist die Liste
   leer, kannst du eine Studio-ID manuell eintragen.

---

## Sensoren

Rund 20 Sensoren, gruppiert nach Bereich:

| Bereich | Sensoren |
|---|---|
| **BioAge** | Biologisches Alter, Stoffwechselalter, Beweglichkeitsalter, Kardio-Alter, Kraft-Alter (gesamt / Oberkörper / Rumpf / Unterkörper) |
| **Körper** | BMI, Körperfett, Skelettmuskelmasse, Körperfettmasse, Körperwasser (% / L) |
| **Kardio** | Ruhepuls, VO2max *(nur wenn Werte hinterlegt)* |
| **Training** | Letztes Training (Zeitstempel), Trainings gesamt |
| **Studio (Netpulse)** | Studio-Auslastung (Live %), Aktivitätslevel, Aktivitätspunkte, Aktive Challenges, Nächster Kurs, Club-Infos |
| **Sonstiges** | Muskel-Dysbalancen, Mitglied seit |

> Sensoren ohne hinterlegte Werte (z. B. Kardio, wenn nie gemessen) erscheinen als
> *nicht verfügbar* und aktivieren sich automatisch, sobald im Studio Werte erfasst werden.

---

## Funktionsweise

- **`iot_class: cloud_polling`** mit zwei getrennten Coordinators:
  - **eGym-Messwerte** — **1×/Stunde** (ändern sich nur nach einem Studiobesuch).
  - **Netpulse-Livedaten** (Auslastung u. a.) — **alle 5 min**.
- **Authentifizierung** — eGym-MWA `authenticate` (Firebase-Token, 1 h Gültigkeit),
  automatischer Refresh bei `401`.
- **Netpulse-Session** — Login mit denselben Zugangsdaten; eine `JSESSIONID` gilt sowohl für
  Netpulse (Auslastung, Kurse, Club-Infos) als auch für die eGym-Mobile-API
  (Aktivitätslevel, Challenges).
- **Keine externen Abhängigkeiten** — HA bringt `aiohttp` bereits mit.

---

## Hinweise & Grenzen

- **Daten sind global** an deinem eGym-Account, nicht am Studio. Die Studio-Wahl steuert
  Anzeige/Branding und den Workouts-Kontext, **nicht** die Messwerte.
- **Studio-Auslastung (Live Capacity)** stammt aus der Netpulse-API
  ([`netpulse_api.py`](custom_components/egym/netpulse_api.py)) und erscheint nur, wenn dein
  Studio überhaupt Auslastungsdaten liefert — sonst bleibt der Sensor unbelegt.
- **Andere Marken** — für nicht-eGym-Marken ggf. `CLIENT_ID` in
  [`const.py`](custom_components/egym/const.py) anpassen.
- **Inoffizielle API** — reverse-engineert, kann sich jederzeit ändern.

---

## Fehlerbehebung

| Problem | Lösung |
|---|---|
| **`invalid_auth`** | E-Mail/Passwort sind die **eGym-ID**-Zugangsdaten (nicht zwingend die Studio-App). |
| **Studioliste leer** | HA-Standort (`latitude`/`longitude`) setzen oder Studio-ID manuell eintragen. |
| **Auslastung fehlt** | Studio liefert keine Netpulse-Capacity-Daten — dann bleibt der Sensor *nicht verfügbar*. |

Auth vorab testen:

```bash
python test_auth.py --email … --password …
```

---

## Lizenz & Haftung

Privates, inoffizielles Projekt ohne Verbindung zu eGym, EGYM Wellpass oder Netpulse.
Nutzung auf eigene Verantwortung. Marken- und Produktnamen gehören ihren jeweiligen Inhabern.

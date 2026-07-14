# eGym / Wellpass Studio — Home Assistant Integration

White-Label-Integration für Fitnessstudios auf der **eGym/Netpulse**-Plattform
(z. B. 7stark, EGYM Wellpass u. a.). Liest deine Fitnessdaten über die eGym-MWA-API.

## Installation

### HACS (empfohlen)
1. HACS → ⋮ → **Custom repositories** → `https://github.com/Asdoos/egym-ha`, Kategorie **Integration**.
2. „eGym / Wellpass Studio" installieren, Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „eGym / Wellpass Studio"**.

### Manuell
1. Ordner `custom_components/egym/` nach `<HA-config>/custom_components/` kopieren.
2. Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen → „eGym / Wellpass Studio"**.

## Einrichtung (2 Schritte)
1. **Login** – E-Mail + Passwort deiner eGym-ID.
2. **Studio wählen** – ⭐ = dein meistbesuchtes Studio; darunter Studios im Umkreis deines
   HA-Standorts (`homeassistant:` → `latitude/longitude`). Falls die Liste leer ist, kannst du
   eine Studio-ID manuell eintragen.

## Sensoren (~20)
| Bereich | Sensoren |
|---|---|
| BioAge | Biologisches Alter, Stoffwechsel-, Beweglichkeits-, Kardio-Alter; Kraft-Alter gesamt/Oberkörper/Rumpf/Unterkörper |
| Körper | BMI, Körperfett, Skelettmuskelmasse, Körperfettmasse, Körperwasser (% / L) |
| Kardio | Ruhepuls, VO2max *(nur wenn Werte hinterlegt)* |
| Training | Letztes Training (Zeitstempel), Trainings gesamt |
| Studio (Netpulse) | Studio-Auslastung (Live %), Aktivitätslevel, Aktivitätspunkte, Aktive Challenges, Nächster Kurs, Club-Infos |
| Sonstiges | Muskel-Dysbalancen, Mitglied seit |

Sensoren ohne hinterlegte Werte (z. B. Kardio, wenn nie gemessen) erscheinen als *nicht verfügbar*
und aktivieren sich automatisch, sobald im Studio Werte erfasst werden.

## Technik
- `iot_class: cloud_polling`. eGym-Messwerte **1×/Stunde** (ändern sich nur nach Studiobesuch); Netpulse-Livedaten (Auslastung etc.) **alle 5 min** über einen separaten Coordinator.
- Auth: eGym-MWA `authenticate` (Firebase-Token, 1 h), automatischer Refresh bei 401.
- Keine externen Python-Abhängigkeiten (HA bringt `aiohttp` mit).
- Kein Tracking/Telemetrie — reines Lesen.

## Hinweise & Grenzen
- **Daten sind global** an deinem eGym-Account, nicht am Studio — die Studio-Wahl steuert Anzeige/
  Branding und den Workouts-Kontext, nicht die Messwerte.
- **Studio-Auslastung (Live Capacity)** kommt aus der Netpulse-API (`netpulse_api.py`): Login mit
  denselben Zugangsdaten, dann Prozentwert des Heimstudios (`used/total`). Der Sensor erscheint nur,
  wenn dein Studio überhaupt Auslastungsdaten liefert; sonst bleibt er unbelegt.
- **Andere Marken:** Für nicht-eGym-Marken ggf. `CLIENT_ID` in `const.py` anpassen.
- Reverse-engineerte, inoffizielle API — kann sich jederzeit ändern. Nur eigener Account, moderates Polling.

## Fehlerbehebung
- **„invalid_auth"** → E-Mail/Passwort sind die **eGym-ID**-Zugangsdaten (nicht zwingend Studio-App).
- **Studioliste leer** → HA-Standort setzen oder Studio-ID manuell eintragen.
- Auth vorab testen: `python ../../test_auth.py --email … --password …`.

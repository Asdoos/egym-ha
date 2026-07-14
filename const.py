"""Konstanten der eGym / Netpulse-Integration (White-Label)."""
from datetime import timedelta

DOMAIN = "egym"

# eGym MWA-API – per Live-Probing bestaetigt (siehe 7stark-App-Architektur.md §4.0)
BASE_URL = "https://mwa-api.int.api.egym.com"
CLIENT_ID = "egym"
# Login braucht eine gueltige partnerLocationId. Daten haengen aber am egymAccountId
# (global), nicht an der Location -> "1" genuegt als Bootstrap fuers Authenticate.
PARTNER_LOCATION_ID = "1"

# Config-Entry-Keys
CONF_STUDIO_ID = "studio_id"
CONF_STUDIO_NAME = "studio_name"

# Umkreis (Meter) fuer die Studiosuche im Config-Flow
STUDIO_SEARCH_RADIUS = 50000

EP_AUTH = "/mwa/api/auth/v1.0/authenticate"
EP_REFRESH = "/mwa/api/auth/v1.0/refresh-token"
EP_PROFILE = "/mwa/api/users/v1.0/profile"
EP_BIOAGE = "/mwa/api/analysis/v1.0/bio-age"
EP_BODY_METRICS = "/mwa/api/measurements/v1.0/latest-body-metrics"
EP_WORKOUTS = "/mwa/api/workouts/v1.0/workouts"
EP_MUSCLE_IMBALANCES = "/mwa/api/analysis/v1.0/muscle-imbalances"
EP_MEMBERSHIP = "/mwa/api/user/membership"
EP_CHECKIN_GYMS = "/mwa/api/checkin/v1/gyms"
EP_MOST_VISITED = "/mwa/api/gym-finder/v1/gyms/most-visited"

# --- Netpulse Live-Capacity (Studio-Auslastung) -------------------------------
# Statisch aus dem APK rekonstruiert (Dex): api.netpulse.com, ClubCapacity liegt
# im Company-Objekt (DB-Spalte `companies.capacity`). Login ist brand-gated und
# hat bei Blind-Versuchen schon eine Konto-Sperre ausgeloest -> genau EIN Versuch,
# danach self-disable (siehe coordinator + netpulse_api). Details: Architektur §13.
NP_BASE = "https://api.netpulse.com"
NP_LOGIN = "/np/exerciser/login"      # klassischer Flow
NP_CLUB = "/np/exerciser/company/favorite"  # Heimstudio-Company inkl. capacity
# Live-Probing 2026-07-14: /np/exerciser/club/ -> 404 (falsch);
# /np/exerciser/company/favorite -> 403 (existiert, braucht Auth) = richtiger Kandidat.
# ponytail: Header-/Body-Werte sind aus dem Dex geraten (clientType/brandName bestaetigte
# Feld-NAMEN, Werte nicht). Falscher Wert -> 4xx -> self-disable, kein Lock. Verifizieren
# liesse sich nur per 1 echtem Login-Mitschnitt (bewusst ohne Proxy gebaut).
NP_CLIENT_TYPE = "ANDROID"
# ponytail: 7stark-spezifische Platzhalter fuer das (aktuell blockierte, studio-
# spezifische) Capacity-Feature. Generisch erst relevant, wenn der eGym->Netpulse-
# Handshake gemappt ist (Architektur §13). Bis dahin nur Beispielwerte.
NP_BRAND_NAMES = ("sevenstark", "7stark")
NP_API_VERSION = "2.0"
NP_APP_VERSION = "7starkApp/1.2"
CONF_NP_DISABLED = "netpulse_disabled"

# gymLocationId (UUID) wird aus partnerLocationId via mappings aufgeloest und gecacht.
LOCALE = "de_DE"           # Query-Param; Namens-Key im JSON ist LOCALE.split("_")[0] = "de"
MEASUREMENT_SYSTEM = "METRIC"
HISTORY_START = "2015-01-01T00:00:00Z"   # weit genug zurueck -> gesamte Historie

# Messwerte aendern sich nur nach einem Studiobesuch -> stuendlich reicht dick.
# ponytail: 1h fix, per Options-Flow konfigurierbar machen wenn jemand es braucht.
SCAN_INTERVAL = timedelta(hours=1)

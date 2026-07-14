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
# Per HTTPS-Mitschnitt der App verifiziert (2026-07-14). WICHTIG: brand-spezifischer
# Host (nicht api.netpulse.com) - sonst 401 "StandardizedFlows not enabled".
# Login  = POST /np/exerciser/login (Form username+password) -> JSESSIONID + chainUuid.
# Capacity = GET /np/locations/v1.0/gym-chains/{chainUuid}/location-details
#            -> [{uuid, utilization:{gymLocationId,totalCapacity,usedCapacity}}]
CONF_NP_HOST = "netpulse_host"   # aus Studio-Alias erkannt oder manuell; KEIN Default
NP_LOGIN = "/np/exerciser/login"
NP_LOCATION_DETAILS = "/np/locations/v1.0/gym-chains/%s/location-details"
NP_BRAND_DESC = "/np/brand/description"   # unauth; chainAlias == Host-Subdomain

# Header aus dem Mitschnitt (App v1.2, versionCode 110; deviceUid war leer).
NP_API_VERSION = "1.5"
NP_APP_VERSION = "1.2"
NP_USER_AGENT = ("clientType=MOBILE_DEVICE; devicePlatform=ANDROID; deviceUid=; "
                 "applicationName=7stark; applicationVersion=1.2; "
                 "applicationVersionCode=110")

# gymLocationId (UUID) wird aus partnerLocationId via mappings aufgeloest und gecacht.
LOCALE = "de_DE"           # Query-Param; Namens-Key im JSON ist LOCALE.split("_")[0] = "de"
MEASUREMENT_SYSTEM = "METRIC"
HISTORY_START = "2015-01-01T00:00:00Z"   # weit genug zurueck -> gesamte Historie

# Messwerte aendern sich nur nach einem Studiobesuch -> stuendlich reicht dick.
# ponytail: 1h fix, per Options-Flow konfigurierbar machen wenn jemand es braucht.
SCAN_INTERVAL = timedelta(hours=1)

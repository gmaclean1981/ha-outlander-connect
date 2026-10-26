"""Constants for the North American Mitsubishi Connect integration."""
DOMAIN = "outlander_connect"
NAME = "Outlander Connect"
VERSION = "0.3.0"
HOST = "us-m.aerpf.com"
CONF_VIN = "vin"
CONF_VEHICLE = "vehicle"
CONF_POLL_MINUTES = "poll_minutes"
CONF_GPS = "gps"
DEFAULT_POLL_MINUTES = 5
HEALTH_INTERVAL_SECONDS = 900
PLATFORMS = ["sensor", "binary_sensor", "device_tracker", "button"]

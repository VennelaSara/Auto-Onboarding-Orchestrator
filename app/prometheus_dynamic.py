import yaml
import requests
from pathlib import Path
from urllib.parse import urlparse

# ---------------- CONFIG ----------------
PROMETHEUS_CONFIG_PATH = Path("/etc/prometheus/prometheus.yml")  # Update this path if different
PROMETHEUS_RELOAD_URL = "http://localhost:9090/-/reload"

# ---------------- DYNAMIC SCRAPE ----------------
def add_prometheus_scrape_job(scrape_config: dict) -> bool:
    """
    Add a new scrape job to Prometheus dynamically and reload Prometheus.
    scrape_config: dict with keys: job_name, metrics_path, targets, auth_required
    """
    try:
        # Load existing config
        with open(PROMETHEUS_CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f) or {}

        if "scrape_configs" not in config:
            config["scrape_configs"] = []

        # Avoid duplicate jobs
        existing_jobs = [job["job_name"] for job in config["scrape_configs"]]
        if scrape_config["job_name"] in existing_jobs:
            print(f"⚠ Job {scrape_config['job_name']} already exists, skipping")
            return False

        # Prepare job entry
        job_entry = {
            "job_name": scrape_config["job_name"],
            "metrics_path": scrape_config.get("metrics_path", "/metrics"),
            "static_configs": [{"targets": scrape_config.get("targets", [])}],
        }

        # Add basic auth if needed
        if scrape_config.get("auth_required"):
            job_entry["basic_auth"] = {
                "username": "PROM_USER",  # replace with your username
                "password": "PROM_PASS"   # replace with your password
            }

        # Append job and save
        config["scrape_configs"].append(job_entry)
        with open(PROMETHEUS_CONFIG_PATH, "w") as f:
            yaml.safe_dump(config, f)

        # Reload Prometheus
        r = requests.post(PROMETHEUS_RELOAD_URL)
        if r.status_code == 200:
            print(f"✅ Prometheus reload successful for job: {scrape_config['job_name']}")
            return True
        else:
            print(f"❌ Failed to reload Prometheus, status_code: {r.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error in dynamic Prometheus config: {e}")
        return False


# ---------------- HELPER TO CONFIGURE SCRAPE ----------------
def configure_prometheus_scrape(url: str, auth=False) -> dict:
    """
    Generate Prometheus scrape config and add it dynamically.
    """
    hostname = urlparse(url).hostname
    scrape_config = {
        "job_name": f"auto_{hostname}",
        "metrics_path": "/metrics",
        "targets": [hostname],
        "auth_required": auth
    }
    print("🔹 Configuring Prometheus scrape:", scrape_config)

    # Add dynamically
    add_prometheus_scrape_job(scrape_config)
    return scrape_config

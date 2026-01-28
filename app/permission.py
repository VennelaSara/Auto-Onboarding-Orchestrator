import requests
import socket
from typing import Dict
from urllib.parse import urlparse
from app.prometheus_dynamic import configure_prometheus_scrape

PROM_TIMEOUT = 3
OTEL_TIMEOUT = 2
STATSD_PORT = 8125


# ---------- PROMETHEUS ----------

def check_prometheus_metrics(base_url: str, headers=None) -> bool:
    try:
        r = requests.get(
            f"{base_url}/metrics",
            headers=headers or {},
            timeout=PROM_TIMEOUT
        )
        return r.status_code == 200 and "HELP" in r.text
    except Exception:
        return False


def check_prometheus_auth(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/metrics", timeout=PROM_TIMEOUT)
        return r.status_code in [401, 403]
    except Exception:
        return False


# ---------- OPENTELEMETRY ----------

def check_otlp_http(base_url: str) -> bool:
    otlp_paths = ["/v1/traces", "/v1/metrics"]
    for path in otlp_paths:
        try:
            r = requests.post(f"{base_url}{path}", timeout=OTEL_TIMEOUT)
            if r.status_code in [200, 404, 415]:
                return True
        except Exception:
            continue
    return False


def check_otlp_grpc(host: str, port: int = 4317) -> bool:
    try:
        with socket.create_connection((host, port), timeout=OTEL_TIMEOUT):
            return True
    except Exception:
        return False


# ---------- STATSD ----------

def check_statsd(host: str, port: int = STATSD_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False


# ---------- CLOUD / K8S ----------

def detect_kubernetes_env(headers: Dict) -> bool:
    return "x-kubernetes" in str(headers).lower()


def detect_cloud_provider(headers: Dict) -> str | None:
    header_str = str(headers).lower()
    if "x-amzn" in header_str:
        return "aws"
    if "x-goog" in header_str:
        return "gcp"
    if "x-ms" in header_str:
        return "azure"
    return None


# ---------- BLACKBOX ----------

def check_blackbox_http(url: str) -> bool:
    try:
        r = requests.get(url, timeout=5)
        return r.status_code < 500
    except Exception:
        return False

#--------------Loki Check--------------
LOKI_TIMEOUT = 3

def check_loki_endpoint(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/loki/api/v1/labels", timeout=LOKI_TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False
    
#----------------Tempo Check--------------
def check_tempo_endpoint(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/tempo/api/traces", timeout=LOKI_TIMEOUT)
        return r.status_code in [200, 404]  # 404 OK if no traces yet
    except Exception:
        return False

# ---------- STRATEGY RESOLVER ----------

def detect_monitoring_strategy(app: Dict) -> Dict:
    base_url = app["url"]
    parsed = urlparse(base_url)
    host = parsed.hostname

    try:
        headers = requests.get(base_url, timeout=2).headers
    except Exception:
        headers = {}

    if check_prometheus_metrics(base_url):
        return {
            "monitorable": True,
            "strategy": "prometheus",
            "confidence": "high",
            "details": "/metrics endpoint detected"
        }

    if check_prometheus_auth(base_url):
        return {
            "monitorable": True,
            "strategy": "prometheus-auth",
            "confidence": "medium",
            "details": "/metrics exists but requires auth"
        }

    if check_otlp_http(base_url):
        return {
            "monitorable": True,
            "strategy": "opentelemetry-http",
            "confidence": "high",
            "details": "OTLP HTTP endpoint detected"
        }

    if check_otlp_grpc(host):
        return {
            "monitorable": True,
            "strategy": "opentelemetry-grpc",
            "confidence": "high",
            "details": "OTLP gRPC endpoint detected on port 4317"
        }

    if check_statsd(host):
        return {
            "monitorable": True,
            "strategy": "statsd",
            "confidence": "medium",
            "details": "StatsD-compatible agent detected"
        }

    if detect_kubernetes_env(headers):
        return {
            "monitorable": True,
            "strategy": "kubernetes-auto",
            "confidence": "medium",
            "details": "Kubernetes environment detected"
        }

    cloud = detect_cloud_provider(headers)
    if cloud:
        return {
            "monitorable": True,
            "strategy": f"{cloud}-cloud-metrics",
            "confidence": "low",
            "details": f"{cloud.upper()} headers detected"
        }

    if check_blackbox_http(base_url):
        return {
            "monitorable": True,
            "strategy": "blackbox-http",
            "confidence": "low",
            "details": "Only uptime / latency monitoring possible"
        }

    return {
        "monitorable": False,
        "strategy": None,
        "confidence": "none",
        "details": "No metrics or telemetry endpoints detected",
        "next_steps": [
            "Expose /metrics",
            "Enable OpenTelemetry SDK",
            "Deploy OpenTelemetry Collector",
            "Use blackbox exporter"
        ]
    }




# ---------- ACTIONS ----------

def apply_monitoring_strategy(app: dict, strategy_info: dict):
    strategy = strategy_info.get("strategy")
    base_url = app["url"]

    if strategy == "prometheus":
        return configure_prometheus_scrape(base_url)

    elif strategy == "prometheus-auth":
        return configure_prometheus_scrape(base_url, auth=True)

    elif strategy == "opentelemetry-http":
        return configure_otlp_pipeline(base_url, protocol="http")

    elif strategy == "opentelemetry-grpc":
        host = urlparse(base_url).hostname
        return configure_otlp_pipeline(host, protocol="grpc")

    elif strategy == "statsd":
        host = urlparse(base_url).hostname
        return configure_statsd_exporter(host)

    elif strategy == "kubernetes-auto":
        return configure_k8s_autodiscovery()

    elif strategy and strategy.endswith("cloud-metrics"):
        cloud_provider = strategy.split("-")[0]
        return configure_cloud_monitoring(cloud_provider)

    elif strategy == "blackbox-http":
        return configure_blackbox_exporter(base_url)
    elif strategy_info.get("logs_enabled"):
        loki_url = strategy_info.get("loki_url", "http://localhost:3100")
        tempo_url = strategy_info.get("tempo_url", "http://localhost:3200")

        loki_config = configure_loki_pipeline(app["name"], loki_url)
        tempo_config = configure_tempo_pipeline(app["name"], tempo_url)

        return {"loki": loki_config, "tempo": tempo_config}

    

    else:
        return {"status": "skipped", "reason": "No actionable strategy found"}
    
# def configure_prometheus_scrape(url: str, auth=False):
#     hostname = urlparse(url).hostname
#     scrape_config = {
#         "job_name": f"auto_{hostname}",
#         "metrics_path": "/metrics",
#         "targets": [hostname],
#         "auth_required": auth,
#         "metrics_to_collect": [
#             "http_requests_total",
#             "process_cpu_seconds_total",
#             "process_resident_memory_bytes",
#             "go_gc_duration_seconds",       # if Go app
#             "python_gc_objects_collected_total"  # if Python app
#         ]
#     }
#     print("✅ Prometheus scrape configured:", scrape_config)
#     return scrape_config

def configure_otlp_pipeline(endpoint: str, protocol="http"):
    monitored_metrics = [
        "trace_duration_seconds",
        "span_errors_total",
        "http_client_duration_seconds",
        "http_server_requests_total",
        "process_cpu_usage",
        "process_memory_rss",
        "custom_app_metrics"  # placeholder for app-specific OTEL metrics
    ]
    pipeline_config = {
        "protocol": protocol,
        "endpoint": endpoint,
        "metrics": monitored_metrics
    }
    print(f"✅ OTEL pipeline configured for {protocol} at {endpoint}:", pipeline_config)
    return pipeline_config

def configure_statsd_exporter(host: str, port: int = 8125):
    monitored_metrics = [
        "requests.count",
        "requests.duration",
        "memory.usage",
        "cpu.usage",
        "queue.size"
    ]
    config = {
        "host": host,
        "port": port,
        "metrics": monitored_metrics
    }
    print(f"✅ StatsD exporter configured for {host}:{port}:", config)
    return config

def configure_blackbox_exporter(url: str):
    monitored_metrics = [
        "probe_success",
        "probe_duration_seconds",
        "http_status_code",
        "dns_lookup_duration_seconds",
        "tcp_connection_duration_seconds"
    ]
    config = {
        "url": url,
        "metrics": monitored_metrics
    }
    print(f"✅ Blackbox exporter configured for {url}:", config)
    return config

def configure_k8s_autodiscovery():
    monitored_metrics = [
        "kube_pod_info",
        "kube_pod_status_phase",
        "kube_deployment_status_replicas",
        "container_cpu_usage_seconds_total",
        "container_memory_usage_bytes",
        "kube_node_status_condition"
    ]
    config = {"strategy": "k8s-autodiscovery", "metrics": monitored_metrics}
    print("✅ Kubernetes autodiscovery enabled:", config)
    return config

def configure_cloud_monitoring(provider: str):
    if provider == "aws":
        monitored_metrics = ["EC2_CPUUtilization", "EC2_MemoryUtilization", "ELB_RequestCount", "RDS_CPUUtilization"]
    elif provider == "gcp":
        monitored_metrics = ["compute.googleapis.com/instance/cpu/utilization", "compute.googleapis.com/instance/disk/write_bytes_count"]
    elif provider == "azure":
        monitored_metrics = ["Percentage CPU", "Network In Total", "Disk Read Bytes/Sec"]
    else:
        monitored_metrics = []

    config = {"cloud_provider": provider, "metrics": monitored_metrics}
    print(f"✅ Cloud monitoring setup for {provider.upper()}:", config)
    return config


def configure_loki_pipeline(app_name: str, loki_url: str):
    config = {
        "app": app_name,
        "loki_endpoint": loki_url,
        "log_streams": ["app_logs", "error_logs"],
        "labels": {"app": app_name}
    }
    print(f"✅ Loki pipeline configured for {app_name}:", config)
    return config

def configure_tempo_pipeline(app_name: str, tempo_url: str):
    config = {
        "app": app_name,
        "tempo_endpoint": tempo_url,
        "trace_ids": [],
        "sample_rate": 1.0
    }
    print(f"✅ Tempo pipeline configured for {app_name}:", config)
    return config

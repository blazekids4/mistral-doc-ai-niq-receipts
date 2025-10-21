import os
import sys
import time
import csv
import json
import random
import datetime
import argparse
import statistics
import signal
import requests
from dotenv import load_dotenv

# Async HTTP support (optional)
try:
    import asyncio
    import aiohttp
    AIOHTTP_AVAILABLE = True
except Exception:
    AIOHTTP_AVAILABLE = False

# Telemetry SDK availability flags will be detected at runtime
try:
    # OpenTelemetry + Azure Monitor exporter (preferred per Azure best practices)
    from opentelemetry import metrics as otel_metrics
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter
    OTEL_AZURE_AVAILABLE = True
except Exception:
    OTEL_AZURE_AVAILABLE = False

try:
    # Fallback to legacy Application Insights SDK if OpenTelemetry exporter not present
    from applicationinsights import TelemetryClient
    AIP_AVAILABLE = True
except Exception:
    AIP_AVAILABLE = False


def load_config():
    load_dotenv()
    api_key = os.environ.get('AZURE_API_KEY')
    ai_conn_str = os.environ.get('APPLICATION_INSIGHTS_CONNECTION_STRING')
    # Always use the working Mistral OCR endpoint (not PROJECT_ENDPOINT from .env which is different)
    # This is the same endpoint that works in process_documents.py
    endpoint = "https://foundry-eastus2-niq.services.ai.azure.com/providers/mistral/azure/ocr"
    return api_key, endpoint, ai_conn_str


def send_telemetry(tc, metrics):
    """
    Send telemetry using either TelemetryClient (legacy) or OpenTelemetry (preferred).

    In this function `tc` may be:
      - an OpenTelemetry telemetry dict (preferred), or
      - an applicationinsights.TelemetryClient instance (fallback), or
      - None (telemetry disabled)

    For production and Azure-hosted scenarios, prefer OpenTelemetry + Azure Monitor exporter
    to follow Azure best practices: https://learn.microsoft.com/azure/azure-monitor/opentelemetry
    """
    if tc is None:
        return

    try:
        if OTEL_AZURE_AVAILABLE and isinstance(tc, dict) and tc.get('otel_meter'):
            # For OpenTelemetry we use a proper histogram counter instead of an observable gauge
            lat_val = metrics.get('latency_ms', 0)
            histogram = tc.get('histogram')
            if histogram:
                # Use the histogram counter directly with the record() method
                histogram.record(lat_val)
        elif AIP_AVAILABLE and hasattr(tc, 'track_metric'):
            tc.track_metric('mistral_latency_ms', metrics.get('latency_ms', 0))
            tc.track_event('mistral_call', properties={
                'status_code': str(metrics.get('status_code')),
                'success': str(metrics.get('success')),
                'error': metrics.get('error', '')
            })
            tc.flush()
        else:
            # Telemetry not configured - skip
            pass
    except Exception as e:
        print(f"Failed to send telemetry: {e}")


def make_request(api_key, endpoint, base64_image, content_type="image/jpeg", timeout=30):
    url = endpoint
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    payload = {
        "model": "mistral-document-ai-2505",
        "document": {
            "type": "image_url",
            "image_url": f"data:{content_type};base64,{base64_image}"
        },
        "include_image_base64": False
    }

    start = time.perf_counter()
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        latency = (time.perf_counter() - start) * 1000.0
        return resp.status_code, resp.text, latency
    except requests.exceptions.RequestException as e:
        latency = (time.perf_counter() - start) * 1000.0
        return None, str(e), latency


def compute_summary(latencies):
    """Compute latency summary statistics from a list of latency values in ms."""
    if not latencies:
        return {}
    lat_sorted = sorted(latencies)
    n = len(lat_sorted)
    def pct(p):
        if n == 0:
            return None
        k = max(0, min(n - 1, int(round((p / 100.0) * (n - 1)))))
        return round(lat_sorted[k], 2)

    summary = {
        'count': n,
        'min_ms': round(lat_sorted[0], 2),
        'max_ms': round(lat_sorted[-1], 2),
        'mean_ms': round(statistics.mean(lat_sorted), 2),
        'median_ms': round(statistics.median(lat_sorted), 2),
        'p50_ms': pct(50),
        'p90_ms': pct(90),
        'p95_ms': pct(95),
        'p99_ms': pct(99),
        'stdev_ms': round(statistics.stdev(lat_sorted), 2) if n > 1 else 0.0
    }
    return summary


def init_telemetry(ai_conn_str):
    """Initialize telemetry client. Prefer OpenTelemetry + Azure Monitor exporter.

    Returns an object to pass to send_telemetry().
    """
    if OTEL_AZURE_AVAILABLE and ai_conn_str:
        try:
            resource = Resource.create({"service.name": "mistral-load-test"})
            exporter = AzureMonitorMetricExporter.from_connection_string(ai_conn_str)
            reader = PeriodicExportingMetricReader(exporter)
            provider = MeterProvider(resource=resource, metric_readers=[reader])
            otel_metrics.set_meter_provider(provider)
            meter = otel_metrics.get_meter(__name__)
            # Use a histogram for latency metrics (allows recording individual values)
            histogram = meter.create_histogram("mistral_latency_ms", description="Mistral API latency in milliseconds")
            return {'otel_meter': meter, 'histogram': histogram}
        except Exception as e:
            print(f"Failed to initialize OpenTelemetry Azure exporter: {e}")

    if AIP_AVAILABLE and ai_conn_str:
        try:
            tc = TelemetryClient(ai_conn_str)
            return tc
        except Exception as e:
            print(f"Failed to init Application Insights client: {e}")

    print("Telemetry not configured or SDKs not available; proceeding without telemetry.")
    return None


def run_load_test(iterations=50, base_delay=(0.5, 1.5), max_retries=3, jitter=True, use_real_blobs=False, csv_path=None):
    api_key, endpoint, ai_conn_str = load_config()
    if not api_key:
        print("AZURE_API_KEY not set in .env")
        return

    telemetry_client = init_telemetry(ai_conn_str)

    # Prepare data directory and CSV path
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    csv_dir = os.path.join('..', 'data', 'responses')
    os.makedirs(csv_dir, exist_ok=True)
    if csv_path is None:
        csv_path = os.path.join(csv_dir, f'load_test_{timestamp}.csv')
    summary_path = os.path.join(csv_dir, f'load_test_summary_{timestamp}.json')

    # If using real blobs, import storage_utils and get blob names
    blob_names = []
    if use_real_blobs:
        try:
            # storage_utils is in the same directory, so import directly
            from storage_utils import get_all_blobs_with_prefix, get_blob_base64
            blob_names = get_all_blobs_with_prefix()
            if not blob_names:
                print("No blobs found with configured prefix; falling back to sample image")
                use_real_blobs = False
        except Exception as e:
            print(f"Failed to load storage_utils or fetch blobs: {e}\nFalling back to sample image.")
            use_real_blobs = False

    # Sample small PNG if not using real blobs
    sample_base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII="
    content_type = "image/png"

    latencies = []
    records = []

    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['iteration', 'attempt', 'timestamp', 'status_code', 'latency_ms', 'success', 'error', 'blob_name'])
        writer.writeheader()

        for i in range(1, iterations + 1):
            attempt = 0
            success = False
            status_code = None
            latency_ms = None
            blob_name = ''

            # Choose blob if using real blobs
            if use_real_blobs and blob_names:
                blob_name = random.choice(blob_names)
                try:
                    base64_image = get_blob_base64(blob_name)
                except Exception as e:
                    print(f"Failed to download blob {blob_name}: {e}")
                    base64_image = sample_base64
            else:
                base64_image = sample_base64

            # Randomized pacing to avoid bursty traffic
            delay = random.uniform(*base_delay) if isinstance(base_delay, tuple) else base_delay
            if jitter:
                delay = delay * random.uniform(0.7, 1.3)
            time.sleep(delay)

            while attempt <= max_retries and not success:
                attempt += 1
                ts = datetime.datetime.now(datetime.UTC).isoformat() 
                status_code, resp_text, latency_ms = make_request(api_key, endpoint, base64_image, content_type)

                entry = {
                    'iteration': i,
                    'attempt': attempt,
                    'timestamp': ts,
                    'status_code': status_code if status_code is not None else 'ERROR',
                    'latency_ms': round(latency_ms, 2) if latency_ms is not None else None,
                    'success': False,
                    'error': '',
                    'blob_name': blob_name
                }

                # Network/request errors
                if status_code is None:
                    entry['error'] = resp_text
                    writer.writerow(entry)
                    print(f"Iter {i} attempt {attempt} - request error: {resp_text} (latency {entry['latency_ms']} ms)")
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue

                if status_code == 429:
                    entry['error'] = '429 Too Many Requests'
                    writer.writerow(entry)
                    print(f"Iter {i} attempt {attempt} - 429 received, backing off (latency {entry['latency_ms']} ms)")
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue

                if 200 <= status_code < 300:
                    entry['success'] = True
                    writer.writerow(entry)
                    latencies.append(entry['latency_ms'])
                    records.append(entry)
                    send_telemetry(telemetry_client, {'latency_ms': entry['latency_ms'], 'status_code': status_code, 'success': True})
                    print(f"Iter {i} attempt {attempt} - success {status_code} (latency {entry['latency_ms']} ms)")
                    success = True
                    break

                # Other HTTP errors
                entry['error'] = resp_text
                writer.writerow(entry)
                records.append(entry)
                send_telemetry(telemetry_client, {'latency_ms': entry['latency_ms'], 'status_code': status_code, 'success': False, 'error': resp_text})
                print(f"Iter {i} attempt {attempt} - HTTP {status_code} (latency {entry['latency_ms']} ms) error: {resp_text}")

                if 500 <= status_code < 600:
                    backoff = 2 ** attempt
                    time.sleep(backoff)
                    continue
                else:
                    break

    # Compute and save summary
    summary = compute_summary([v for v in latencies if v is not None])
    summary['total_iterations'] = iterations
    summary['successful_calls'] = len([r for r in records if r.get('success')])
    summary['failed_calls'] = iterations - summary['successful_calls']
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    print(f"Load test complete. Metrics saved to {csv_path} and summary to {summary_path}")


if __name__ == '__main__':
    # Set up graceful keyboard interrupt handling
    def signal_handler(sig, frame):
        print("\nLoad test interrupted. Saving partial results...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description='Mistral API load test')
    parser.add_argument('--iterations', type=int, default=50)
    parser.add_argument('--use-real-blobs', action='store_true')
    parser.add_argument('--async', dest='use_async', action='store_true', help='Run using aiohttp async runner')
    parser.add_argument('--concurrency', type=int, default=5, help='Max concurrent async requests')
    parser.add_argument('--csv-path', type=str, default=None, help='Custom CSV output path')
    args = parser.parse_args()

    if args.use_async:
        if not AIOHTTP_AVAILABLE:
            print('aiohttp not installed; falling back to sync runner')
            run_load_test(iterations=args.iterations, use_real_blobs=args.use_real_blobs, csv_path=args.csv_path)
        else:
            # Async runner implementation
            async def async_make_request(session, api_key, endpoint, base64_image, content_type='image/jpeg', timeout=30):
                url = endpoint
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {api_key}'
                }
                payload = {
                    'model': 'mistral-document-ai-2505',
                    'document': {'type': 'image_url', 'image_url': f'data:{content_type};base64,{base64_image}'},
                    'include_image_base64': False
                }
                start = time.perf_counter()
                try:
                    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                        text = await resp.text()
                        latency = (time.perf_counter() - start) * 1000.0
                        return resp.status, text, latency
                except Exception as e:
                    latency = (time.perf_counter() - start) * 1000.0
                    return None, str(e), latency

            async def async_runner():
                api_key, endpoint, ai_conn_str = load_config()
                if not api_key:
                    print('AZURE_API_KEY not set in .env')
                    return

                telemetry_client = init_telemetry(ai_conn_str)

                # Prepare dirs
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                csv_dir = os.path.join('..', 'data', 'responses')
                os.makedirs(csv_dir, exist_ok=True)
                csv_path_local = args.csv_path or os.path.join(csv_dir, f'load_test_{timestamp}.csv')
                summary_path_local = os.path.join(csv_dir, f'load_test_summary_{timestamp}.json')

                # Optionally get blobs
                blob_names_local = []
                if args.use_real_blobs:
                    try:
                        from storage_utils import get_all_blobs_with_prefix, get_blob_base64
                        blob_names_local = get_all_blobs_with_prefix()
                        if not blob_names_local:
                            print('No blobs found; falling back to sample')
                    except Exception as e:
                        print(f'Failed to get blobs: {e}')

                sample_base64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAASsJTYQAAAAASUVORK5CYII='
                content_type_local = 'image/png'

                sem = asyncio.Semaphore(args.concurrency)
                latencies_local = []
                records_local = []

                async with aiohttp.ClientSession() as session:
                    async def worker(iteration):
                        attempt = 0
                        success = False
                        blob_name_local = ''
                        if args.use_real_blobs and blob_names_local:
                            blob_name_local = random.choice(blob_names_local)
                            try:
                                base64_image_local = get_blob_base64(blob_name_local)
                            except Exception:
                                base64_image_local = sample_base64
                        else:
                            base64_image_local = sample_base64

                        # pacing
                        delay = random.uniform(0.5, 1.5)
                        await asyncio.sleep(delay * random.uniform(0.7, 1.3))

                        nonlocal latencies_local, records_local
                        while attempt <= args.iterations and not success:
                            attempt += 1
                            async with sem:
                                status_code, resp_text, latency_ms = await async_make_request(session, api_key, endpoint, base64_image_local, content_type_local)
                            ts = datetime.datetime.now(datetime.UTC).isoformat()
                            entry = {
                                'iteration': iteration,
                                'attempt': attempt,
                                'timestamp': ts,
                                'status_code': status_code if status_code is not None else 'ERROR',
                                'latency_ms': round(latency_ms, 2) if latency_ms is not None else None,
                                'success': False,
                                'error': '',
                                'blob_name': blob_name_local
                            }
                            if status_code is None:
                                entry['error'] = resp_text
                                records_local.append(entry)
                                await asyncio.sleep(2 ** attempt)
                                continue
                            if status_code == 429:
                                entry['error'] = '429 Too Many Requests'
                                records_local.append(entry)
                                await asyncio.sleep(2 ** attempt)
                                continue
                            if 200 <= status_code < 300:
                                entry['success'] = True
                                latencies_local.append(entry['latency_ms'])
                                records_local.append(entry)
                                send_telemetry(telemetry_client, {'latency_ms': entry['latency_ms'], 'status_code': status_code, 'success': True})
                                success = True
                                break
                            entry['error'] = resp_text
                            records_local.append(entry)
                            send_telemetry(telemetry_client, {'latency_ms': entry['latency_ms'], 'status_code': status_code, 'success': False, 'error': resp_text})
                            if 500 <= status_code < 600:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            else:
                                break

                    # create tasks limited by concurrency
                    tasks = [asyncio.create_task(worker(i)) for i in range(1, args.iterations + 1)]
                    await asyncio.gather(*tasks)

                # Write CSV and summary after run
                with open(csv_path_local, 'w', newline='', encoding='utf-8') as csvfile2:
                    writer2 = csv.DictWriter(csvfile2, fieldnames=['iteration', 'attempt', 'timestamp', 'status_code', 'latency_ms', 'success', 'error', 'blob_name'])
                    writer2.writeheader()
                    for r in records_local:
                        writer2.writerow(r)

                summary_local = compute_summary([v for v in latencies_local if v is not None])
                summary_local['total_iterations'] = args.iterations
                summary_local['successful_calls'] = len([r for r in records_local if r.get('success')])
                summary_local['failed_calls'] = args.iterations - summary_local['successful_calls']
                with open(summary_path_local, 'w', encoding='utf-8') as f:
                    json.dump(summary_local, f, indent=2)

                print(f'Async load test complete. CSV: {csv_path_local}, summary: {summary_path_local}')

            asyncio.run(async_runner())
    else:
        run_load_test(iterations=args.iterations, use_real_blobs=args.use_real_blobs, csv_path=args.csv_path)

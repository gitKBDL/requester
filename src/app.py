import argparse
import logging
import time
import concurrent.futures
from pathlib import Path
from typing import Iterable
import requests
from rich.console import Console
from rich.table import Table

import config

from .utils import ResponseSink, setup_logging
from .models import parse_raw_request
from .placeholders import PlaceholderResolver
from .proxies import load_proxies, check_proxies, ProxyPool, ProxyExhausted
from .network import send_with_proxy_failover
from .metrics import Metrics

def iter_request_files() -> Iterable[Path]:
    folder = Path(config.REQUESTS_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    for path in sorted(folder.glob("*.txt")):
        # Ignore example files unless the user renames them.
        if path.name.lower().startswith("example"):
            continue
        yield path

def warn_no_proxies(delay: bool, source: Path, direct_flag: bool) -> None:
    banner = "\n".join(
        [
            "=" * 70,
            "  NO PROXIES FOUND — RUNNING DIRECT",
            f"  File: {source}",
            "  Add proxies or use --direct to skip the startup delay.",
            "=" * 70,
        ]
    )
    logging.warning(banner)
    if delay:
        logging.warning("Starting in 10 seconds because proxies are missing...")
        time.sleep(10)
    elif direct_flag:
        logging.warning("--direct flag: running direct with no delay.")

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Ignore proxies.txt and send directly.",
    )
    parser.add_argument(
        "--proxy-file",
        default=config.PROXIES_FILE,
        type=Path,
        help="Path to proxy list file (default: config.PROXIES_FILE).",
    )
    parser.add_argument(
        "--response",
        nargs="?",
        const=True,
        metavar="FILE",
        help="Dump responses. Without FILE -> print to console. With FILE -> append to responses/FILE (or abs path).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check all proxies in parallel and exit.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Number of parallel workers for sending requests (default: 10).",
    )
    return parser.parse_args()

def process_single_request(
    path: Path,
    resolver: PlaceholderResolver,
    session: requests.Session,
    pool: ProxyPool,
    response_sink: ResponseSink,
    metrics: Metrics
) -> None:
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw_text = resolver.replace(raw_text)
        parsed = parse_raw_request(raw_text)
        
        response = send_with_proxy_failover(parsed, session, pool)
        metrics.record_response(response.status_code)
        
        if response_sink.enabled():
            response_sink.write(response)
            
        # Handle meta options
        if "delay" in parsed.meta:
            try:
                delay = float(parsed.meta["delay"])
                if delay > 0:
                    logging.info("Meta: sleeping for %ss", delay)
                    time.sleep(delay)
            except ValueError:
                logging.warning("Invalid delay value in meta: %s", parsed.meta["delay"])

    except Exception as exc:
        metrics.record_error()
        logging.error("Failed to send %s: %s", path.name, exc)

def print_summary(metrics: Metrics) -> None:
    console = Console()
    stats = metrics.stats
    
    table = Table(title="Session Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")

    table.add_row("Total Requests", str(stats.total))
    table.add_row("Success (2xx/3xx)", f"[green]{stats.success}[/green]")
    table.add_row("Failed (4xx/5xx)", f"[red]{stats.failed}[/red]")
    
    console.print("\n")
    console.print(table)
    
    # Top status codes
    if stats.codes:
        code_table = Table(title="Status Codes", show_header=True)
        code_table.add_column("Code")
        code_table.add_column("Count", justify="right")
        
        for code, count in sorted(stats.codes.items(), key=lambda x: x[1], reverse=True):
            color = "green" if 200 <= code < 400 else "red"
            code_label = str(code) if code != -1 else "Network Error"
            code_table.add_row(f"[{color}]{code_label}[/{color}]", str(count))
            
        console.print(code_table)

def run_loop(args: argparse.Namespace) -> None:
    session = requests.Session()
    metrics = Metrics()

    proxies = [] if args.direct else load_proxies(Path(args.proxy_file))
    if args.direct and proxies:
        logging.info(
            "--direct enabled: ignoring %s proxies from %s",
            len(proxies),
            args.proxy_file,
        )
        proxies = []

    pool = ProxyPool(
        proxies,
        ignore_proxies=args.direct,
        file_path=None if args.direct else Path(args.proxy_file),
    )
    if pool.has_proxies():
        logging.info("Loaded proxies: %s (from %s)", len(proxies), args.proxy_file)
    else:
        warn_no_proxies(delay=not args.direct, source=Path(args.proxy_file), direct_flag=args.direct)

    logging.info("Starting sender. Reading from %s", config.REQUESTS_DIR)
    logging.info("Parallel workers: %s", args.workers)

    resolver = PlaceholderResolver(
        folder=Path(config.PLACEHOLDERS_DIR),
        rotation=config.PLACEHOLDER_ROTATION,
    )
    response_sink = ResponseSink(args.response)
    if response_sink.enabled():
        mode = "console" if response_sink.mode == "console" else f"file={response_sink.path}"
        logging.info("Response dump enabled (%s)", mode)

    try:
        while True:
            files = list(iter_request_files())
            if not files:
                logging.warning("No *.txt request files found in %s, stopping.", config.REQUESTS_DIR)
                break

            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = [
                    executor.submit(process_single_request, path, resolver, session, pool, response_sink, metrics)
                    for path in files
                ]
                concurrent.futures.wait(futures)

            time.sleep(config.INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logging.info("Interrupted with Ctrl+C, exiting cleanly.")
    except ProxyExhausted as exc:
        logging.error("%s. Terminating.", exc)
    finally:
        session.close()
        print_summary(metrics)
def main() -> None:
    setup_logging()
    args = parse_args()
    if args.check:
        if args.direct:
            logging.warning("--check with --direct: nothing to test (no proxies).")
            return
        proxies = load_proxies(Path(args.proxy_file))
        check_proxies(proxies, dest_file=Path(args.proxy_file))
        return
    run_loop(args)

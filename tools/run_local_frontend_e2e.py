#!/usr/bin/env python3
"""Run a local browser smoke test against the PantryBuddy frontend."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import urlopen

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - handled at runtime
    sync_playwright = None
    PlaywrightTimeoutError = Exception


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = PROJECT_ROOT / "frontend"
BACKEND_DIR = PROJECT_ROOT / "backend"
DEFAULT_FRONTEND_PORT = 8080
DEFAULT_ADAPTER_PORT = 8000
DEFAULT_ARTIFACTS_ROOT = PROJECT_ROOT / "test-results" / "local-e2e"
MAC_BROWSER_PATHS = {
    "chromium": [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    ],
    "firefox": [
        Path("/Applications/Firefox.app/Contents/MacOS/firefox"),
    ],
    "webkit": [
        Path("/Applications/Safari.app/Contents/MacOS/Safari"),
    ],
}


@dataclass
class ManagedProcess:
    name: str
    process: subprocess.Popen

    def stop(self) -> None:
        if self.process.poll() is not None:
            return
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Launch or reuse local PantryBuddy servers, then run a browser smoke test "
            "that generates a meal plan and verifies source attribution is visible."
        )
    )
    parser.add_argument(
        "--frontend-url",
        help="Existing frontend URL to reuse, e.g. http://127.0.0.1:8080/.",
    )
    parser.add_argument(
        "--api-base-url",
        help="Existing local API base URL to reuse, e.g. http://127.0.0.1:8000.",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=DEFAULT_FRONTEND_PORT,
        help=f"Frontend port when starting a local static server (default: {DEFAULT_FRONTEND_PORT}).",
    )
    parser.add_argument(
        "--adapter-port",
        type=int,
        default=DEFAULT_ADAPTER_PORT,
        help=f"Adapter port when starting the local backend (default: {DEFAULT_ADAPTER_PORT}).",
    )
    parser.add_argument(
        "--reuse-existing-only",
        action="store_true",
        help="Fail instead of starting missing local servers.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run the browser with a visible window instead of headless mode.",
    )
    parser.add_argument(
        "--slow-mo-ms",
        type=int,
        default=0,
        help="Delay each browser action by this many milliseconds. Defaults to 800 in headed mode.",
    )
    parser.add_argument(
        "--hold-open-seconds",
        type=float,
        default=2.0,
        help="Keep the browser open briefly after a headed run so the final state is visible.",
    )
    parser.add_argument(
        "--browser",
        default="chromium",
        choices=("chromium", "firefox", "webkit"),
        help="Playwright browser engine to use.",
    )
    parser.add_argument(
        "--artifacts-dir",
        help=(
            "Directory to write trace/video/screenshots. Defaults to "
            "test-results/local-e2e/<timestamp>."
        ),
    )
    return parser.parse_args()


def build_frontend_url(base_url: str, api_base_url: str) -> str:
    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["apiBaseUrl"] = api_base_url
    return urlunparse(parsed._replace(query=urlencode(query)))


def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def wait_for_http(url: str, timeout_seconds: float = 20.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return
        except HTTPError as exc:
            if 200 <= exc.code < 500:
                return
            last_error = exc
        except URLError as exc:
            last_error = exc
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(0.4)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def start_frontend_server(port: int) -> ManagedProcess:
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "http.server", str(port)],
        cwd=str(FRONTEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ManagedProcess(name="frontend", process=process)


def start_local_adapter(port: int) -> ManagedProcess:
    env = os.environ.copy()
    env.update(
        {
            "RECIPE_DATA_SOURCE": "local",
            "RECIPE_COMPATIBILITY_MODE": "canonical",
            "LOCAL_ADAPTER_PORT": str(port),
        }
    )
    process = subprocess.Popen(  # noqa: S603
        [sys.executable, "local_adapter.py"],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return ManagedProcess(name="adapter", process=process)


def build_artifacts_dir(custom_dir: Optional[str]) -> Path:
    if custom_dir:
        artifacts_dir = Path(custom_dir).expanduser()
        if not artifacts_dir.is_absolute():
            artifacts_dir = PROJECT_ROOT / artifacts_dir
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        return artifacts_dir

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifacts_dir = DEFAULT_ARTIFACTS_ROOT / timestamp
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def screenshot_step(page, screenshots_dir: Path, step_name: str) -> str:
    output_path = screenshots_dir / f"{step_name}.png"
    page.screenshot(path=str(output_path))
    return str(output_path)


def ensure_frontend(base_url: Optional[str], port: int, reuse_only: bool) -> tuple[str, Optional[ManagedProcess]]:
    if base_url:
        wait_for_http(base_url)
        return base_url, None

    default_url = f"http://127.0.0.1:{port}/"
    if is_port_open("127.0.0.1", port):
        wait_for_http(default_url)
        return default_url, None

    if reuse_only:
        raise RuntimeError(f"No frontend server is running on {default_url}.")

    process = start_frontend_server(port)
    wait_for_http(default_url)
    return default_url, process


def ensure_adapter(base_url: Optional[str], port: int, reuse_only: bool) -> tuple[str, Optional[ManagedProcess]]:
    if base_url:
        health_url = f"{base_url.rstrip('/')}/v2/generate-meal-plan"
        wait_for_http(health_url)
        return base_url.rstrip("/"), None

    default_url = f"http://127.0.0.1:{port}"
    health_url = f"{default_url}/v2/generate-meal-plan"
    if is_port_open("127.0.0.1", port):
        wait_for_http(health_url)
        return default_url, None

    if reuse_only:
        raise RuntimeError(f"No local adapter is running on {default_url}.")

    process = start_local_adapter(port)
    wait_for_http(health_url)
    return default_url, process


def run_browser_check(
    frontend_url: str,
    browser_name: str,
    headed: bool,
    slow_mo_ms: int,
    hold_open_seconds: float,
    artifacts_dir: Path,
) -> dict[str, object]:
    if sync_playwright is None:
        raise RuntimeError(
            "Playwright is not installed. Run `python3 -m pip install -r requirements-dev.txt` "
            "and `python3 -m playwright install chromium` first."
        )

    with sync_playwright() as playwright:
        browser_launcher = getattr(playwright, browser_name)
        launch_options = {"headless": not headed}
        effective_slow_mo = slow_mo_ms or (800 if headed else 0)
        if effective_slow_mo > 0:
            launch_options["slow_mo"] = effective_slow_mo
        browser_executable = detect_browser_executable(browser_name)
        if browser_executable is not None:
            launch_options["executable_path"] = str(browser_executable)

        browser = browser_launcher.launch(**launch_options)
        videos_dir = artifacts_dir / "videos"
        screenshots_dir = artifacts_dir / "screenshots"
        videos_dir.mkdir(parents=True, exist_ok=True)
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        trace_path = artifacts_dir / "trace.zip"
        context = browser.new_context(record_video_dir=str(videos_dir))
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        screenshot_paths: list[str] = []
        result: dict[str, object] | None = None
        try:
            page.goto(frontend_url, wait_until="networkidle")
            screenshot_paths.append(
                screenshot_step(page, screenshots_dir, "01_loaded_frontend")
            )
            page.get_by_role("button", name="Generate Meal Plan").click()
            page.locator(".recipe-trigger").first.wait_for(timeout=15000)
            page.locator(".recipe-source-link").wait_for(timeout=15000)
            screenshot_paths.append(
                screenshot_step(page, screenshots_dir, "02_generated_meal_plan")
            )

            first_title = (page.locator(".recipe-panel-title").text_content() or "").strip()
            first_source = (
                page.locator(".recipe-meta-item").nth(3).locator(".recipe-meta-value").text_content() or ""
            ).strip()
            first_link = page.locator(".recipe-source-link").get_attribute("href") or ""
            screenshot_paths.append(
                screenshot_step(page, screenshots_dir, "03_first_selected_recipe")
            )

            chosen_index = None
            chosen_title = first_title
            recipe_trigger_count = page.locator(".recipe-trigger").count()
            for index in range(1, recipe_trigger_count):
                trigger = page.locator(".recipe-trigger").nth(index)
                trigger_title = (trigger.text_content() or "").strip()
                if trigger_title and trigger_title != first_title:
                    trigger.click()
                    page.wait_for_timeout(250)
                    chosen_index = index
                    chosen_title = trigger_title
                    break

            if chosen_index is None:
                raise RuntimeError("Could not find a second recipe card to verify panel updates.")

            try:
                page.wait_for_function(
                    "(expected) => { const el = document.querySelector('.recipe-panel-title'); return el && el.textContent.trim() === expected; }",
                    arg=chosen_title,
                    timeout=5000,
                )
            except PlaywrightTimeoutError as exc:
                raise RuntimeError("Recipe panel did not update after selecting a different meal.") from exc

            second_title = (page.locator(".recipe-panel-title").text_content() or "").strip()
            second_source = (
                page.locator(".recipe-meta-item").nth(3).locator(".recipe-meta-value").text_content() or ""
            ).strip()
            second_link = page.locator(".recipe-source-link").get_attribute("href") or ""
            screenshot_paths.append(
                screenshot_step(page, screenshots_dir, "04_second_selected_recipe")
            )

            if not first_source or not first_link:
                raise RuntimeError("Initial selected recipe did not render source attribution.")
            if not second_source or not second_link:
                raise RuntimeError("Second selected recipe did not render source attribution.")

            if headed and hold_open_seconds > 0:
                page.wait_for_timeout(int(hold_open_seconds * 1000))

            result = {
                "firstTitle": first_title,
                "firstSource": first_source,
                "firstLink": first_link,
                "secondTitle": second_title,
                "secondSource": second_source,
                "secondLink": second_link,
                "artifactsDir": str(artifacts_dir),
                "traceZip": str(trace_path),
                "videoPath": "",
                "screenshots": screenshot_paths,
            }
        finally:
            context.tracing.stop(path=str(trace_path))
            context.close()
            if result is not None and page.video is not None:
                result["videoPath"] = page.video.path()
            browser.close()

        if result is None:
            raise RuntimeError("Browser smoke test did not produce a result.")

        return result


def detect_browser_executable(browser_name: str) -> Optional[Path]:
    for path in MAC_BROWSER_PATHS.get(browser_name, []):
        if path.exists():
            return path
    return None


def main() -> int:
    args = parse_args()
    managed_processes: list[ManagedProcess] = []
    artifacts_dir = build_artifacts_dir(args.artifacts_dir)

    try:
        api_base_url, adapter_process = ensure_adapter(
            args.api_base_url,
            args.adapter_port,
            args.reuse_existing_only,
        )
        if adapter_process is not None:
            managed_processes.append(adapter_process)

        frontend_base_url, frontend_process = ensure_frontend(
            args.frontend_url,
            args.frontend_port,
            args.reuse_existing_only,
        )
        if frontend_process is not None:
            managed_processes.append(frontend_process)

        frontend_url = build_frontend_url(frontend_base_url, api_base_url)
        result = run_browser_check(
            frontend_url,
            args.browser,
            args.headed,
            args.slow_mo_ms,
            args.hold_open_seconds,
            artifacts_dir,
        )
        print(json.dumps({"frontendUrl": frontend_url, **result}, indent=2))
        return 0
    finally:
        for process in reversed(managed_processes):
            process.stop()


if __name__ == "__main__":
    raise SystemExit(main())

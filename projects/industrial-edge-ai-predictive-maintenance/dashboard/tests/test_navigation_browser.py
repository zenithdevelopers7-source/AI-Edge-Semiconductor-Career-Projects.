"""Real-browser acceptance for all 18 EDGEOPS navigation sections.

Runs against a disposable, isolated local FastAPI instance with a synthetic
account and database. Never touches the operator's .local/dashboard.sqlite3.

Install: python -m pip install -r requirements.txt playwright
         python -m playwright install chromium
Run:     python -m unittest discover -s tests -p test_navigation_browser.py -v
"""
from __future__ import annotations

import os
import json
import secrets
import sqlite3
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

ROOT = Path(__file__).resolve().parents[1]
STAGES = (
    "overview", "assets", "telemetry", "architecture", "insights", "hardware",
    "alerts", "maintenance", "security", "governance", "reports", "settings",
    "devices", "models", "knowledge", "simulation", "profiles", "readiness",
)


@unittest.skipIf(sync_playwright is None, "Install playwright and chromium for browser acceptance")
class NavigationBrowserAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="edgeops-navigation-")
        cls.email = "navigation-tester@example.invalid"
        cls.password = secrets.token_urlsafe(28)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        env = os.environ.copy()
        env["EDGEOPS_DASHBOARD_DB"] = str(Path(cls.temp.name) / "isolated.sqlite3")
        env["EDGEOPS_ADMIN_EMAIL"] = cls.email
        env["EDGEOPS_ADMIN_PASSWORD"] = cls.password
        cls.server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app",
             "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        try:
            for _ in range(80):
                if cls.server.poll() is not None:
                    raise RuntimeError("Isolated FastAPI process exited during startup")
                try:
                    with urllib.request.urlopen(cls.base + "/signin", timeout=1) as response:
                        if response.status == 200:
                            break
                except (urllib.error.URLError, TimeoutError, ConnectionError):
                    time.sleep(.15)
            else:
                raise RuntimeError("Isolated FastAPI service failed to respond")
            cls.playwright = sync_playwright().start()
            cls.browser = cls.playwright.chromium.launch(headless=True)
        except BaseException:
            cls.server.terminate()
            cls.server.wait(timeout=8)
            cls.temp.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.terminate()
        try:
            cls.server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=8)
        cls.server.stderr.close()
        cls.temp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1440, "height": 900})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(self.base + "/signin")
        self.page.locator("#email").fill(self.email)
        self.page.locator("#password").fill(self.password)
        self.page.locator("#submit").click()
        self.page.wait_for_url("**/app", timeout=10000)
        self.page.locator("#connection-chip[data-state='ok']").wait_for(timeout=10000)

    def tearDown(self):
        self.context.close()

    def assert_stage(self, name):
        section = self.page.locator(f"#page-{name}")
        self.assertTrue(section.is_visible(), f"Section {name} must be displayed")
        self.assertEqual(
            self.page.locator(".page-section.active").count(), 1,
            f"Only one content section may be active for {name}",
        )
        active = self.page.locator(f'.nav-item[data-page="{name}"]')
        self.assertEqual(active.get_attribute("aria-current"), "page")
        self.assertTrue(active.get_attribute("class").find("active") >= 0)
        self.assertGreater(len(self.page.locator("#page-title").inner_text().strip()), 4)
        self.assertGreater(len(self.page.locator("#page-subtitle").inner_text().strip()), 12)
        self.assertIn("#" + name, self.page.url)
        self.assertIn("EDGEOPS", self.page.title())

    def test_01_all_eighteen_pages_render_without_browser_errors(self):
        self.assertEqual(self.page.locator(".nav-item[data-page]").count(), len(STAGES))
        for name in STAGES:
            with self.subTest(section=name):
                self.page.locator(f'.nav-item[data-page="{name}"]').click()
                self.assert_stage(name)
                if name == "architecture":
                    self.page.locator('[data-arch-node="mqtt"]').click()
                    self.assertIn("MQTT", self.page.locator("#arch-detail-title").inner_text())
                if name == "assets":
                    self.page.locator("#asset-search").fill("motor")
                    self.assertIn("of 12 assets", self.page.locator("#asset-result-count").inner_text())
                    self.page.locator("#asset-search").fill("")
                if name == "hardware":
                    self.page.locator("#hardware-table tr").first.wait_for()
                    self.assertGreater(self.page.locator("#hardware-table tr").count(), 10)
                if name == "security":
                    self.assertEqual(self.page.locator("#session-role").inner_text(), "admin")
                    self.assertGreater(self.page.locator("#audit-entries tr").count(), 0)
        self.assertFalse(self.errors, "Uncaught JS errors: " + repr(self.errors))

    def test_02_browser_history_and_deep_links(self):
        for name in ("assets", "architecture", "security"):
            self.page.locator(f'.nav-item[data-page="{name}"]').click()
            self.assert_stage(name)
        self.page.go_back()
        self.assert_stage("architecture")
        self.page.go_back()
        self.assert_stage("assets")
        self.page.go_forward()
        self.assert_stage("architecture")
        self.page.reload()
        self.assert_stage("architecture")
        self.assertFalse(self.errors, repr(self.errors))

    def test_03_mobile_navigation_open_close_and_section_selection(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        menu=self.page.locator("#menu-toggle")
        self.assertTrue(menu.is_visible())
        menu.click()
        self.assertEqual(menu.get_attribute("aria-expanded"), "true")
        self.page.locator('.nav-item[data-page="architecture"]').click()
        self.assert_stage("architecture")
        self.assertEqual(menu.get_attribute("aria-expanded"), "false")
        self.assertTrue(self.page.locator("#mobile-scrim").is_hidden())
        menu.click()
        self.page.keyboard.press("Escape")
        self.assertEqual(menu.get_attribute("aria-expanded"), "false")
        self.assertFalse(self.errors, repr(self.errors))


    def test_04_invalid_password_is_rejected_and_protected_app_redirects(self):
        guest = self.browser.new_context()
        page = guest.new_page()
        try:
            page.goto(self.base + "/app")
            page.wait_for_url("**/signin")
            page.locator("#email").fill(self.email)
            page.locator("#password").fill("not-the-real-test-password")
            page.locator("#submit").click()
            page.locator("#form-error").get_by_text("Invalid email or password.").wait_for()
            self.assertIn("/signin", page.url)
            page.goto(self.base + "/api/me")
            self.assertIn("Authentication required", page.locator("body").inner_text())
        finally:
            guest.close()

    def test_05_logout_revokes_browser_session_and_back_is_protected(self):
        self.page.locator("#logout").click()
        self.page.wait_for_url("**/signin")
        self.page.go_back()
        # Even when the browser restores a cached document, a protected
        # navigation must not return authenticated application content.
        self.page.goto(self.base + "/app")
        self.page.wait_for_url("**/signin")
        self.assertFalse(self.errors, repr(self.errors))

    def test_06_expired_server_session_requires_new_login(self):
        database_path = Path(self.temp.name) / "isolated.sqlite3"
        with sqlite3.connect(database_path, timeout=10) as db:
            db.execute("UPDATE sessions SET expires_at = 1")
            db.commit()
        self.page.goto(self.base + "/app", wait_until="domcontentloaded")
        self.page.wait_for_url("**/signin")
        self.assertTrue(self.page.locator("#signin-form").is_visible())
        self.assertFalse(self.errors, repr(self.errors))

    def test_07_session_metadata_and_authenticated_app_content(self):
        self.assertEqual(self.page.locator("#session-user").inner_text(), self.email)
        self.assertEqual(self.page.locator("#session-role").inner_text(), "admin")
        self.assertNotEqual(self.page.locator("#session-expiry").inner_text(), "Unavailable")
        self.assertEqual(self.page.locator("#connection-chip").get_attribute("data-state"), "ok")
        self.assertTrue(self.page.locator("#page-overview").is_visible())
        self.assertFalse(self.errors, repr(self.errors))


    def test_08_asset_filters_search_counts_and_empty_state(self):
        self.page.locator('.nav-item[data-page="assets"]').click()
        rows = self.page.locator("#all-assets tr")
        self.assertEqual(rows.count(), 12)
        self.page.locator("#asset-filter").select_option("critical")
        self.assertEqual(rows.count(), 1)
        self.assertIn("Drive Motor A", rows.first.inner_text())
        self.assertEqual(self.page.locator("#asset-result-count").inner_text(), "1 of 12 assets")
        self.page.locator("#asset-filter").select_option("watch")
        self.assertEqual(rows.count(), 3)
        self.page.locator("#asset-filter").select_option("nominal")
        self.assertEqual(rows.count(), 8)
        self.page.locator("#asset-filter").select_option("all")
        self.page.locator("#asset-search").fill("MTR-001")
        self.assertEqual(rows.count(), 1)
        self.assertIn("Drive Motor A", rows.first.inner_text())
        self.page.locator("#asset-search").fill("nonexistent-factory-equipment")
        self.assertEqual(self.page.locator("#asset-result-count").inner_text(), "0 of 12 assets")
        self.assertIn("No demo assets match", rows.first.inner_text())
        self.page.locator("#asset-search").fill("")
        self.assertEqual(rows.count(), 12)
        self.assertFalse(self.errors, repr(self.errors))

    def test_09_alert_filters_and_browser_only_acknowledgments(self):
        self.page.locator('.nav-item[data-page="alerts"]').click()
        items = self.page.locator("#all-alerts .alert-item")
        self.assertEqual(items.count(), 3)
        self.assertEqual(self.page.locator("#nav-alert-count").inner_text(), "3")
        self.page.locator("#alert-filter").select_option("critical")
        self.assertEqual(items.count(), 1)
        self.assertIn("Elevated vibration", items.first.inner_text())
        self.page.locator("#alert-filter").select_option("acknowledged")
        self.assertIn("No demo alerts match", self.page.locator("#all-alerts").inner_text())
        self.page.locator("#alert-filter").select_option("open")
        self.assertEqual(items.count(), 3)
        items.first.locator("button[data-ack]").click()
        self.assertEqual(items.count(), 2)
        self.assertEqual(self.page.locator("#nav-alert-count").inner_text(), "2")
        self.assertIn("2 OPEN", self.page.locator("#alert-summary").inner_text())
        self.page.locator("#alert-filter").select_option("acknowledged")
        self.assertEqual(items.count(), 1)
        self.assertIn("Acknowledged", items.first.inner_text())
        self.assertTrue(items.first.locator("button[data-ack]").is_disabled())
        self.page.reload()
        self.page.locator('.nav-item[data-page="alerts"]').click()
        self.assertEqual(items.count(), 3)
        self.assertEqual(self.page.locator("#nav-alert-count").inner_text(), "3")
        self.assertFalse(self.errors, repr(self.errors))

    def test_10_global_search_routes_demo_content(self):
        search = self.page.locator("#global-search")
        search.fill("compressor")
        search.press("Enter")
        self.assert_stage("assets")
        self.assertIn("Compressor Unit", self.page.locator("#toast").inner_text())
        search.fill("vibration detected")
        search.press("Enter")
        self.assert_stage("alerts")
        self.assertIn("Elevated vibration", self.page.locator("#toast").inner_text())
        search.fill("architecture")
        search.press("Enter")
        self.assert_stage("architecture")
        search.fill("impossible-search-query-xyz")
        search.press("Enter")
        self.assertIn("No matching simulated", self.page.locator("#toast").inner_text())
        self.assertFalse(self.errors, repr(self.errors))


    def test_11_architecture_stages_security_and_failure_views(self):
        self.page.locator('.nav-item[data-page="architecture"]').click()
        stages = {
            "sensors": ("Sensors & Bench Rig", "PLANNED"),
            "esp32": ("ESP32 Acquisition", "PLANNED"),
            "mqtt": ("MQTT / Mutual TLS", "LAB TESTED"),
            "gateway": ("Edge API Gateway", "LAB TESTED"),
            "pipeline": ("Data Pipeline & Persistence", "LAB TESTED"),
            "ai": ("AI / Agentic Intelligence", "NOT DEPLOYED"),
            "api": ("Enterprise API & Access", "LOCAL DEMO"),
            "dashboard": ("Human Operations Console", "LOCAL DEMO"),
        }
        for key, (title, status) in stages.items():
            with self.subTest(component=key):
                button = self.page.locator(f'[data-arch-node="{key}"]')
                button.click()
                self.assertEqual(button.get_attribute("aria-pressed"), "true")
                self.assertEqual(self.page.locator("#arch-detail-title").inner_text(), title)
                self.assertEqual(self.page.locator("#arch-detail-badge").inner_text(), status)
                for detail in ("tech", "security", "failure", "evidence", "decision"):
                    self.assertGreater(
                        len(self.page.locator(f"#arch-detail-{detail}").inner_text().strip()),
                        15,
                    )
                self.assertEqual(self.page.locator('.arch-node[aria-pressed="true"]').count(), 1)
        views = {
            "security": "TRUST BOUNDARIES",
            "failure": "FAILURE PATHS",
            "overview": "8 SYSTEM STAGES",
        }
        for mode, heading in views.items():
            button = self.page.locator(f'[data-arch-mode="{mode}"]')
            button.click()
            self.assertEqual(button.get_attribute("aria-pressed"), "true")
            self.assertEqual(self.page.locator("#arch-map-status").inner_text(), heading)
            self.assertEqual(self.page.locator("#arch-pipeline").get_attribute("data-mode"), mode)
            self.assertEqual(self.page.locator('.arch-tab[aria-pressed="true"]').count(), 1)
            self.assertGreater(len(self.page.locator("#arch-view-help").inner_text()), 20)
        self.assertIn("read-only", self.page.locator("#page-architecture").inner_text().lower())
        self.assertFalse(self.errors, repr(self.errors))

    def test_12_report_export_download_is_valid_disclosed_synthetic_json(self):
        self.page.locator('.nav-item[data-page="reports"]').click()
        with self.page.expect_download() as transfer:
            self.page.locator("#report-export").click()
        download = transfer.value
        self.assertEqual(download.suggested_filename, "edgeops-synthetic-dashboard-snapshot.json")
        path = download.path()
        with open(path, "r", encoding="utf-8") as handle:
            exported = json.load(handle)
        self.assertEqual(exported["product"], "EDGEOPS")
        self.assertEqual(exported["mode"], "synthetic-ui-prototype")
        self.assertIn("NOT live", exported["provenance"])
        self.assertEqual(len(exported["assets"]), 12)
        self.assertEqual(len(exported["alerts"]), 3)
        self.assertIn("No production safety approval", exported["disclaimers"])
        self.assertIn("not an operational data report", self.page.locator("#toast").inner_text().lower())
        self.assertFalse(self.errors, repr(self.errors))


    def test_13_responsive_page_widths_and_usable_controls(self):
        """Every section must fit the viewport; dense tables may scroll internally."""
        for width, height in ((1440,900),(1024,768),(768,900),(390,844),(320,720)):
            with self.subTest(viewport=width):
                self.page.set_viewport_size({"width":width,"height":height})
                for name in STAGES:
                    with self.subTest(viewport=width,section=name):
                        if width<=800:
                            self.page.locator("#menu-toggle").click()
                        self.page.locator(f'.nav-item[data-page="{name}"]').click()
                        self.assertTrue(self.page.locator(f"#page-{name}").is_visible())
                        layout=self.page.evaluate("""() => ({
                            viewport:document.documentElement.clientWidth,
                            document:document.documentElement.scrollWidth,
                            body:document.body.scrollWidth,
                            main:document.querySelector('main').getBoundingClientRect().width,
                            toggler:document.querySelector('#menu-toggle').getBoundingClientRect().width,
                            visibleSidebar:getComputedStyle(document.querySelector('#sidebar')).transform
                        })""")
                        self.assertLessEqual(
                            layout["document"],layout["viewport"]+2,
                            f"Horizontal page overflow at {width}px on {name}: {layout}",
                        )
                        self.assertLessEqual(
                            layout["body"],layout["viewport"]+2,
                            f"Body overflow at {width}px on {name}: {layout}",
                        )
                if width <= 800:
                    self.assertTrue(self.page.locator("#menu-toggle").is_visible())
                else:
                    self.assertTrue(self.page.locator('.nav-item[data-page="settings"]').is_visible())
        self.assertFalse(self.errors,repr(self.errors))


    def test_14_keyboard_navigation_skip_link_and_focus_management(self):
        """The signed-in dashboard must remain usable without pointer input."""
        self.page.keyboard.press("Tab")
        skip = self.page.locator('a.skip[href="#main"]')
        self.assertTrue(skip.evaluate("el => document.activeElement === el"))
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.locator("#main").get_attribute("tabindex"), "-1")
        nav = self.page.locator('.nav-item[data-page="architecture"]')
        nav.focus()
        self.page.keyboard.press("Enter")
        self.assert_stage("architecture")
        self.assertTrue(self.page.locator("#page-title").evaluate("el => document.activeElement === el"))
        self.page.locator('[data-arch-node="ai"]').focus()
        self.page.keyboard.press("Enter")
        self.assertEqual(self.page.locator("#arch-detail-badge").inner_text(), "NOT DEPLOYED")
        self.page.locator('[data-arch-mode="security"]').focus()
        self.page.keyboard.press("Space")
        self.assertEqual(self.page.locator("#arch-map-status").inner_text(), "TRUST BOUNDARIES")
        self.assertFalse(self.errors, repr(self.errors))

    def test_15_accessible_names_labels_landmarks_and_visible_focus(self):
        """Check core semantics and style presence; not a full WCAG audit."""
        self.assertEqual(self.page.locator("main#main").count(), 1)
        self.assertEqual(self.page.locator('nav[aria-label="Dashboard sections"]').count(), 1)
        self.assertEqual(self.page.locator('button[data-page]').count(), len(STAGES))
        self.assertEqual(self.page.locator('button[data-page][aria-current="page"]').count(), 1)
        self.assertEqual(self.page.locator('button[data-page] .nav-symbol[aria-hidden="true"]').count(), len(STAGES))
        for control in ("global-search", "asset-search", "asset-filter", "alert-filter"):
            self.assertTrue(self.page.locator("#"+control).evaluate("""el => !!(
                el.getAttribute('aria-label') ||
                (el.labels && el.labels.length) ||
                document.querySelector('label[for="'+el.id+'"]')
            )"""), "Missing accessible input label: "+control)
        button=self.page.locator('.nav-item[data-page="assets"]')
        button.focus()
        style=button.evaluate("""el => ({
            width:getComputedStyle(el).outlineWidth,
            color:getComputedStyle(el).outlineColor,
            style:getComputedStyle(el).outlineStyle
        })""")
        self.assertNotEqual(style["style"], "none")
        self.assertGreaterEqual(float(style["width"].replace("px","")), 2)
        self.assertNotEqual(style["color"], "rgba(0, 0, 0, 0)")
        self.assertFalse(self.errors, repr(self.errors))

    def test_16_signin_form_has_keyboard_operable_labels_and_feedback(self):
        guest=self.browser.new_context()
        page=guest.new_page()
        try:
            page.goto(self.base+"/signin")
            self.assertEqual(page.locator('a.skip[href="#signin-form"]').count(), 1)
            for field in ("email", "password"):
                self.assertGreater(page.locator('label[for="'+field+'"]').count(), 0)
            page.locator("#toggle-password").focus()
            page.keyboard.press("Enter")
            self.assertEqual(page.locator("#password").get_attribute("type"), "text")
            page.keyboard.press("Enter")
            self.assertEqual(page.locator("#password").get_attribute("type"), "password")
            page.locator("#forgot-password").focus()
            page.keyboard.press("Enter")
            self.assertIn("not configured", page.locator("#access-note").inner_text())
            self.assertEqual(page.locator("#form-error").get_attribute("role"), "alert")
        finally:
            guest.close()


    def test_17_inventory_error_and_retry_recover_without_stale_data(self):
        """A failed inventory request clears stale content; retry restores it."""
        self.page.locator('.nav-item[data-page="hardware"]').click()
        self.assertEqual(self.page.locator("#hardware-table tr").count(), 30)
        def fail_inventory(route):
            route.fulfill(status=503, content_type="application/json", body='{"detail":"simulated outage"}')
        self.page.route("**/api/hardware",fail_inventory)
        self.page.locator("#refresh-hardware").click()
        self.page.locator('#hardware-feedback[data-state="error"]').wait_for(timeout=10000)
        self.assertIn("Inventory could not be loaded",self.page.locator("#hardware-table").inner_text())
        self.assertEqual(self.page.locator("#hardware-metrics").inner_text().strip(),"")
        self.page.unroute("**/api/hardware",fail_inventory)
        self.page.locator("#refresh-hardware").click()
        self.page.locator('#hardware-feedback[data-state="ok"]').wait_for(timeout=10000)
        self.assertEqual(self.page.locator("#hardware-table tr").count(),30)
        self.assertFalse(self.errors,repr(self.errors))

    def test_18_audit_access_denied_then_retry_restores_history(self):
        self.page.locator('.nav-item[data-page="security"]').click()
        def deny_audit(route):
            route.fulfill(status=403, content_type="application/json", body='{"detail":"restricted"}')
        self.page.route("**/api/audit?limit=30",deny_audit)
        self.page.locator("#refresh-audit").click()
        self.page.locator('#audit-feedback[data-state="error"]').wait_for(timeout=10000)
        self.assertIn("Access restricted",self.page.locator("#audit-feedback").inner_text())
        self.assertIn("Audit history unavailable",self.page.locator("#audit-entries").inner_text())
        self.page.unroute("**/api/audit?limit=30",deny_audit)
        self.page.locator("#refresh-audit").click()
        self.page.locator('#audit-feedback[data-state="ok"]').wait_for(timeout=10000)
        self.assertGreater(self.page.locator("#audit-entries tr").count(),0)
        self.assertFalse(self.errors,repr(self.errors))

    def test_19_api_health_outage_global_banner_and_reconnect(self):
        def fail_health(route):
            route.fulfill(status=503, content_type="application/json", body='{"detail":"simulated outage"}')
        self.page.route("**/api/system/health",fail_health)
        self.page.reload()
        self.page.locator('#connection-chip[data-state="error"]').wait_for(timeout=10000)
        banner=self.page.locator("#api-recovery")
        self.assertTrue(banner.is_visible())
        self.assertIn("Service returned 503",banner.inner_text())
        self.assertIn("Inventory unavailable",self.page.locator("#hardware-table").inner_text())
        self.assertIn("Audit history unavailable",self.page.locator("#audit-entries").inner_text())
        self.page.unroute("**/api/system/health",fail_health)
        self.page.locator("#retry-connection").click()
        self.page.locator('#connection-chip[data-state="ok"]').wait_for(timeout=10000)
        self.assertTrue(banner.is_hidden())
        self.assertEqual(self.page.locator("#hardware-table tr").count(),30)
        self.assertEqual(self.page.locator("#audit-feedback").get_attribute("data-state"),"ok")
        self.assertFalse(self.errors,repr(self.errors))


    def test_20_release_gate_synthetic_disclosure_and_assets(self):
        """Final review: the UI must never present simulated data as live control."""
        for section in ("overview", "insights", "hardware", "architecture", "alerts", "reports"):
            with self.subTest(section=section):
                self.page.locator(f'.nav-item[data-page="{section}"]').click()
                disclosure=self.page.locator(".disclosure").first
                self.assertTrue(disclosure.is_visible())
                self.assertIn("simulated", disclosure.inner_text().lower())
                self.assertIn("no real devices", disclosure.inner_text().lower())
                self.assertFalse(self.page.get_by_role("button",name="Start motor").count())
                self.assertFalse(self.page.get_by_role("button",name="Stop motor").count())
        images=self.page.locator("img")
        for idx in range(images.count()):
            image=images.nth(idx)
            self.assertTrue(image.evaluate("el => el.complete && el.naturalWidth > 0"),
                            "Broken dashboard image: "+str(image.get_attribute("src")))
        self.assertFalse(self.errors,repr(self.errors))

    def test_21_release_gate_security_headers_and_private_api(self):
        """These checks are local-prototype safeguards, not a penetration test."""
        responses={
            "/app":self.page.request.get(self.base+"/app"),
            "/api/me":self.page.request.get(self.base+"/api/me"),
            "/static/app.js":self.page.request.get(self.base+"/static/app.js"),
        }
        for path,response in responses.items():
            self.assertEqual(response.status,200,path)
            headers=response.headers
            self.assertEqual(headers.get("cache-control"),"no-store")
            self.assertEqual(headers.get("x-frame-options"),"DENY")
            self.assertEqual(headers.get("x-content-type-options"),"nosniff")
            self.assertIn("frame-ancestors 'none'",headers.get("content-security-policy",""))
        anonymous=self.browser.new_context()
        try:
            response=anonymous.request.get(self.base+"/api/hardware")
            self.assertEqual(response.status,401)
            response=anonymous.request.get(self.base+"/api/audit")
            self.assertEqual(response.status,401)
            response=anonymous.request.get(self.base+"/static/server.py")
            self.assertEqual(response.status,404)
            response=anonymous.request.get(self.base+"/app",max_redirects=0)
            self.assertEqual(response.status,303)
            self.assertEqual(response.headers.get("location"),"/signin")
        finally:
            anonymous.close()

    def test_22_release_gate_visual_capture_and_readability(self):
        """Create reproducible screenshots for manual visual review in CI artifacts."""
        screenshots=Path(__file__).parent/".."/".acceptance-captures"
        screenshots.mkdir(parents=True,exist_ok=True)
        for width,height in ((1440,900),(390,844)):
            self.page.set_viewport_size({"width":width,"height":height})
            for name in ("overview","architecture","hardware","reports"):
                if width<=800:
                    self.page.locator("#menu-toggle").click()
                self.page.locator(f'.nav-item[data-page="{name}"]').click()
                heading=self.page.locator("#page-title")
                self.assertTrue(heading.is_visible())
                self.assertGreater(len(heading.inner_text().strip()),4)
                self.page.screenshot(
                    path=str(screenshots/f"edgeops-{width}-{name}.png"),
                    full_page=True,animations="disabled"
                )
        self.assertFalse(self.errors,repr(self.errors))


    def test_23_offline_reports_ui_empty_state_and_synthetic_disclosure(self):
        self.page.locator('.nav-item[data-page="reports"]').click()
        self.page.locator('#experiment-feedback[data-state="ok"]').wait_for(timeout=10000)
        self.assertIn("verified synthetic experiments", self.page.locator("#experiment-feedback").inner_text())
        self.assertIn("No verified offline experiments", self.page.locator("#experiment-entries").inner_text())
        self.assertIn("no predictive model is deployed", self.page.locator("#page-reports").inner_text().lower())
        self.assertFalse(self.errors, repr(self.errors))

    def test_24_offline_reports_ui_retry_and_safe_escaping(self):
        self.page.locator('.nav-item[data-page="reports"]').click()
        example={
          "mode":"synthetic-offline-only","model_deployed":False,
          "hardware_connected":False,
          "experiments":[{
             "run_id":"c1a717fb28e832215988332d2ab672a4a123fa90d0695dab31331aa9904af8c1",
             "model_kind":"<img src=x onerror=alert(1)>",
             "test_count":10,"precision":0.9,"recall":1.0,"f1":0.947368,
             "deployment_status":"not-deployed"
          }]
        }
        def mocked(route):
            route.fulfill(status=200,content_type="application/json",body=json.dumps(example))
        self.page.route("**/api/offline-experiments?limit=20",mocked)
        self.page.locator("#refresh-experiments").click()
        self.page.locator('#experiment-feedback[data-state="ok"]').wait_for(timeout=10000)
        self.assertEqual(self.page.locator("#experiment-entries tr").count(),1)
        self.assertEqual(self.page.locator("#experiment-entries img").count(),0)
        self.assertIn("94.7%",self.page.locator("#experiment-entries").inner_text())
        self.page.unroute("**/api/offline-experiments?limit=20",mocked)
        self.page.locator("#refresh-experiments").click()
        self.page.locator('#experiment-feedback[data-state="ok"]').wait_for(timeout=10000)
        self.assertIn("No verified offline experiments",self.page.locator("#experiment-entries").inner_text())
        self.assertFalse(self.errors,repr(self.errors))



if __name__ == "__main__":
    unittest.main(verbosity=2)

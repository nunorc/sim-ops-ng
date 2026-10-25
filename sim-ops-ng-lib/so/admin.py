
from flask import Flask, render_template, redirect, url_for, request, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import os
import secrets
import logging
import subprocess
import sys
from urllib.parse import urlsplit

from .utils import resolve_control_request

app = Flask(__name__)
# an empty key breaks every login: fall back to a random one, made before gunicorn forks so workers share it
app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
# CSRF: SameSite=Lax keeps the session cookie off cross-site POSTs; _same_origin_posts covers older browsers
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
BACKEND_URL = os.getenv("SIM_OPS_NG_API_URL", "http://localhost:9111")
USER_PASSWORD = os.getenv("SIM_OPS_NG_USER_PASSWORD", "user123")
ADMIN_PASSWORD = os.getenv("SIM_OPS_NG_ADMIN_PASSWORD", "admin123")

# Derive WS URL from BACKEND_URL for local dev; leave empty for Docker/nginx (built client-side)
_backend_is_local = any(h in BACKEND_URL for h in ("localhost", "127.0.0.1", "0.0.0.0"))
if _backend_is_local:
    _ws_scheme = "wss" if BACKEND_URL.startswith("https") else "ws"
    _ws_host = BACKEND_URL.split("://", 1)[1]
    WS_URL = os.getenv("SIM_OPS_NG_WS_URL", f"{_ws_scheme}://{_ws_host}/api/ws")
else:
    WS_URL = os.getenv("SIM_OPS_NG_WS_URL", "")  # empty → client builds from window.location (nginx/proxy)

REQUEST_TIMEOUT = 5

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

TRIGGER_SCRIPTS = {1: "trigger-1.py", 2: "trigger-2.py"}
TRIGGER_TIMEOUT = 60

@app.before_request
def _same_origin_posts():
    """403 for a POST whose Origin (or Referer) is another host than this app's."""
    if request.method != "POST":
        return None
    source = request.headers.get("Origin") or request.headers.get("Referer")
    if not source:
        return None  # not a browser (curl, scripts): no ambient cookie to abuse
    # hostnames only: nginx forwards Host without the port the browser used
    if urlsplit(source).hostname != urlsplit(f"//{request.host}").hostname:
        logger.warning("Rejected cross-origin POST to %s from %s", request.path, source)
        return {"error": "Cross-origin request rejected"}, 403
    return None


def admin_headers():
    """Get headers with admin password"""
    if not session.get("admin"):
        return None
    return {"X-Admin-Password": ADMIN_PASSWORD}


def require_login():
    """Check if user is logged in"""
    # the session cookie is signed, not encrypted: it holds a flag, never the password
    return not session.get("admin")


def _backend_error(response):
    """(error_dict, status_code) for a non-200 backend response, keeping the API's error detail."""
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, list):  # FastAPI request validation: [{"msg": ..., ...}, ...]
        detail = "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detail)
    return {"error": str(detail) if detail else f"Backend error: {response.status_code}"}, response.status_code


def _backend_get(path, params=None):
    """GET path from the backend; returns (json_or_error_dict, status_code)."""
    try:
        response = requests.get(
            f"{BACKEND_URL}{path}",
            headers=admin_headers(),
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json(), 200
        return _backend_error(response)
    except requests.RequestException as e:
        logger.error(f"Backend connection error: {e}")
        return {"error": "Cannot connect to backend"}, 503


def _backend_post(path, payload):
    """POST payload to path on the backend; returns (json_or_error_dict, status_code)."""
    try:
        response = requests.post(
            f"{BACKEND_URL}{path}",
            headers=admin_headers(),
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json(), 200
        return _backend_error(response)
    except requests.RequestException as e:
        logger.error(f"Backend connection error: {e}")
        return {"error": "Cannot connect to backend"}, 503


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page and handler"""
    if request.method == "POST":
        password = request.form.get("password", "")

        if not password:
            flash("Password is required", "error")
            return render_template("login.html")

        if not secrets.compare_digest(password, ADMIN_PASSWORD):
            flash("Invalid password", "error")
            return render_template("login.html")

        session.clear()
        session["admin"] = True
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    """Logout handler"""
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))


@app.route("/", methods=["GET"])
def index():
    """Dashboard page"""
    if require_login():
        return redirect(url_for("login"))

    # Fetch sim state (also checks backend connectivity)
    sim_state, status = _backend_get("/api/sim")
    if status != 200:
        flash("Warning: Cannot connect to SimOps API. Check if services are running.", "warning")
        sim_state = {}

    # Fetch ground station state (for the downlink status in the header)
    state_data, status = _backend_get("/api/state")
    gs_state = state_data.get("ground_station", {}) if status == 200 else {}

    # Fetch scenario (includes generic info and breakpoints)
    scenario, status = _backend_get("/api/scenario")
    if status == 200:
        breakpoints = scenario.get("breakpoints", [])
    else:
        scenario = {}
        breakpoints = []

    # read the password from the backend (source of truth), not the session cookie, which outlives a backend restart
    password_data, status = _backend_get("/api/admin/user-password")
    user_password = password_data.get("password", USER_PASSWORD) if status == 200 else USER_PASSWORD

    return render_template(
        "control.html",
        ws_url=WS_URL,
        user_password=user_password,
        admin_password=ADMIN_PASSWORD,
        status_dl=gs_state.get("status_dl", "NO_RF"),
        scenario=scenario,      # Full scenario dict
        breakpoints=breakpoints,  # Breakpoints list for UI
        breakpoint=sim_state.get("breakpoint", ""),
        data_proxy=sim_state.get("data_proxy", "SLE"),
    )


@app.route("/start", methods=["POST"])
def start():
    """Start simulation"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/start",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Simulation started", "success")
        else:
            flash(f"Error starting simulation: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Start command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/stop", methods=["POST"])
def stop():
    """Stop simulation"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/stop",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Simulation stopped", "success")
        else:
            flash(f"Error stopping simulation: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Stop command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/pause", methods=["POST"])
def pause():
    """Pause simulation"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/pause",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Simulation paused", "success")
        else:
            flash(f"Error pausing simulation: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Pause command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/resume", methods=["POST"])
def resume():
    """Resume simulation"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/resume",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Simulation resumed", "success")
        else:
            flash(f"Error resuming simulation: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Resume command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/next-breakpoint", methods=["POST"])
def next_breakpoint():
    """Move to next breakpoint"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/next-breakpoint",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Moved to next breakpoint", "success")
        else:
            flash(f"Error moving to breakpoint: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Breakpoint command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/previous-breakpoint", methods=["POST"])
def previous_breakpoint():
    """Move to previous breakpoint"""
    if require_login():
        return redirect(url_for("login"))

    try:
        response = requests.post(
            f"{BACKEND_URL}/api/previous-breakpoint",
            headers=admin_headers(),
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 200:
            flash("Moved to previous breakpoint", "success")
        else:
            flash(f"Error moving to breakpoint: {response.status_code}", "error")
    except requests.RequestException as e:
        logger.error(f"Breakpoint command error: {e}")
        flash("Cannot connect to backend", "error")

    return redirect(url_for("index"))


@app.route("/api/change_password", methods=["POST"])
def change_password_api():
    """Change user password via API"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    try:
        data = request.get_json(silent=True) or {}
        new_password = data.get("password", "").strip()

        if not new_password:
            return {"error": "Password cannot be empty"}, 400

        # update the password on the backend API (what MCS authenticates against), not just in the session
        response = requests.post(
            f"{BACKEND_URL}/api/admin/user-password",
            headers=admin_headers(),
            json={"password": new_password},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            return _backend_error(response)

        # no local caching: the control panel reads the password back from the backend on each render
        logger.info("User password changed successfully")
        return {"success": True, "message": "Password changed successfully"}

    except requests.RequestException as e:
        logger.error(f"Error changing password: {e}")
        return {"error": "Cannot connect to backend"}, 503
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return {"error": str(e)}, 500


def _apply_control(data, headers):
    """Apply a single control step using the same routing as the trigger scripts"""
    url, payload = resolve_control_request(BACKEND_URL, data)

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            return {"status": "FAIL", "error": _backend_error(response)[0]["error"]}
    except requests.RequestException as e:
        return {"status": "FAIL", "error": str(e)}


@app.route("/api/trigger/<int:trigger_id>", methods=["POST"])
def run_trigger(trigger_id):
    """Run data/trigger-<n>.py as a subprocess."""
    if require_login():
        return {"error": "Not authenticated"}, 401

    script = TRIGGER_SCRIPTS.get(trigger_id)
    if script is None:
        return {"error": f"Unknown trigger: {trigger_id}"}, 404

    env = {**os.environ,
           "SIM_OPS_NG_API_URL": BACKEND_URL,
           "SIM_OPS_NG_ADMIN_PASSWORD": ADMIN_PASSWORD}

    try:
        proc = subprocess.run(
            [sys.executable, os.path.join(_DATA_DIR, script)],
            cwd=_DATA_DIR, env=env, capture_output=True, text=True,
            timeout=TRIGGER_TIMEOUT, check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error(f"{script} timed out after {TRIGGER_TIMEOUT}s")
        return {"error": f"{script} timed out after {TRIGGER_TIMEOUT}s"}, 504
    except OSError as e:
        logger.error(f"Cannot run {script}: {e}")
        return {"error": f"Cannot run {script}: {e}"}, 500

    output = (proc.stdout or "") + (proc.stderr or "")
    steps = sum(1 for line in proc.stdout.splitlines() if line.startswith("S:"))
    logger.info(f"Ran {script} (rc={proc.returncode}, {steps} steps)\n{output}")

    if proc.returncode != 0:
        return {"error": f"{script} failed", "output": output, "steps": steps}, 500

    return {"success": True, "trigger": trigger_id, "script": script,
            "steps": steps, "output": output}


@app.route("/api/safe-mode", methods=["POST"])
def trigger_safe_mode():
    """Trigger spacecraft safe mode (single control step)"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    step = {"system": "spacecraft", "control": "trigger_safe_mode", "value": None}
    result = _apply_control(step, admin_headers())

    logger.info(f"Triggered safe mode: {result}")
    if result.get("status") == "FAIL":
        return {"error": result.get("error") or "Failed to trigger safe mode", "result": result}, 502
    return {"success": True, "result": result}


@app.route("/api/command", methods=["POST"])
def send_command():
    """Send a spacecraft command to the backend"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    data = request.get_json(silent=True) or {}
    control = data.get("control", "").strip()
    value = data.get("value", "")

    if not control:
        return {"error": "Control name is required"}, 400

    return _backend_post("/api/admin/set-state", {"attr": control, "value": value})


@app.route("/api/overrides", methods=["GET"])
def get_overrides():
    """Get current overrides"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    return _backend_get("/api/overrides")


@app.route("/api/override/set", methods=["POST"])
def set_override():
    """Set an override"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    data = request.get_json(silent=True) or {}
    attr = data.get("attr", "").strip()
    value = data.get("value", "")

    if not attr:
        return {"error": "Attribute name is required"}, 400

    return _backend_post("/api/override/set", {"attr": attr, "value": value})


@app.route("/api/override/unset", methods=["POST"])
def unset_override():
    """Remove an override"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    data = request.get_json(silent=True) or {}
    attr = data.get("attr", "").strip()

    if not attr:
        return {"error": "Attribute name is required"}, 400

    return _backend_post("/api/override/unset", {"attr": attr})


@app.route("/api/scenarios", methods=["GET"])
def list_scenarios():
    """List available scenario JSON files from the backend's data folder"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    return _backend_get("/api/scenarios")


@app.route("/api/scenario/load", methods=["POST"])
def load_scenario_api():
    """Load a scenario from the backend's data folder, restarting the sim loop if needed"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "").strip()

    if not filename:
        return {"error": "Filename is required"}, 400

    return _backend_post("/api/scenario/load", {"filename": f"data/{filename}"})


@app.route("/api/set-data-proxy", methods=["POST"])
def set_data_proxy():
    """Set the data proxy mode (EGSE or SLE)"""
    if require_login():
        return {"error": "Not authenticated"}, 401

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "").upper().strip()

    if mode not in ("EGSE", "SLE"):
        return {"error": "Invalid mode. Must be EGSE or SLE."}, 400

    return _backend_post("/api/data-proxy", {"mode": mode})

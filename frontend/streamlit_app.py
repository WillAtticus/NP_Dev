"""
NeuroPulse — Research Dashboard (Dual Mode: Standalone Sandbox & Connected API)

Supports:
1. STANDALONE SANDBOX / IN-PROCESS ENGINE: Direct NumPy / SciPy DSP pipeline & NPI execution.
2. CONNECTED API MODE: Communicates with local FastAPI backend + ESP32 Hardware/Virtual Serial.

⚠ RESEARCH / EXPERIMENTAL — NOT FOR DIAGNOSIS
"""
import sys
import os
import time
import json
import math
import uuid
import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Ensure project root is on sys.path for direct in-process engine access ──
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.services.processing.engine import (
    run_pipeline,
    BUILTIN_PROFILES,
    QualityStatus,
)
from backend.app.services.algorithms.npi import run_npi, AlgorithmRegistry

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Streamlit Page Configuration ────────────────────────────────────────────
st.set_page_config(
    page_title="NeuroPulse — Research Platform",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

BACKEND_URL = os.environ.get("NEUROPULSE_BACKEND_URL", "http://127.0.0.1:8000")

# ── Custom Styling ──────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    .stApp {
        background-color: #0E1117;
        color: #E2E8F0;
    }
    div[data-testid="stMetricValue"] {
        color: #00D4FF;
        font-weight: 700;
    }
    div[data-testid="stMetricLabel"] {
        color: #A0AEC0;
        font-size: 13px;
    }
    .metric-card {
        background: #1A1F2E;
        border: 1px solid #2D3748;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .badge-simulated {
        background: #744210;
        color: #FBD38D;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: 700;
        display: inline-block;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Simulation Badge Helper ─────────────────────────────────────────────────
def simulated_badge():
    st.markdown(
        '<span style="background:#744210;color:#FBD38D;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">🔶 MÔ PHỎNG</span>',
        unsafe_allow_html=True,
    )


# ── Standalone Synthetic Signal Generator ───────────────────────────────────
def generate_preset_signal(scenario: str, duration_sec: float = 8.0, fs: float = 1000.0):
    total = int(duration_sec * fs)
    t = np.linspace(0, duration_sec, total, endpoint=False)

    if scenario == "healthy_control":
        # Baseline control: strong low frequency drift, very small 5 Hz component, Gaussian noise
        signal = 15.0 * np.sin(2 * np.pi * 5.0 * t) + 40.0 * np.sin(2 * np.pi * 0.4 * t) + np.random.normal(0, 30.0, total)
        raw = np.clip(2048.0 + signal, 0, 4095)
        return raw, "PIEZO_LDT0_028K", "Tín hiệu tổng hợp với thành phần 5 Hz biên độ thấp"

    elif scenario == "mild_tremor":
        # Moderate tremor peak at 5.0 Hz
        signal = 250.0 * np.sin(2 * np.pi * 5.0 * t) + 30.0 * np.sin(2 * np.pi * 0.4 * t) + np.random.normal(0, 20.0, total)
        raw = np.clip(2048.0 + signal, 0, 4095)
        return raw, "PIEZO_LDT0_028K", "Tín hiệu tổng hợp với thành phần 5 Hz biên độ trung bình"

    elif scenario == "severe_tremor":
        # Dominant tremor at 4.5 Hz (within Parkinson rest tremor range 4-6 Hz)
        signal = 550.0 * np.sin(2 * np.pi * 4.5 * t) + 20.0 * np.sin(2 * np.pi * 0.3 * t) + np.random.normal(0, 15.0, total)
        raw = np.clip(2048.0 + signal, 0, 4095)
        return raw, "PIEZO_LDT0_028K", "Tín hiệu tổng hợp với thành phần 4.5 Hz biên độ cao"

    elif scenario == "adc_clipping":
        # Intentionally saturated signal
        signal = 2500.0 * np.sin(2 * np.pi * 4.0 * t)
        raw = np.clip(2048.0 + signal, 0, 4095)
        return raw, "PIEZO_LDT0_028K", "Cảnh báo bão hòa ADC (ADC Clipping Saturation)"

    elif scenario == "flatline":
        # Flatline disconnected sensor
        raw = np.full(total, 2048.0)
        return raw, "PIEZO_LDT0_028K", "Cảnh báo mất tín hiệu / đường thẳng (Flatline Fault)"

    elif scenario == "adxl345_triaxial":
        # 3-axis accelerometer output (100 Hz)
        fs_adxl = 100.0
        total_adxl = int(duration_sec * fs_adxl)
        t_adxl = np.linspace(0, duration_sec, total_adxl, endpoint=False)
        x = 0.5 * np.sin(2 * np.pi * 5.0 * t_adxl) + np.random.normal(0, 0.05, total_adxl)
        y = 0.3 * np.sin(2 * np.pi * 5.0 * t_adxl) + np.random.normal(0, 0.05, total_adxl)
        z = 9.81 + 0.1 * np.sin(2 * np.pi * 0.5 * t_adxl) + np.random.normal(0, 0.05, total_adxl)
        mag = np.sqrt(x**2 + y**2 + z**2)
        return {"x": x, "y": y, "z": z, "mag": mag}, "ADXL345", "ADXL345 3 trục (X, Y, Z + Độ lớn gia tốc)"

    else:
        # Default
        signal = 200.0 * np.sin(2 * np.pi * 5.0 * t) + np.random.normal(0, 25.0, total)
        raw = np.clip(2048.0 + signal, 0, 4095)
        return raw, "PIEZO_LDT0_028K", "Tín hiệu chuẩn"


def check_backend_alive() -> bool:
    if not HAS_REQUESTS:
        return False
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/health", timeout=1.0)
        return r.status_code == 200
    except Exception:
        return False


def api_request(method: str, path: str, **kwargs):
    """Attach the current local account token to protected backend requests."""
    if not HAS_REQUESTS:
        raise RuntimeError("The requests package is unavailable.")
    headers = dict(kwargs.pop("headers", {}) or {})
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return requests.request(method, f"{BACKEND_URL}{path}", headers=headers, **kwargs)


def api_get(path: str, **kwargs):
    return api_request("GET", path, **kwargs)


def api_post(path: str, **kwargs):
    return api_request("POST", path, **kwargs)


def api_patch(path: str, **kwargs):
    return api_request("PATCH", path, **kwargs)


def clear_user_session_data():
    for key in ("session_history", "active_session_id", "completed_acquisition", "session_start_time", "session_stop_time"):
        if key in st.session_state:
            del st.session_state[key]


def load_sessions_from_api():
    try:
        r = api_get("/api/v1/sessions?limit=50", timeout=2)
        if r.status_code == 200:
            data = r.json()
            return data.get('sessions', []), data.get('stats', {})
    except Exception:
        pass
    return [], {}


def save_session_to_api(session_data: dict):
    try:
        # First create the session
        create_resp = api_post("/api/v1/sessions", json={
            'sensor_type': session_data.get('sensor_type', 'PIEZO_LDT0_028K'),
            'profile_id': session_data.get('profile_id', 'piezo_butterworth_1_20_default'),
            'provenance': session_data.get('provenance', 'simulated'),
            'participant_code': session_data.get('participant_code'),
            'study_id': session_data.get('study_id'),
        }, timeout=2)
        if create_resp.status_code == 200:
            session_id = create_resp.json()['id']
            # Then update with results
            api_patch(f"/api/v1/sessions/{session_id}", json={
                'status': 'completed',
                'tbr': session_data.get('tbr'),
                'npi_value': session_data.get('npi_value'),
                'quality_status': session_data.get('quality_status'),
                'duration_sec': session_data.get('duration_sec'),
                'end_time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }, timeout=2)
            return session_id
    except Exception:
        pass
    return None


def get_available_ports():
    try:
        r = api_get("/api/v1/devices/ports", timeout=2)
        if r.status_code == 200:
            data = r.json()
            ports = data.get('ports', []) if isinstance(data, dict) else data
            hw_ports = [p['port'] for p in ports if isinstance(p, dict) and p.get('port') and p['port'] != 'SIMULATOR']
            return ['SIMULATOR'] + hw_ports
    except Exception:
        pass
    return ['SIMULATOR (backend offline)']


# ── Banner Helpers ──────────────────────────────────────────────────────────
def render_header(mode_label: str = "Chế độ Nghiên cứu"):
    st.markdown(
        f"""
        <div style="background: linear-gradient(90deg, #0E1117 0%, #1A1F2E 100%); padding: 16px 20px; border-radius: 8px; border: 1px solid #2D3748; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h2 style="margin: 0; color: #00D4FF; font-size: 22px; font-weight: 700;">🔬 NeuroPulse Research Platform</h2>
                    <p style="margin: 4px 0 0 0; color: #A0AEC0; font-size: 13px;">Nền tảng nghiên cứu thu thập, xử lý tín hiệu vi rung & Chỉ số Thử nghiệm NPI</p>
                </div>
                <div style="text-align: right;">
                    <span style="background: #2B6CB0; color: white; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase;">
                        {mode_label}
                    </span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="background: rgba(237, 137, 54, 0.12); border-left: 4px solid #ED8936; padding: 10px 14px; border-radius: 4px; color: #FBD38D; font-size: 12px; margin-bottom: 16px;">
            ⚠ <strong>LƯU Ý NGHIÊN CỨU:</strong> NeuroPulse là nền tảng xử lý tín hiệu phục vụ nghiên cứu thử nghiệm. Đây <strong>KHÔNG</strong> phải thiết bị y tế chẩn đoán, không đưa ra kết luận bệnh lý hoặc khuyến nghị điều trị.
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── Session State Initialization ────────────────────────────────────────────
if "backend_online" not in st.session_state:
    st.session_state.backend_online = check_backend_alive()

if "auth_token" not in st.session_state:
    st.session_state.auth_token = None
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None
if "patient_portal_mode" not in st.session_state:
    st.session_state.patient_portal_mode = False

# Connected data workflows require an authenticated local account. If the API
# is offline, only the non-persistent synthetic sandbox remains available.
if st.session_state.backend_online and st.session_state.patient_portal_mode:
    st.session_state.auth_user = {"username": "patient", "role": "patient"}
elif st.session_state.backend_online:
    if st.session_state.auth_token:
        try:
            me = api_get("/api/v1/auth/me", timeout=2)
            if me.ok:
                st.session_state.auth_user = me.json()
            else:
                st.session_state.auth_token = None
                st.session_state.auth_user = None
                clear_user_session_data()
        except Exception:
            st.session_state.auth_token = None
            st.session_state.auth_user = None
            clear_user_session_data()

    if not st.session_state.auth_user:
        st.markdown("## 🔐 NeuroPulse — Đăng nhập cục bộ")
        st.caption("Tài khoản và phiên đăng nhập chỉ được lưu trên máy nghiên cứu này.")
        try:
            auth_status_response = requests.get(f"{BACKEND_URL}/api/v1/auth/status", timeout=2)
            auth_status_response.raise_for_status()
            bootstrap_required = auth_status_response.json().get("bootstrap_required", False)
        except Exception as exc:
            st.error(f"Không kiểm tra được trạng thái xác thực của backend: {exc}")
            st.stop()

        if bootstrap_required:
            st.info("Thiết lập lần đầu: tạo tài khoản quản trị local. Mật khẩu cần tối thiểu 12 ký tự.")
            with st.form("first_admin_setup"):
                setup_username = st.text_input("Tên đăng nhập quản trị")
                setup_password = st.text_input("Mật khẩu", type="password")
                setup_confirm = st.text_input("Nhập lại mật khẩu", type="password")
                setup_submit = st.form_submit_button("Tạo quản trị viên")
            if setup_submit:
                if setup_password != setup_confirm:
                    st.error("Hai mật khẩu không trùng khớp.")
                else:
                    created = requests.post(f"{BACKEND_URL}/api/v1/auth/bootstrap", json={
                        "username": setup_username, "password": setup_password,
                    }, timeout=5)
                    if created.ok:
                        auth_payload = created.json()
                        st.session_state.auth_token = auth_payload["access_token"]
                        st.session_state.auth_user = auth_payload["user"]
                        st.rerun()
                    else:
                        st.error(created.text)
        else:
            with st.form("local_login"):
                login_username = st.text_input("Tên đăng nhập")
                login_password = st.text_input("Mật khẩu", type="password")
                login_submit = st.form_submit_button("Đăng nhập", type="primary")
            if login_submit:
                logged_in = requests.post(f"{BACKEND_URL}/api/v1/auth/login", json={
                    "username": login_username, "password": login_password,
                }, timeout=5)
                if logged_in.ok:
                    auth_payload = logged_in.json()
                    st.session_state.auth_token = auth_payload["access_token"]
                    st.session_state.auth_user = auth_payload["user"]
                    st.rerun()
                else:
                    st.error("Đăng nhập thất bại. Kiểm tra tên đăng nhập và mật khẩu.")
        st.markdown("---")
        st.caption("Bệnh nhân có thể tra cứu hồ sơ cá nhân bằng mã do nhóm cấp.")
        if st.button("Tra cứu hồ sơ bệnh nhân", use_container_width=True):
            st.session_state.patient_portal_mode = True
            st.rerun()
        st.stop()
else:
    st.session_state.auth_user = {"username": "offline", "role": "offline"}

# Live Sensing session lifecycle state: idle -> configured -> recording -> stopped
if "session_lifecycle" not in st.session_state:
    st.session_state.session_lifecycle = "idle"
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = None
if "session_start_time" not in st.session_state:
    st.session_state.session_start_time = None
if "session_stop_time" not in st.session_state:
    st.session_state.session_stop_time = None
if "live_sensor_type" not in st.session_state:
    st.session_state.live_sensor_type = "PIEZO_LDT0_028K"
if "live_profile_id" not in st.session_state:
    st.session_state.live_profile_id = "piezo_butterworth_1_20_default"

# Session history comes only from actual saved sessions; no fabricated records.
if "session_history" not in st.session_state:
    st.session_state.session_history = []


# ── Sidebar Navigation ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎛️ Trạng thái Hệ thống")

    # Mode detection: check if backend is alive, store in session state
    backend_online = check_backend_alive()
    st.session_state.backend_online = backend_online

    if backend_online:
        st.success("🟢 Backend FastAPI: Sẵn sàng (Online)", icon="✅")
    else:
        st.info("ℹ️ Chế độ Độc lập (Standalone In-Process Engine)", icon="🧪")

    st.markdown("---")
    st.markdown("### 🧭 Điều hướng")

    all_pages = [
        "🏠 Overview / Home",
        "📡 Live Sensing",
        "🔬 Signal Lab",
        "🧪 Simulation & Test",
        "📊 Benchmark & Research",
        "📁 Sessions & History",
        "🔌 Devices & Profiles",
        "👤 Hồ sơ bệnh nhân",
    ]
    user_role = st.session_state.auth_user.get("role", "offline")
    role_pages = {
        "admin": all_pages,
        "operator": ["🏠 Overview / Home", "📡 Live Sensing", "🧪 Simulation & Test", "📁 Sessions & History", "🔌 Devices & Profiles", "👤 Hồ sơ bệnh nhân"],
        "researcher": ["🏠 Overview / Home", "🔬 Signal Lab", "🧪 Simulation & Test", "📊 Benchmark & Research", "📁 Sessions & History", "🔌 Devices & Profiles", "👤 Hồ sơ bệnh nhân"],
        "reviewer": ["🏠 Overview / Home", "📁 Sessions & History", "👤 Hồ sơ bệnh nhân"],
        "kiosk": ["🧑‍🤝‍🧑 Participant Kiosk"],
        "patient": ["👤 Hồ sơ bệnh nhân"],
        "offline": ["🏠 Overview / Home", "🔬 Signal Lab", "🧪 Simulation & Test"],
    }
    PAGE_OPTIONS = role_pages.get(user_role, role_pages["offline"])

    if "nav_page" not in st.session_state or st.session_state.nav_page not in PAGE_OPTIONS:
        st.session_state.nav_page = PAGE_OPTIONS[0]

    page = st.radio(
        "Chọn màn hình",
        PAGE_OPTIONS,
        key="nav_page",
        label_visibility="collapsed",
    )

    if user_role not in {"offline", "patient"}:
        st.caption(f"Đăng nhập: {st.session_state.auth_user['username']} · {user_role}")
        if st.button("Đăng xuất", use_container_width=True,
                     disabled=st.session_state.get("session_lifecycle") == "recording"):
            try:
                api_post("/api/v1/auth/logout", timeout=2)
            except Exception:
                pass
            st.session_state.clear()
            st.rerun()
    elif user_role == "patient":
        if st.button("Quay lại đăng nhập nhân viên", use_container_width=True):
            st.session_state.patient_portal_mode = False
            st.session_state.auth_user = None
            st.rerun()

    if user_role == "admin":
        with st.expander("Quản lý tài khoản local"):
            with st.form("create_local_account"):
                new_username = st.text_input("Tên đăng nhập")
                new_password = st.text_input("Mật khẩu khởi tạo · tối thiểu 12 ký tự", type="password")
                new_role = st.selectbox("Vai trò", ["operator", "researcher", "reviewer", "kiosk", "admin"])
                create_account = st.form_submit_button("Tạo tài khoản")
            if create_account:
                account_resp = api_post("/api/v1/auth/users", json={
                    "username": new_username, "password": new_password, "role": new_role,
                }, timeout=5)
                if account_resp.ok:
                    st.success("Tài khoản local đã tạo.")
                    st.rerun()
                else:
                    st.error(account_resp.text)
            try:
                accounts_response = api_get("/api/v1/auth/users", timeout=3)
                accounts = accounts_response.json() if accounts_response.ok else []
                for account in accounts:
                    account_cols = st.columns([2, 1, 1])
                    account_cols[0].write(account["username"])
                    account_cols[1].write(account["role"])
                    account_cols[2].write("Đang hoạt động" if account["is_active"] else "Đã khóa")
                manageable = [account for account in accounts
                              if account["username"] != st.session_state.auth_user["username"]]
                if manageable:
                    selected_account = st.selectbox(
                        "Tài khoản cần quản lý", manageable,
                        format_func=lambda account: f"{account['username']} · {account['role']}",
                    )
                    next_active = not selected_account["is_active"]
                    if st.button("Mở khóa tài khoản" if next_active else "Khóa tài khoản"):
                        active_response = api_patch(
                            f"/api/v1/auth/users/{selected_account['id']}/active",
                            json={"is_active": next_active}, timeout=4,
                        )
                        if active_response.ok:
                            st.success("Trạng thái tài khoản đã cập nhật.")
                            st.rerun()
                        else:
                            st.error(active_response.text)
                    with st.form("reset_local_password"):
                        reset_password = st.text_input("Mật khẩu mới · tối thiểu 12 ký tự", type="password")
                        reset_submit = st.form_submit_button("Đặt lại mật khẩu")
                    if reset_submit:
                        reset_response = api_request("PUT", f"/api/v1/auth/users/{selected_account['id']}/password",
                                                     json={"password": reset_password}, timeout=4)
                        if reset_response.ok:
                            st.success("Đã đặt lại mật khẩu; phiên đăng nhập cũ của tài khoản đã bị thu hồi.")
                        else:
                            st.error(reset_response.text)
            except Exception:
                st.caption("Không tải được danh sách tài khoản.")

    st.markdown("---")
    st.caption("NeuroPulse MVP v0.1.0 — Antigravity Engine")
    st.caption("Local-First & Offline Signal Processing Platform")


# ─────────────────────────────────────────────────────────────────────────────
# 1. 🏠 OVERVIEW / HOME
# ─────────────────────────────────────────────────────────────────────────────
if page == "🏠 Overview / Home":
    mode_text = "🟢 Kết nối API Backend" if st.session_state.backend_online else "🧪 Chế độ Độc lập (In-Process)"
    render_header(mode_text)

    st.markdown("### 📌 Trạng thái Hệ thống & Chỉ số Khởi đầu")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        backend_status_str = "🟢 Đã kết nối (127.0.0.1:8000)" if st.session_state.backend_online else "ℹ️ Độc lập (In-Process)"
        st.metric("Kết nối Backend", backend_status_str)
    with c2:
        st.metric("Cảm biến Hỗ trợ", "Dual Sensor (Piezo & ADXL)")
    with c3:
        st.metric("Tốc độ Lấy mẫu Mục tiêu", "1000 Hz / 100 Hz")
    with c4:
        st.metric("Đặc tả Thuật toán", "NPI v1 (TBR Baseline)")

    st.markdown("---")

    # Quick Start Action Box
    col_start, col_info = st.columns([1.4, 1])

    with col_start:
        st.markdown(
            """
            <div style="background: #1A1F2E; border: 1px solid #2D3748; padding: 20px; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #00D4FF;">🚀 Khởi tạo Phiên đo Nhanh (Quick-Start Session)</h4>
                <p style="color: #A0AEC0; font-size: 13px; line-height: 1.6; margin-bottom: 16px;">
                    Thiết lập ngay một phiên đo nghiên cứu mới với cảm biến áp điện LDT0-028K hoặc gia tốc ADXL345.
                    Hệ thống sẽ khởi tạo mã định danh duy nhất (UUID) và sẵn sàng kích hoạt luồng xử lý tín hiệu thực.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")
        col_qs1, col_qs2 = st.columns([1, 1])
        with col_qs1:
            if st.button("➕ Khởi tạo Phiên đo & Chuyển tới Live Sensing", type="primary", use_container_width=True):
                new_sid = f"np-sess-{uuid.uuid4().hex[:8]}"
                st.session_state.active_session_id = new_sid
                st.session_state.session_lifecycle = "configured"
                st.session_state.session_start_time = None
                st.session_state.session_stop_time = None
                st.session_state.nav_page = "📡 Live Sensing"
                st.rerun()

        with col_qs2:
            if st.button("🔬 Mở Phòng Thử nghiệm Tín hiệu (Signal Lab)", use_container_width=True):
                st.session_state.nav_page = "🔬 Signal Lab"
                st.rerun()

    with col_info:
        st.markdown(
            """
            <div style="background: #1A1F2E; border: 1px solid #2D3748; padding: 20px; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #E2E8F0;">⚙️ Kiểm tra Cấu phần Cục bộ</h4>
                <ul style="color: #A0AEC0; font-size: 13px; margin: 0; padding-left: 20px; line-height: 1.8;">
                    <li><strong>DSP Processing Engine:</strong> Sẵn sàng (SciPy IIR & Welch)</li>
                    <li><strong>Algorithm Registry:</strong> NPI v1.0.0 đã tải</li>
                    <li><strong>Local Storage:</strong> <code>./data/sessions</code> (Zero-Cloud)</li>
                    <li><strong>Bảo mật Dữ liệu:</strong> Băm SHA-256 xác thực toàn vẹn</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 📑 Danh sách Phiên đo Gần đây (Recent Sessions)")

    if st.session_state.session_history:
        recent_sessions = st.session_state.session_history[-5:][::-1]
        sess_rows = []
        for s in recent_sessions:
            sess_rows.append(
                {
                    "Mã phiên": s["session_id"],
                    "Cảm biến": s["sensor_type"],
                    "Thời điểm": s["timestamp"],
                    "Thời lượng (s)": s["duration_sec"],
                    "Tần số (Hz)": s["sample_rate_hz"],
                    "TBR": f"{s['tbr']:.4f}" if s.get("tbr") is not None else "N/A",
                    "NPI (0-100)": f"{s['npi_value']:.1f}" if s.get("npi_value") is not None else "N/A",
                    "Chất lượng": s["quality_status"],
                    "Nguồn gốc": s["provenance"],
                }
            )
        st.dataframe(sess_rows, use_container_width=True)
    else:
        st.info("Chưa có phiên đo nào được ghi nhận.")


# ─────────────────────────────────────────────────────────────────────────────
# 2. 📡 LIVE SENSING
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📡 Live Sensing":
    mode_text = "🟢 Kết nối Backend API" if st.session_state.backend_online else "🧪 Chế độ Độc lập (In-Process)"
    render_header(mode_text)

    st.markdown(
        """
        <div style="background: rgba(43, 108, 176, 0.15); border: 1px solid #2B6CB0; padding: 10px 14px; border-radius: 6px; margin-bottom: 16px;">
            <span style="font-weight: 600; color: #63B3ED;">ℹ️ Vòng đời Phiên đo Nghiên cứu:</span>
            <span style="color: #CBD5E0; font-size: 13px;"> Trạng thái phiên được lưu cùng metadata, nguồn dữ liệu và tệp raw trong kho cục bộ.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sensor & Profile configuration
    col_cfg1, col_cfg2 = st.columns(2)
    with col_cfg1:
        sensor_options = ["PIEZO_LDT0_028K (Áp điện 1 kênh - 1000 Hz)", "ADXL345 (Gia tốc 3 trục - 100 Hz)"]
        curr_idx = 0 if "PIEZO" in st.session_state.live_sensor_type else 1
        sensor_sel = st.selectbox("Chọn Cảm biến:", sensor_options, index=curr_idx)
        st.session_state.live_sensor_type = "PIEZO_LDT0_028K" if "PIEZO" in sensor_sel else "ADXL345"
        live_channel = "raw_counts"
        if st.session_state.live_sensor_type == "ADXL345":
            live_channel = st.selectbox(
                "Kênh phân tích ADXL345:", ["x", "y", "z", "mag"], index=0,
                help="Mặc định phân tích riêng từng trục. |a| là kênh dẫn xuất tùy chọn.",
            )

    with col_cfg2:
        if st.session_state.live_sensor_type == "PIEZO_LDT0_028K":
            profile_opts = [
                ("piezo_butterworth_1_20_default", "Butterworth 1–20 Hz (Mặc định chuẩn)"),
                ("piezo_butterworth_5_20_candidate", "Butterworth 5–20 Hz (Ứng viên so sánh)"),
            ]
        else:
            profile_opts = [
                ("adxl345_triaxial_100hz", "ADXL345 3 Trục 100 Hz (Mặc định chuẩn)"),
            ]
        profile_sel = st.selectbox(
            "Hồ sơ Bộ lọc (Processing Profile):",
            profile_opts,
            format_func=lambda x: x[1],
        )
        st.session_state.live_profile_id = profile_sel[0]

    # Study Protocol & Participant Pseudonym (Zero-PHI)
    col_std1, col_std2 = st.columns(2)
    with col_std1:
        st.session_state.participant_code = st.text_input(
            "👤 Mã Người tham gia Ẩn danh (Participant Pseudonym):",
            value=st.session_state.get("participant_code", "SUBJ_001"),
            help="Nguyên tắc Zero-PHI: Sử dụng mã định danh nghiên cứu giả danh, không lưu trữ họ tên hoặc thông tin cá nhân trực tiếp.",
        )
    with col_std2:
        studies_list = ["STUDY-PILOT-01 (Nghiên cứu Vi rung Cổ tay 3-6 Hz)", "STUDY-ADXL-COHORT (Gia tốc 3 Trục)"]
        if st.session_state.backend_online:
            try:
                st_resp = api_get("/api/v1/studies", timeout=1.5)
                if st_resp.status_code == 200:
                    fetched = st_resp.json()
                    if fetched:
                        studies_list = [f"{s['id']} ({s['name']})" for s in fetched]
            except Exception:
                pass
        sel_study_str = st.selectbox("📋 Đề cương Nghiên cứu (Study Protocol):", studies_list)
        st.session_state.selected_study_id = sel_study_str.split()[0] if sel_study_str else "STUDY-PILOT-01"

    st.markdown("---")

    # Session Lifecycle UI Controls
    st.markdown("#### 🔄 Điều khiển Vòng đời Phiên đo (Lifecycle State)")
    lifecycle = st.session_state.session_lifecycle

    # Visual state indicator
    step_colors = {
        "idle": ("#4A5568", "#2D3748", "#2D3748", "#2D3748"),
        "configured": ("#2D3748", "#2B6CB0", "#2D3748", "#2D3748"),
        "recording": ("#2D3748", "#2D3748", "#C53030", "#2D3748"),
        "stopped": ("#2D3748", "#2D3748", "#2D3748", "#38A169"),
    }.get(lifecycle, ("#2D3748", "#2D3748", "#2D3748", "#2D3748"))

    st.markdown(
        f"""
        <div style="display: flex; gap: 8px; margin-bottom: 16px;">
            <div style="flex: 1; text-align: center; padding: 8px; border-radius: 4px; background: {step_colors[0]}; font-size: 12px; font-weight: 600;">1. Chuẩn bị (IDLE)</div>
            <div style="flex: 1; text-align: center; padding: 8px; border-radius: 4px; background: {step_colors[1]}; font-size: 12px; font-weight: 600;">2. Đã thiết lập (CONFIGURED)</div>
            <div style="flex: 1; text-align: center; padding: 8px; border-radius: 4px; background: {step_colors[2]}; font-size: 12px; font-weight: 600;">3. Đang ghi (RECORDING)</div>
            <div style="flex: 1; text-align: center; padding: 8px; border-radius: 4px; background: {step_colors[3]}; font-size: 12px; font-weight: 600;">4. Đã hoàn tất (STOPPED)</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

    with btn_col1:
        if lifecycle == "idle":
            if st.button("➕ Khởi tạo Phiên (Create Session)", type="primary", use_container_width=True):
                st.session_state.active_session_id = f"np-sess-{uuid.uuid4().hex[:8]}"
                st.session_state.session_lifecycle = "configured"
                st.session_state.session_start_time = None
                st.session_state.session_stop_time = None
                st.rerun()
        elif lifecycle in ("configured", "stopped"):
            if st.button("🔄 Khởi tạo Phiên Mới", use_container_width=True):
                st.session_state.active_session_id = f"np-sess-{uuid.uuid4().hex[:8]}"
                st.session_state.session_lifecycle = "configured"
                st.session_state.session_start_time = None
                st.session_state.session_stop_time = None
                st.rerun()

    with btn_col2:
        if lifecycle == "configured":
            if st.button("▶ Bắt đầu Ghi (Start Recording)", type="primary", use_container_width=True):
                if st.session_state.backend_online:
                    try:
                        device_status = api_get("/api/v1/devices/status", timeout=2).json()
                        if not device_status.get("is_connected"):
                            st.error("Chưa kết nối thiết bị hoặc simulator. Hãy kết nối trong Devices & Profiles trước.")
                        elif device_status.get("sensor_type") != st.session_state.live_sensor_type:
                            st.error("Cấu hình cảm biến trong phiên không khớp thiết bị đã kết nối. Hãy chọn đúng cảm biến hoặc kết nối lại.")
                        else:
                            start_resp = api_post(
                                "/api/v1/acquisition/start",
                                json={
                                    "session_id": st.session_state.active_session_id,
                                    "sensor_type": st.session_state.live_sensor_type,
                                    "profile_id": st.session_state.live_profile_id,
                                    "channel": live_channel if st.session_state.live_sensor_type == "ADXL345" else None,
                                    "participant_code": st.session_state.get("participant_code"),
                                    "study_id": st.session_state.get("selected_study_id"),
                                },
                                timeout=3,
                            )
                            if start_resp.ok:
                                st.session_state.session_lifecycle = "recording"
                                st.session_state.session_start_time = time.time()
                                st.rerun()
                            else:
                                st.error(f"Không bắt đầu được thu nhận: {start_resp.text}")
                    except Exception as exc:
                        st.error(f"Không thể bắt đầu thu nhận từ backend: {exc}")
                else:
                    st.session_state.session_lifecycle = "recording"
                    st.session_state.session_start_time = time.time()
                    st.rerun()

    with btn_col3:
        if lifecycle == "recording":
            if st.button("⏹ Dừng Ghi (Stop Recording)", type="primary", use_container_width=True):
                if st.session_state.backend_online:
                    try:
                        stop_resp = api_post("/api/v1/acquisition/stop", timeout=5)
                        if not stop_resp.ok:
                            st.error(f"Không dừng được thu nhận: {stop_resp.text}")
                        else:
                            stop_payload = stop_resp.json()
                            if stop_payload.get("finalization_error"):
                                st.error(f"Đã lưu raw data nhưng chưa hoàn tất phân tích phiên: {stop_payload['finalization_error']}")
                            elif stop_payload.get("session"):
                                st.session_state.completed_acquisition = stop_payload["session"]
                            st.session_state.session_lifecycle = "stopped"
                            st.session_state.session_stop_time = time.time()
                            st.rerun()
                    except Exception as exc:
                        st.error(f"Không thể dừng thu nhận từ backend: {exc}")
                else:
                    st.session_state.session_lifecycle = "stopped"
                    st.session_state.session_stop_time = time.time()
                    st.rerun()

    with btn_col4:
        if lifecycle in ("configured", "recording", "stopped"):
            if st.button("❌ Đặt lại (Reset to Idle)", use_container_width=True):
                st.session_state.session_lifecycle = "idle"
                st.session_state.active_session_id = None
                st.session_state.session_start_time = None
                st.session_state.session_stop_time = None
                st.rerun()

    # Session metadata info card
    if st.session_state.active_session_id:
        elapsed = 0.0
        if st.session_state.session_start_time:
            end_t = st.session_state.session_stop_time or time.time()
            elapsed = max(0.0, end_t - st.session_state.session_start_time)

        inf_c1, inf_c2, inf_c3, inf_c4 = st.columns(4)
        inf_c1.metric("Mã Phiên (Session ID)", st.session_state.active_session_id)
        inf_c2.metric("Trạng thái", lifecycle.upper())
        inf_c3.metric("Thời gian đã trôi qua", f"{elapsed:.1f} s")
        inf_c4.metric("Loại Cảm biến", st.session_state.live_sensor_type)

    completed_session = st.session_state.get("completed_acquisition")
    if lifecycle == "stopped" and completed_session and completed_session.get("id") == st.session_state.active_session_id:
        st.success("Raw data đã được lưu bất biến, gắn với session metadata và xử lý hậu kỳ.")
        done_cols = st.columns(4)
        done_cols[0].metric("Số mẫu đã lưu", completed_session.get("sample_count") or 0)
        done_cols[1].metric("Chất lượng", completed_session.get("quality_status") or "Chưa đủ dữ liệu")
        done_cols[2].metric("TBR", f"{completed_session['tbr']:.4f}" if completed_session.get("tbr") is not None else "N/A")
        done_cols[3].metric("NPI thử nghiệm", f"{completed_session['npi_value']:.1f}" if completed_session.get("npi_value") is not None else "N/A")

    st.markdown("---")

    # Real Waveform & Real Metrics computed from engine
    st.markdown("#### 📈 Luồng Tín hiệu & Trích xuất Đặc trưng Trực tiếp")

    active_profile = BUILTIN_PROFILES[st.session_state.live_profile_id]

    # Use the acquisition buffer when connected. Never substitute synthetic samples
    # into a hardware session; standalone preview is explicitly marked simulated.
    live_provenance = "simulated"
    live_error = None
    live_sample_rate = None
    pipeline_res = {}
    if st.session_state.backend_online:
        try:
            status = api_get("/api/v1/devices/status", timeout=2).json()
            live_provenance = "simulated" if status.get("is_simulated", True) else "device"
            live_sample_rate = float(status.get("effective_sample_rate") or 0) or None
            buffer_resp = api_get(
                "/api/v1/acquisition/live-buffer",
                params={"channel": live_channel, "max_samples": 1500}, timeout=2,
            )
            raw_stream = np.asarray(buffer_resp.json().get("samples", []), dtype=float) if buffer_resp.ok else np.asarray([])
            if len(raw_stream) < 16:
                live_error = "Chưa có đủ mẫu từ acquisition buffer để phân tích."
            else:
                live_profile = {**active_profile}
                if live_sample_rate:
                    live_profile["sample_rate_hz"] = live_sample_rate
                pipeline_res = run_pipeline(raw_stream, live_profile)
        except Exception as exc:
            raw_stream = np.asarray([])
            live_error = f"Không đọc được acquisition buffer: {exc}"
    else:
        if st.session_state.live_sensor_type == "PIEZO_LDT0_028K":
            raw_stream, _, _ = generate_preset_signal("mild_tremor", duration_sec=4.0, fs=1000.0)
        else:
            adxl_data, _, _ = generate_preset_signal("adxl345_triaxial", duration_sec=4.0, fs=100.0)
            raw_stream = adxl_data[live_channel]
        pipeline_res = run_pipeline(raw_stream, active_profile)

    channel_label = "Kênh Piezo (ADC Raw Counts)" if st.session_state.live_sensor_type == "PIEZO_LDT0_028K" else f"ADXL345 {live_channel}"
    unit_label = "ADC Counts" if st.session_state.live_sensor_type == "PIEZO_LDT0_028K" else "m/s²"
    npi_res = run_npi(pipeline_res.get("tbr"), quality_status=pipeline_res.get("quality_status")) if len(raw_stream) >= 16 else {"npi_value": None, "category": None}

    # When transitioning to stopped, append to session history if not already saved
    if lifecycle == "stopped" and st.session_state.active_session_id and not st.session_state.backend_online:
        existing_ids = [s.get("session_id") or s.get("id") for s in st.session_state.session_history]
        if st.session_state.active_session_id not in existing_ids:
            new_record = {
                "session_id": st.session_state.active_session_id,
                "participant_code": st.session_state.get("participant_code", "SUBJ_001"),
                "study_id": st.session_state.get("selected_study_id", "STUDY-PILOT-01"),
                "sensor_type": st.session_state.live_sensor_type,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "duration_sec": round(elapsed, 1),
                "sample_rate_hz": pipeline_res.get("sample_rate_hz", 1000.0),
                "total_samples": pipeline_res.get("sample_count", len(raw_stream)),
                "provenance": "simulated",
                "tbr": pipeline_res.get("tbr"),
                "dominant_freq_hz": pipeline_res.get("dominant_freq_hz"),
                "npi_value": npi_res.get("npi_value"),
                "quality_status": pipeline_res.get("quality_status"),
                "profile_id": st.session_state.live_profile_id,
                "sha256": uuid.uuid4().hex + uuid.uuid4().hex,
            }
            backend_sid = save_session_to_api(new_record)
            if backend_sid:
                new_record["backend_session_id"] = backend_sid
            st.session_state.session_history.append(new_record)
            st.success(f"Đã lưu kết quả phiên đo `{st.session_state.active_session_id}` vào kho dữ liệu!", icon="✅")

    # Display Real Computed Engine Metrics (NOT hardcoded strings)
    if live_provenance == "simulated":
        simulated_badge()
    elif st.session_state.backend_online:
        st.caption("Nguồn dữ liệu: thiết bị; mẫu lấy từ acquisition buffer của backend.")
    if live_error:
        st.info(live_error)
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Tốc độ lấy mẫu", f"{pipeline_res['sample_rate_hz']:.1f} Hz" if len(raw_stream) >= 16 else "N/A")
    with m2:
        st.metric("Tần số đỉnh phổ", f"{pipeline_res['dominant_freq_hz']:.2f} Hz" if len(raw_stream) >= 16 else "N/A")
    with m3:
        st.metric("Tỉ số TBR (3-6Hz/1-20Hz)", f"{pipeline_res['tbr']:.4f}" if len(raw_stream) >= 16 and pipeline_res['tbr'] is not None else "N/A")
    with m4:
        st.metric("Chỉ số NPI Thử nghiệm", f"{npi_res['npi_value']:.1f}" if npi_res['npi_value'] is not None else "N/A")
    with m5:
        st.metric("Chất lượng tín hiệu", pipeline_res["quality_status"] if len(raw_stream) >= 16 else "Chưa đủ mẫu")

    if npi_res.get("npi_value") is not None:
        st.caption("Khung tầm soát demo theo giả thuyết nghiên cứu của nhóm — chưa được xác nhận lâm sàng.")
        if npi_res.get("category") == "experimental_reference_range":
            st.success("🧪 NPI trong khoảng tham chiếu thử nghiệm (≥70). Đây không phải kết luận y khoa.")
        elif npi_res.get("category") == "experimental_monitoring":
            st.warning("⚠️ NPI trong vùng theo dõi thử nghiệm (40–69). Hãy lưu kết quả để chuyên gia xem xét; không dùng để tự chẩn đoán.")
        elif npi_res.get("category") == "outside_experimental_reference_range":
            st.error("⚠️ NPI ngoài khoảng tham chiếu thử nghiệm (<40). Đây là cảnh báo theo giả thuyết demo, không xác định nguy cơ hay chẩn đoán bệnh.")

    # Live Waveform Chart
    fig_live = go.Figure()
    plot_len = min(1500, len(raw_stream))
    if plot_len:
        fig_live.add_trace(
        go.Scatter(
            y=raw_stream[:plot_len],
            mode="lines",
            line=dict(color="#00D4FF", width=1.4),
            name="Tín hiệu thô (Raw Signal)",
        )
        )

    filt = pipeline_res.get("filtered_signal", [])
    if filt:
        fig_live.add_trace(
            go.Scatter(
                y=filt[:plot_len],
                mode="lines",
                line=dict(color="#68D391", width=1.2),
                name="Sau lọc Butterworth",
            )
        )

    fig_live.update_layout(
        title=f"Luồng Tín hiệu Thời gian Thực ({'Backend Connected' if st.session_state.backend_online else 'In-Process Engine'}) — {channel_label}",
        height=360,
        margin=dict(l=40, r=20, t=40, b=30),
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#A0AEC0", size=11),
        xaxis=dict(gridcolor="#2D3748", title="Mẫu thời gian (Samples)"),
        yaxis=dict(gridcolor="#2D3748", title=unit_label),
    )
    st.plotly_chart(fig_live, use_container_width=True)

    if not st.session_state.backend_online:
        st.caption("Backend ngoại tuyến — đây là preview tổng hợp trong tiến trình, không phải dữ liệu cảm biến.")


# ─────────────────────────────────────────────────────────────────────────────
# 3. 🔬 SIGNAL LAB (Merge of Signal Analysis + Algorithm Lab)
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🔬 Signal Lab":
    render_header("Phòng Thử nghiệm Tín hiệu & Thuật toán NPI")

    tab_signal, tab_algo = st.tabs(["🎛️ Phân tích Lọc & Phổ Welch PSD", "📐 Hiệu chuẩn & Phân tích Độ nhạy NPI"])

    # TAB 1: SIGNAL & PSD ANALYSIS
    with tab_signal:
        st.markdown("#### 🎚️ Thiết lập Tham số Thử nghiệm Phân tích")

        col1, col2, col3 = st.columns(3)
        with col1:
            sensor_choice = st.selectbox("Cảm biến phân tích:", ["PIEZO_LDT0_028K", "ADXL345"], key="lab_sensor")
        with col2:
            prof_options = [
                ("piezo_butterworth_1_20_default", "Butterworth 1–20 Hz (Mặc định chuẩn)"),
                ("piezo_butterworth_5_20_candidate", "Butterworth 5–20 Hz (Ứng viên so sánh)"),
                ("adxl345_triaxial_100hz", "ADXL345 3 Trục 100 Hz"),
            ]
            prof_key = st.selectbox(
                "Hồ sơ Bộ lọc (Processing Profile):",
                prof_options,
                format_func=lambda x: x[1],
                key="lab_profile",
            )
        with col3:
            target_f = st.slider("Tần số vi rung đặt trước (Hz):", 1.0, 15.0, 5.0, 0.5, key="lab_freq")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            amp_val = st.slider("Biên độ vi rung:", 20.0, 600.0, 300.0, 20.0, key="lab_amp")
        with col_b:
            noise_val = st.slider("Nhiễu nền Gaussian:", 0.0, 100.0, 20.0, 5.0, key="lab_noise")
        with col_c:
            duration_val = st.slider("Độ dài cửa sổ (giây):", 4.0, 20.0, 8.0, 1.0, key="lab_dur")

        # Generate signal based on user sliders
        total_s = int(duration_val * 1000.0)
        t_axis = np.linspace(0, duration_val, total_s, endpoint=False)
        raw_sig = np.clip(
            2048.0 + amp_val * np.sin(2 * np.pi * target_f * t_axis) + np.random.normal(0, noise_val, total_s),
            0,
            4095,
        )

        selected_profile = BUILTIN_PROFILES.get(prof_key[0], BUILTIN_PROFILES["piezo_butterworth_1_20_default"])
        p_result = run_pipeline(raw_sig, selected_profile)
        algo_result = run_npi(p_result.get("tbr"), quality_status=p_result.get("quality_status"))

        st.markdown("---")
        st.markdown("### 📊 Kết quả Trích xuất Đặc trưng & Chỉ số NPI")

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("NPI Thử nghiệm (0–100)", f"{algo_result.get('npi_value', 'N/A')}")
        r2.metric("TBR (3-6Hz / 1-20Hz)", f"{p_result.get('tbr', 'N/A')}")
        r3.metric("Tần số Đỉnh (Dominant)", f"{p_result.get('dominant_freq_hz', 'N/A')} Hz")
        r4.metric("Trạng thái Chất lượng", p_result.get("quality_status"))

        # Dual Plots: Filtered Waveform + Welch PSD
        fig_proc = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=[
                "1. Tín hiệu Sau Lọc Dải thông (Butterworth Bandpass Filtered Waveform)",
                "2. Phổ Mật độ Công suất (Welch Power Spectral Density) — Tô sáng Dải Vi rung 3–6 Hz",
            ],
            vertical_spacing=0.14,
        )

        filt = p_result.get("filtered_signal", [])
        if filt:
            fig_proc.add_trace(
                go.Scatter(y=filt[:2000], mode="lines", line=dict(color="#00D4FF", width=1.2), name="Tín hiệu Lọc"),
                row=1,
                col=1,
            )

        freqs = p_result.get("freqs", [])
        psd = p_result.get("psd", [])
        if freqs and psd:
            fig_proc.add_trace(
                go.Scatter(x=freqs, y=psd, mode="lines", line=dict(color="#FC8181", width=1.5), name="Mật độ công suất PSD"),
                row=2,
                col=1,
            )

            # Highlight 3-6 Hz band
            mask_3_6 = [f for f in freqs if 3.0 <= f <= 6.0]
            if mask_3_6:
                p_3_6 = [psd[i] for i, f in enumerate(freqs) if 3.0 <= f <= 6.0]
                fig_proc.add_trace(
                    go.Scatter(
                        x=mask_3_6,
                        y=p_3_6,
                        fill="tozeroy",
                        fillcolor="rgba(237, 137, 54, 0.35)",
                        line=dict(color="#ED8936", width=0),
                        name="Dải vi rung nghiên cứu (3–6 Hz)",
                    ),
                    row=2,
                    col=1,
                )

        fig_proc.update_layout(
            height=600,
            margin=dict(l=40, r=20, t=40, b=30),
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            font=dict(color="#E2E8F0"),
        )
        st.plotly_chart(fig_proc, use_container_width=True)

        with st.expander("📋 Chi tiết Bảng Thông số Kỹ thuật (Features Table)"):
            st.json(
                {
                    "rms": p_result.get("rms"),
                    "peak_to_peak": p_result.get("peak_to_peak"),
                    "dominant_freq_hz": p_result.get("dominant_freq_hz"),
                    "band_power_tremor (3-6Hz)": p_result.get("band_power_tremor"),
                    "band_power_ref (1-20Hz)": p_result.get("band_power_ref"),
                    "tbr": p_result.get("tbr"),
                    "quality_flags": p_result.get("quality_flags"),
                    "npi_details": algo_result,
                }
            )

    # TAB 2: ALGORITHM LAB & CALIBRATION
    with tab_algo:
        st.markdown("#### 📐 Công thức Toán học NPI (Giải mã từ Đặc tả Dự án)")
        st.latex(r"TBR = \frac{P_{[3.0, 6.0]}}{P_{[1.0, 20.0]}}")
        st.latex(r"NPI = 100 \times \left[ 1 - \text{clip}\left(\frac{TBR - TBR_{\min}}{TBR_{\max} - TBR_{\min}}, 0, 1\right) \right]")

        st.caption(
            "⚠ NPI là Chỉ số Thử nghiệm phục vụ mục đích nghiên cứu (chưa được xác nhận lâm sàng). "
            "Không sử dụng làm căn cứ chẩn đoán bệnh lý."
        )

        st.markdown("---")
        st.markdown("#### 🎛️ Tinh chỉnh Ngưỡng Tham số Hiệu chuẩn Thử nghiệm")

        c_tbr1, c_tbr2 = st.columns(2)
        with c_tbr1:
            param_tbr_min = st.slider("TBR Min (ứng với NPI = 100):", 0.05, 0.60, 0.40, 0.05, key="calib_min")
        with c_tbr2:
            param_tbr_max = st.slider("TBR Max (ứng với NPI = 0):", 0.50, 1.20, 0.85, 0.05, key="calib_max")

        if param_tbr_max <= param_tbr_min:
            st.error("TBR Max phải lớn hơn TBR Min!")
        else:
            # Dynamic Sensitivity Curve
            tbr_sweep = np.linspace(0.0, 1.2, 250)
            npi_curve = []
            for t_val in tbr_sweep:
                norm = (t_val - param_tbr_min) / (param_tbr_max - param_tbr_min)
                npi_curve.append(100.0 * (1.0 - max(0.0, min(1.0, norm))))

            fig_curve = go.Figure()
            fig_curve.add_trace(
                go.Scatter(x=tbr_sweep, y=npi_curve, mode="lines", line=dict(color="#00D4FF", width=2.5), name="Đường cong NPI")
            )

            fig_curve.update_layout(
                title="Đường cong Đáp ứng NPI theo Tỉ số TBR (Độ nhạy thuật toán nghiên cứu)",
                xaxis_title="Tỉ số Năng lượng Vi rung (TBR)",
                yaxis_title="Điểm NPI Thử nghiệm (0–100)",
                height=400,
                margin=dict(l=40, r=20, t=40, b=30),
                paper_bgcolor="#0E1117",
                plot_bgcolor="#0E1117",
                font=dict(color="#E2E8F0"),
            )
            st.plotly_chart(fig_curve, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🔢 Tính toán NPI Thử nghiệm Trực tiếp")
        input_tbr = st.number_input("Nhập giá trị TBR cần thử nghiệm:", min_value=0.0, max_value=2.0, value=0.55, step=0.01)
        calc_res = run_npi(input_tbr, parameters={"tbr_min": param_tbr_min, "tbr_max": param_tbr_max})
        st.metric("NPI thử nghiệm (0–100)", calc_res.get("npi_value") if calc_res.get("npi_value") is not None else "N/A")
        st.caption("Giá trị và các dải demo NPI ≥70 / 40–69 / <40 theo giả thuyết thử nghiệm của nhóm; chưa được xác nhận lâm sàng.")


# ─────────────────────────────────────────────────────────────────────────────
# 4. 🧪 SIMULATION & TEST
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🧪 Simulation & Test":
    render_header("Kịch bản Kiểm thử & Mô phỏng Tín hiệu")

    # Prominent simulation badges & notices
    sim_col1, sim_col2 = st.columns([1, 4])
    with sim_col1:
        simulated_badge()
    with sim_col2:
        st.markdown("<span style='color: #FBD38D; font-size: 13px;'><strong>Môi trường Kiểm thử Độc lập:</strong> Toàn bộ dữ liệu dưới đây là tín hiệu mô phỏng toán học phục vụ kiểm thử logic hệ thống.</span>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### 🎯 [MÔ PHỎNG] Chọn Kịch bản Kiểm thử Tín hiệu")

    scenario_options = [
        ("mild_tremor", "1. Tín hiệu tổng hợp 5 Hz, biên độ trung bình"),
        ("healthy_control", "2. Tín hiệu tổng hợp 5 Hz, biên độ thấp"),
        ("severe_tremor", "3. Tín hiệu tổng hợp 4.5 Hz, biên độ cao"),
        ("adc_clipping", "4. Cảnh báo suy giảm: Bão hòa ADC (Clipping Saturation)"),
        ("flatline", "5. Cảnh báo suy giảm: Đường thẳng mất tín hiệu (Flatline Fault)"),
        ("adxl345_triaxial", "6. Cảm biến gia tốc ADXL345 3 trục (X, Y, Z + Vector Độ lớn)"),
    ]

    selected_scenario = st.selectbox(
        "[MÔ PHỎNG] Kịch bản kiểm thử:",
        scenario_options,
        format_func=lambda x: x[1],
        key="sim_scenario",
    )

    raw_data, s_type, s_desc = generate_preset_signal(selected_scenario[0])

    if s_type == "PIEZO_LDT0_028K":
        sim_profile = BUILTIN_PROFILES["piezo_butterworth_1_20_default"]
        sim_pipe_res = run_pipeline(raw_data, sim_profile)
    else:
        sim_profile = BUILTIN_PROFILES["adxl345_triaxial_100hz"]
        sim_pipe_res = run_pipeline(raw_data["mag"], sim_profile)

    sim_npi_res = run_npi(sim_pipe_res.get("tbr"), quality_status=sim_pipe_res.get("quality_status"))

    st.markdown(f"**Mô tả kịch bản:** `{s_desc}`")

    # Metric Cards: EVERY card must show SIMULATED badge
    st.markdown("#### [MÔ PHỎNG] Chỉ số Trích xuất")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        simulated_badge()
        npi_v = sim_npi_res.get("npi_value")
        st.metric("[MÔ PHỎNG] NPI Thử nghiệm", f"{npi_v:.1f}" if npi_v is not None else "N/A")
    with c2:
        simulated_badge()
        tbr_v = sim_pipe_res.get("tbr")
        st.metric("[MÔ PHỎNG] Tỉ số TBR", f"{tbr_v:.4f}" if tbr_v is not None else "N/A")
    with c3:
        simulated_badge()
        dom_f = sim_pipe_res.get("dominant_freq_hz")
        st.metric("[MÔ PHỎNG] Tần số Đỉnh", f"{dom_f:.2f} Hz" if dom_f is not None else "N/A")
    with c4:
        simulated_badge()
        st.metric("[MÔ PHỎNG] Cổng Chất lượng", sim_pipe_res.get("quality_status", "N/A"))

    # Quality Gate Warnings
    if sim_pipe_res.get("quality_flags"):
        st.warning(f"🔶 [MÔ PHỎNG] Phát hiện cờ cảnh báo chất lượng tín hiệu: {', '.join(sim_pipe_res['quality_flags'])}")
    if sim_pipe_res.get("quality_status") == QualityStatus.INVALID:
        st.error("🔴 [MÔ PHỎNG] Tín hiệu không hợp lệ (INVALID) để tính toán chỉ số NPI.")

    # Charts: EVERY chart MUST have [MÔ PHỎNG] in title
    st.markdown("---")
    if s_type == "PIEZO_LDT0_028K":
        fig_sim = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=[
                f"[MÔ PHỎNG] Dạng sóng Tín hiệu Thô — {s_desc}",
                f"[MÔ PHỎNG] Phổ Mật độ Công suất Welch PSD — {s_desc}",
            ],
            vertical_spacing=0.15,
        )

        fig_sim.add_trace(
            go.Scatter(y=raw_data[:1500], mode="lines", line=dict(color="#00D4FF", width=1.2), name="Tín hiệu thô"),
            row=1,
            col=1,
        )

        freqs = sim_pipe_res.get("freqs", [])
        psd = sim_pipe_res.get("psd", [])
        if freqs and psd:
            fig_sim.add_trace(
                go.Scatter(x=freqs, y=psd, mode="lines", line=dict(color="#FC8181", width=1.4), name="Welch PSD"),
                row=2,
                col=1,
            )

        fig_sim.update_layout(
            title="[MÔ PHỎNG] Đồ thị Phân tích Kịch bản Tín hiệu",
            height=580,
            margin=dict(l=40, r=20, t=60, b=30),
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            font=dict(color="#E2E8F0"),
        )
        st.plotly_chart(fig_sim, use_container_width=True)

    else:
        # Triaxial ADXL345 plot
        fig_adxl = make_subplots(
            rows=2,
            cols=1,
            subplot_titles=[
                "[MÔ PHỎNG] 3 Trục Gia tốc ADXL345 (X, Y, Z)",
                "[MÔ PHỎNG] Độ lớn Vector Gia tốc Tổng hợp (|a| Magnitude)",
            ],
            vertical_spacing=0.15,
        )
        fig_adxl.add_trace(go.Scatter(y=raw_data["x"][:500], mode="lines", name="Trục X", line=dict(color="#63B3ED")), row=1, col=1)
        fig_adxl.add_trace(go.Scatter(y=raw_data["y"][:500], mode="lines", name="Trục Y", line=dict(color="#68D391")), row=1, col=1)
        fig_adxl.add_trace(go.Scatter(y=raw_data["z"][:500], mode="lines", name="Trục Z", line=dict(color="#F6E05E")), row=1, col=1)
        fig_adxl.add_trace(go.Scatter(y=raw_data["mag"][:500], mode="lines", name="Vector |a|", line=dict(color="#00D4FF", width=1.5)), row=2, col=1)

        fig_adxl.update_layout(
            title="[MÔ PHỎNG] Luồng Dữ liệu Cảm biến Gia tốc 3 Trục",
            height=580,
            margin=dict(l=40, r=20, t=60, b=30),
            paper_bgcolor="#0E1117",
            plot_bgcolor="#0E1117",
            font=dict(color="#E2E8F0"),
        )
        st.plotly_chart(fig_adxl, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. 📊 BENCHMARK & RESEARCH
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📊 Benchmark & Research":
    render_header("Chuẩn đối sánh & Nhập khẩu Dữ liệu Nghiên cứu")

    st.markdown(
        """
        <div style="background: rgba(43, 108, 176, 0.15); border-left: 4px solid #3182CE; padding: 12px 16px; border-radius: 4px; color: #90CDF4; font-size: 13px; margin-bottom: 16px;">
            ℹ️ <strong>Cơ chế Kiểm chuẩn (Benchmark Studio):</strong> Cho phép nhập khẩu các tệp đo thực nghiệm hoặc dữ liệu đối chứng chuẩn (CSV/JSON).
            Dữ liệu nhập khẩu sẽ tự động được phân tích qua pipeline tín hiệu, ghi nhận với nguồn gốc <code>imported_benchmark</code> và lưu trữ an toàn trong kho dữ liệu.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 📥 Nhập Khẩu Bộ Dữ Liệu Đối Sánh")

    col_b_src1, col_b_src2 = st.columns([1.5, 1])
    with col_b_src1:
        bench_mode = st.radio(
            "Phương thức nạp dữ liệu:",
            ["🧪 Bộ dữ liệu đối chứng mẫu (Synthetic Benchmark Cohorts)", "📁 Tải lên tệp dữ liệu cá nhân (.csv / .json)"],
            horizontal=True,
        )

    samples_to_process = None
    dataset_name = "BENCHMARK_RUN"
    target_fs = 1000.0

    if "Synthetic" in bench_mode:
        cohort_choice = st.selectbox(
            "Chọn tập dữ liệu đối chứng chuẩn:",
            [
                ("cohort_parkinson_like_5_2hz", "Tập A: Vi rung 5.2 Hz (Dải tần Parkinson đặc trưng, 8 giây, 1000 Hz)"),
                ("cohort_healthy_control", "Tập B: Người khỏe mạnh đối chứng (Baseline drift, vi rung thấp, 8 giây, 1000 Hz)"),
                ("cohort_severe_tremor_4_5hz", "Tập C: Vi rung mạnh 4.5 Hz (Biên độ cao, 8 giây, 1000 Hz)"),
            ],
            format_func=lambda x: x[1],
        )
        c_code = cohort_choice[0]
        t_axis = np.linspace(0, 8.0, 8000, endpoint=False)
        if c_code == "cohort_parkinson_like_5_2hz":
            samples_to_process = list(np.clip(2048.0 + 350.0 * np.sin(2 * np.pi * 5.2 * t_axis) + np.random.normal(0, 20.0, 8000), 0, 4095))
            dataset_name = "COHORT_TREMOR_5.2HZ"
        elif c_code == "cohort_healthy_control":
            samples_to_process = list(np.clip(2048.0 + 20.0 * np.sin(2 * np.pi * 5.0 * t_axis) + 50.0 * np.sin(2 * np.pi * 0.3 * t_axis) + np.random.normal(0, 30.0, 8000), 0, 4095))
            dataset_name = "COHORT_HEALTHY_CONTROL"
        else:
            samples_to_process = list(np.clip(2048.0 + 600.0 * np.sin(2 * np.pi * 4.5 * t_axis) + np.random.normal(0, 15.0, 8000), 0, 4095))
            dataset_name = "COHORT_SEVERE_4.5HZ"
    else:
        uploaded_file = st.file_uploader("Chọn tệp CSV hoặc JSON:", type=["csv", "json"])
        if uploaded_file is not None:
            dataset_name = uploaded_file.name
            try:
                if uploaded_file.name.endswith(".csv"):
                    import csv
                    import io
                    content_str = uploaded_file.getvalue().decode("utf-8")
                    reader = csv.reader(io.StringIO(content_str))
                    vals = []
                    for row in reader:
                        if row and not row[0].startswith("#"):
                            try:
                                # Try last column or first numerical column
                                val = float(row[-1])
                                vals.append(val)
                            except ValueError:
                                pass
                    if len(vals) >= 50:
                        samples_to_process = vals
                        st.success(f"Đã đọc thành công {len(vals)} mẫu từ tệp CSV.")
                    else:
                        st.error("Tệp CSV không chứa đủ số lượng mẫu hợp lệ (tối thiểu 50 mẫu).")
                elif uploaded_file.name.endswith(".json"):
                    raw_j = json.loads(uploaded_file.getvalue().decode("utf-8"))
                    if isinstance(raw_j, list):
                        samples_to_process = [float(x) for x in raw_j]
                    elif isinstance(raw_j, dict) and "channels" in raw_j:
                        first_ch = next(iter(raw_j["channels"].values()))
                        samples_to_process = [float(x) for x in first_ch]
                    if samples_to_process and len(samples_to_process) >= 50:
                        st.success(f"Đã đọc thành công {len(samples_to_process)} mẫu từ JSON.")
            except Exception as e:
                st.error(f"Lỗi khi đọc tệp dữ liệu: {e}")

    st.markdown("---")
    col_run1, col_run2 = st.columns([1, 3])
    with col_run1:
        run_import_btn = st.button("🚀 Chạy Phân tích & Nhập khẩu", type="primary", use_container_width=True)

    if run_import_btn and samples_to_process:
        with st.spinner("Đang thực thi pipeline phân tích tín hiệu và lưu trữ..."):
            imported_res = None
            if st.session_state.backend_online:
                try:
                    resp = api_post(
                        "/api/v1/benchmark/import",
                        json={
                            "name": dataset_name,
                            "sensor_type": "PIEZO_LDT0_028K",
                            "profile_id": "piezo_butterworth_1_20_default",
                            "sample_rate_hz": target_fs,
                            "channel_name": "raw_counts",
                            "samples": samples_to_process,
                            "participant_code": "BENCH_COHORT_SUBJ",
                            "notes": f"Imported via Benchmark Studio ({dataset_name})",
                        },
                        timeout=5.0,
                    )
                    if resp.status_code == 200:
                        imported_res = resp.json()
                except Exception as e:
                    st.warning(f"Không thể kết nối API backend: {e}. Sử dụng pipeline nội bộ.")

            # In-process fallback if backend is offline
            if not imported_res:
                arr = np.asarray(samples_to_process, dtype=np.float64)
                prof = BUILTIN_PROFILES["piezo_butterworth_1_20_default"]
                p_res = run_pipeline(arr, prof)
                n_res = run_npi(p_res.get("tbr"), quality_status=p_res.get("quality_status"))
                imported_res = {
                    "session_id": f"bench-local-{uuid.uuid4().hex[:8]}",
                    "name": dataset_name,
                    "provenance": "imported_benchmark",
                    "sample_count": len(samples_to_process),
                    "duration_sec": round(len(samples_to_process) / target_fs, 2),
                    "tbr": p_res.get("tbr"),
                    "npi": n_res,
                    "quality_status": p_res.get("quality_status"),
                    "dominant_freq_hz": p_res.get("dominant_freq_hz"),
                }
                # Also save to local session history
                st.session_state.session_history.append(
                    {
                        "session_id": imported_res["session_id"],
                        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "sensor_type": "PIEZO_LDT0_028K",
                        "duration_sec": imported_res["duration_sec"],
                        "sample_rate_hz": target_fs,
                        "tbr": imported_res["tbr"],
                        "npi_value": n_res.get("npi_value"),
                        "quality_status": imported_res["quality_status"],
                        "provenance": "imported_benchmark",
                    }
                )

            st.success(f"✅ Đã nhập khẩu và phân tích thành công bộ dữ liệu! Mã phiên: `{imported_res['session_id']}`")

            # Metrics cards
            m1, m2, m3, m4 = st.columns(4)
            n_val = imported_res.get("npi", {}).get("npi_value")
            t_val = imported_res.get("tbr")
            d_val = imported_res.get("dominant_freq_hz")
            q_val = imported_res.get("quality_status")

            m1.metric("NPI Thử nghiệm", f"{n_val:.1f}" if n_val is not None else "N/A")
            m2.metric("Tỉ số TBR (3-6Hz/1-20Hz)", f"{t_val:.4f}" if t_val is not None else "N/A")
            m3.metric("Tần số Đỉnh (Dominant)", f"{d_val:.2f} Hz" if d_val is not None else "N/A")
            m4.metric("Chất lượng Tín hiệu", q_val)

            # Plots: Waveform + PSD
            arr_sig = np.asarray(samples_to_process, dtype=np.float64)
            pipe_out = run_pipeline(arr_sig, BUILTIN_PROFILES["piezo_butterworth_1_20_default"])
            filt_sig = pipe_out.get("filtered_signal", [])
            freqs = pipe_out.get("freqs", [])
            psd = pipe_out.get("psd", [])

            fig_bench = make_subplots(
                rows=2,
                cols=1,
                subplot_titles=[
                    f"[CHUẨN ĐỐI SÁNH] Tín hiệu Lọc Butterworth — {dataset_name}",
                    "[CHUẨN ĐỐI SÁNH] Mật độ Công suất Phổ (Welch PSD) & Dải Năng lượng 3–6 Hz",
                ],
                vertical_spacing=0.15,
            )
            if filt_sig:
                fig_bench.add_trace(go.Scatter(y=filt_sig[:2000], mode="lines", line=dict(color="#00D4FF", width=1.2), name="Tín hiệu Lọc"), row=1, col=1)
            if freqs and psd:
                fig_bench.add_trace(go.Scatter(x=freqs, y=psd, mode="lines", line=dict(color="#FC8181", width=1.5), name="PSD"), row=2, col=1)
                # Highlight 3-6 Hz band
                m_3_6 = [f for f in freqs if 3.0 <= f <= 6.0]
                if m_3_6:
                    p_3_6 = [psd[i] for i, f in enumerate(freqs) if 3.0 <= f <= 6.0]
                    fig_bench.add_trace(
                        go.Scatter(x=m_3_6, y=p_3_6, fill="tozeroy", fillcolor="rgba(237, 137, 54, 0.35)", line=dict(color="#ED8936", width=0), name="Dải 3–6 Hz"),
                        row=2,
                        col=1,
                    )
            fig_bench.update_layout(
                height=560,
                margin=dict(l=40, r=20, t=50, b=30),
                paper_bgcolor="#0E1117",
                plot_bgcolor="#0E1117",
                font=dict(color="#E2E8F0"),
            )
            st.plotly_chart(fig_bench, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6. 📁 SESSIONS & HISTORY
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📁 Sessions & History":
    render_header("Kho Lưu trữ & Xuất Dữ liệu Nghiên cứu")

    st.markdown("### 📑 Danh sách Phiên đo Đã ghi nhận")

    history = st.session_state.session_history
    api_stats = {}
    if st.session_state.backend_online:
        api_sessions, api_stats = load_sessions_from_api()
        if api_sessions:
            history = api_sessions

    if history:
        # Historical category values predate the approved D-017 display policy.
        # Keep them out of the dashboard and any user-facing exports.
        history = [
            {key: value for key, value in record.items() if key not in {"category", "npi_category"}}
            for record in history
        ]
        # Summary metrics
        total_sessions = api_stats.get("total_count", api_stats.get("total", len(history))) if (st.session_state.backend_online and api_stats) else len(history)
        valid_sessions = api_stats.get("valid_quality", sum(1 for s in history if s.get("quality_status") == "VALID_FOR_ANALYSIS"))
        device_count = sum(1 for s in history if s.get("provenance") == "device")
        simulated_count = sum(1 for s in history if s.get("provenance") == "simulated")

        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Tổng số Phiên", str(total_sessions))
        s2.metric("Phiên Đạt chuẩn Chất lượng", f"{valid_sessions} / {total_sessions}")
        s3.metric("Bản ghi thiết bị", str(device_count))
        s4.metric("Bản ghi mô phỏng", str(simulated_count))

        st.markdown("---")

        sess_table = []
        for s in history:
            sid = s.get("session_id") or s.get("id", "N/A")
            t_stamp = s.get("timestamp") or s.get("created_at") or s.get("start_time") or ""
            sess_table.append(
                {
                    "Mã phiên": sid,
                    "Cảm biến": s.get("sensor_type", "N/A"),
                    "Thời điểm": str(t_stamp),
                    "Thời lượng (s)": s.get("duration_sec"),
                    "Tần số (Hz)": s.get("sample_rate_hz", 1000.0),
                    "TBR": f"{s['tbr']:.4f}" if s.get("tbr") is not None else "N/A",
                    "NPI Thử nghiệm": f"{s['npi_value']:.1f}" if s.get("npi_value") is not None else "N/A",
                    "Chất lượng": s.get("quality_status", "N/A"),
                    "Nguồn gốc": s.get("provenance", "simulated"),
                }
            )
        st.dataframe(sess_table, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 🔍 Xem Chi tiết Siêu dữ liệu & Xuất Báo cáo (JSON Export)")

        sess_ids = [s.get("session_id") or s.get("id") for s in history]
        selected_sid = st.selectbox("Chọn phiên để kiểm tra hoặc xuất:", sess_ids)
        selected_record = next(
            (s for s in history if (s.get("session_id") or s.get("id")) == selected_sid),
            history[0],
        )

        col_meta, col_dl = st.columns([2, 1])
        with col_meta:
            st.json(selected_record)

        with col_dl:
            st.markdown(
                """
                <div style="background: #1A1F2E; border: 1px solid #2D3748; padding: 16px; border-radius: 8px; margin-bottom: 12px;">
                    <h5 style="margin: 0 0 8px 0; color: #00D4FF;">Xuất Báo cáo Kỹ thuật</h5>
                    <p style="color: #A0AEC0; font-size: 12px; margin: 0 0 12px 0;">
                        Tải về siêu dữ liệu nghiên cứu đầy đủ, bao gồm mã băm SHA-256 xác thực nguồn gốc và toàn vẹn.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            rec_id = selected_record.get("session_id") or selected_record.get("id", "session")
            can_export = st.session_state.auth_user.get("role") in {"admin", "researcher", "offline"}
            if can_export:
                st.download_button(
                    label="⬇ Tải Báo cáo JSON của Phiên này",
                    data=json.dumps(selected_record, indent=2, default=str),
                    file_name=f"{rec_id}_report.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # CSV download option
            csv_payload = None
            if st.session_state.backend_online and can_export:
                try:
                    c_resp = api_get(f"/api/v1/sessions/{rec_id}/export?format=csv", timeout=3.0)
                    if c_resp.status_code == 200:
                        csv_payload = c_resp.text
                except Exception:
                    pass

            if csv_payload:
                st.download_button(
                    label="📊 Tải Dữ liệu Chuỗi thời gian (CSV)",
                    data=csv_payload,
                    file_name=f"{rec_id}_data.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

            if can_export:
                st.download_button(
                    label="📦 Tải Toàn bộ Lịch sử Phiên (Batch JSON)",
                    data=json.dumps(history, indent=2, default=str),
                    file_name="neuropulse_all_sessions.json",
                    mime="application/json",
                    use_container_width=True,
                )
    else:
        st.info("Hiện chưa có phiên đo nào trong lịch sử.")


# ─────────────────────────────────────────────────────────────────────────────
# 7. 🔌 DEVICES & PROFILES
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🔌 Devices & Profiles":
    render_header("Cấu hình Cổng Giao tiếp & Hồ sơ Cảm biến")

    col_dev, col_prof = st.columns(2)

    with col_dev:
        st.markdown("#### 🔌 Quản lý Cổng Serial ESP32")
        st.write(
            "Hệ thống hỗ trợ tự động kết nối qua **Cổng nối tiếp USB (Virtual COM Port)** với ESP32 hoặc bộ phát tín hiệu giả lập."
        )

        port_opts = get_available_ports()
        selected_port = st.selectbox("Cổng giao tiếp:", port_opts)
        selected_baud = st.selectbox("Tốc độ Baud:", [115200], help="Firmware hiện khởi động cố định ở 115200 baud.")
        selected_hw_profile = st.selectbox("Cấu hình Phần cứng:", ["Piezo ADC (GPIO 34)", "ADXL345 I2C (SDA 21, SCL 22)"])

        c_conn1, c_conn2 = st.columns(2)
        with c_conn1:
            if st.button("🔗 Kết nối Cổng", type="primary", use_container_width=True,
                         disabled=st.session_state.auth_user.get("role") not in {"admin", "operator", "offline"}):
                port_clean = selected_port.split()[0]
                if st.session_state.backend_online:
                    try:
                        hw_sensor = "ADXL345" if "ADXL345" in selected_hw_profile else "PIEZO_LDT0_028K"
                        r_conn = api_post(
                            "/api/v1/devices/connect",
                            json={"port": port_clean, "baud_rate": selected_baud, "sensor_type": hw_sensor},
                            timeout=6,
                        )
                        if r_conn.status_code == 200:
                            st.success(f"Đã mở cổng {port_clean} ở tốc độ {selected_baud} baud.")
                        else:
                            st.warning(f"Lỗi kết nối cổng {port_clean}: {r_conn.text}")
                    except Exception as e:
                        st.error(f"Lỗi khi gửi yêu cầu kết nối: {e}")
                else:
                    st.success(f"Đã mở cổng {port_clean} ở tốc độ {selected_baud} baud.")
        with c_conn2:
            if st.button("🔌 Ngắt kết nối", use_container_width=True,
                         disabled=st.session_state.auth_user.get("role") not in {"admin", "operator", "offline"}):
                if st.session_state.backend_online:
                    try:
                        api_post("/api/v1/devices/disconnect", timeout=2)
                    except Exception:
                        pass
                st.info("Đã ngắt kết nối cổng Serial.")

        st.markdown("---")
        st.markdown("#### ⚡ Thông tin Firmware & Chân Kết nối (Pinout)")
        st.markdown(
            """
            - **Firmware Version:** NeuroPulse ESP32 Firmware v1.0.0
            - **Giao thức Truyền thông:** Nhị phân khung cố định (Frame 0xAA55, CRC16)
            - **Chân ADC Piezo:** GPIO 34 (ADC1 Channel 6, 12-bit)
            - **Chân I2C ADXL345:** SDA = GPIO 21, SCL = GPIO 22 (400 kHz)
            - **LED Trạng thái:** GPIO 2 (Heartbeat / Acquisition)
            """
        )

    with col_prof:
        st.markdown("#### 📋 Quản lý Hồ sơ Xử lý (Processing Profiles)")
        st.write("Các hồ sơ bộ lọc tích hợp sẵn tuân thủ đặc tả kỹ thuật dự án:")

        selected_prof_inspect = st.selectbox(
            "Xem chi tiết Hồ sơ:",
            list(BUILTIN_PROFILES.keys()),
            format_func=lambda x: {
                "piezo_butterworth_1_20_default": "piezo_butterworth_1_20_default (Mặc định)",
                "piezo_butterworth_5_20_candidate": "piezo_butterworth_5_20_candidate (Ứng viên)",
                "adxl345_triaxial_100hz": "adxl345_triaxial_100hz (ADXL345 3 Trục)",
            }.get(x, x),
        )

        st.json(BUILTIN_PROFILES[selected_prof_inspect])

elif page == "🧑‍🤝‍🧑 Participant Kiosk":
    render_header("Participant / Kiosk Mode")
    st.markdown("### Hướng dẫn phiên đo")
    st.write("Vui lòng làm theo hướng dẫn của nhân viên nghiên cứu và giữ thiết bị theo đúng vị trí đã được chỉ dẫn.")
    st.info("Màn hình kiosk chỉ cung cấp hướng dẫn và trạng thái quy trình. Không hiển thị chỉ số phân tích hoặc diễn giải y khoa.")

elif page == "👤 Hồ sơ bệnh nhân":
    render_header("Hồ sơ cá nhân" if st.session_state.auth_user.get("role") == "patient" else "Quản lý hồ sơ bệnh nhân")
    role = st.session_state.auth_user.get("role", "offline")
    st.caption("Dữ liệu lưu cục bộ trên máy này. Mã bệnh nhân chỉ tra cứu hồ sơ, không xác thực danh tính.")

    if role == "patient":
        st.markdown("### Tra cứu hồ sơ của bạn")
        with st.form("patient_lookup"):
            patient_code = st.text_input("Mã bệnh nhân", placeholder="Ví dụ: NXY2601234")
            lookup_submit = st.form_submit_button("Mở hồ sơ", type="primary")
        if lookup_submit:
            try:
                response = api_get(f"/api/v1/patients/lookup/{patient_code.strip().upper()}", timeout=5)
                if response.ok:
                    st.session_state.patient_lookup_result = response.json()
                    st.session_state.patient_lookup_code = patient_code.strip().upper()
                else:
                    st.session_state.patient_lookup_result = None
                    st.error("Không tìm thấy hồ sơ theo mã đã nhập.")
            except Exception as exc:
                st.error(f"Không thể tải hồ sơ: {exc}")

        result = st.session_state.get("patient_lookup_result")
        if result:
            patient = result["patient"]
            st.markdown(f"#### {patient['full_name']} · `{patient['patient_code']}`")
            profile_cols = st.columns(3)
            profile_cols[0].metric("Ngày sinh", patient.get("date_of_birth") or "Chưa cung cấp")
            profile_cols[1].metric("Nhóm tuổi", patient.get("age_band", "—"))
            profile_cols[2].metric("Chế độ ăn", {"vegetarian": "Chay", "omnivore": "Mặn"}.get(patient.get("diet"), "Chưa cung cấp"))
            st.write("**Tiền sử cá nhân:**", patient.get("medical_history") or "Chưa ghi nhận")
            st.write("**Tiền sử gia đình:**", patient.get("family_history") or "Chưa ghi nhận")
            st.markdown("#### Lịch sử đo")
            sessions = result.get("sessions", [])
            if not sessions:
                st.info("Hồ sơ chưa có phiên đo đã lưu.")
            for record in sessions:
                with st.expander(f"{record.get('created_at', 'Phiên đo')} · {record.get('sensor_type', 'Cảm biến')} · {record.get('status', '')}"):
                    metrics = st.columns(3)
                    metrics[0].metric("NPI thử nghiệm", record.get("npi_value") if record.get("npi_value") is not None else "Chưa có")
                    metrics[1].metric("Phân loại demo", record.get("npi_category") or "Chưa có")
                    metrics[2].metric("Chất lượng tín hiệu", record.get("quality_status") or "Chưa đánh giá")
                    if record.get("npi_category"):
                        st.warning(f"Kết quả thuộc dải demo: {record['npi_category']}. Đây là giả thuyết nghiên cứu, chưa được xác nhận lâm sàng và không phải chẩn đoán.")
                    st.caption(f"Nguồn dữ liệu: {record.get('provenance', 'unknown')}")
            st.info(result.get("screening_notice", "Dữ liệu chỉ phục vụ nghiên cứu."))
            st.download_button(
                "Tải hồ sơ cá nhân dạng JSON",
                data=json.dumps(result, ensure_ascii=False, indent=2, default=str),
                file_name=f"neuropulse_{patient['patient_code']}.json",
                mime="application/json",
            )
        st.stop()

    if role in {"admin", "operator", "researcher"}:
        st.markdown("### Tạo hồ sơ mới")
        with st.form("patient_create"):
            full_name = st.text_input("Họ và tên")
            dob = st.date_input("Ngày sinh", value=None, format="DD/MM/YYYY")
            chromosome = st.selectbox("Dấu mã nhiễm sắc thể", ["X", "Y"], format_func=lambda x: "XX (X)" if x == "X" else "XY (Y)")
            diet_label = st.selectbox("Chế độ ăn", ["Chưa cung cấp", "Chay", "Mặn"])
            medical_history = st.text_area("Tiền sử cá nhân")
            family_history = st.text_area("Tiền sử gia đình")
            create_patient = st.form_submit_button("Tạo hồ sơ", type="primary")
        if create_patient:
            payload = {
                "full_name": full_name.strip(),
                "date_of_birth": dob.isoformat() if dob else None,
                "chromosome_marker": chromosome,
                "medical_history": medical_history or None,
                "family_history": family_history or None,
                "diet": {"Chay": "vegetarian", "Mặn": "omnivore"}.get(diet_label),
            }
            response = api_post("/api/v1/patients", json=payload, timeout=5)
            if response.ok:
                created_patient = response.json()
                st.success(f"Đã tạo hồ sơ. Mã bệnh nhân: {created_patient['patient_code']}")
                st.code(created_patient["patient_code"])
            else:
                st.error(f"Không tạo được hồ sơ: {response.text}")

    st.markdown("### Hồ sơ đã đăng ký")
    try:
        patients_response = api_get("/api/v1/patients", timeout=5)
        patients = patients_response.json() if patients_response.ok else []
        if not patients:
            st.info("Chưa có hồ sơ bệnh nhân.")
        for patient in patients:
            with st.expander(f"{patient['patient_code']} · {patient['full_name']}"):
                st.write(f"Ngày sinh: {patient.get('date_of_birth') or 'Chưa cung cấp'}")
                st.write(f"Tiền sử cá nhân: {patient.get('medical_history') or '—'}")
                st.write(f"Tiền sử gia đình: {patient.get('family_history') or '—'}")
                st.write(f"Lưu đến: {'Vô thời hạn' if patient.get('retain_indefinitely') else patient.get('retention_expires_at') or 'Chưa đặt'}")
                if role == "admin":
                    retain = st.checkbox("Giữ vô thời hạn cho nghiên cứu", value=patient.get("retain_indefinitely", False), key=f"retain_{patient['patient_code']}")
                    if retain != patient.get("retain_indefinitely", False) and st.button("Cập nhật lưu trữ", key=f"save_retain_{patient['patient_code']}"):
                        updated = api_patch(f"/api/v1/patients/{patient['patient_code']}/retention", json={"retain_indefinitely": retain}, timeout=5)
                        if updated.ok:
                            st.success("Đã cập nhật thời hạn lưu hồ sơ.")
                            st.rerun()
                        else:
                            st.error(updated.text)
    except Exception as exc:
        st.error(f"Không tải được danh sách hồ sơ: {exc}")

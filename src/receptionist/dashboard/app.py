import os
import streamlit as st
import httpx
import json
from datetime import datetime

st.set_page_config(page_title="AI Receptionist Admin", layout="wide")

API_URL = os.environ.get("API_URL", "http://localhost:8000/api/v1").rstrip("/")
if not API_URL.endswith("/api/v1"):
    API_URL = f"{API_URL}/api/v1"
API_KEY = os.environ.get("RECEPTIONIST_API_KEY", "")


def _headers(tenant: str = None) -> dict:
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    if tenant:
        headers["X-Tenant-ID"] = tenant
    return headers


def api_get(path: str, params: dict = None, tenant: str = None):
    try:
        resp = httpx.get(f"{API_URL}{path}", params=params,
                         headers=_headers(tenant), timeout=10)
        if resp.status_code == 401:
            st.error("API authentication failed. Set the RECEPTIONIST_API_KEY environment variable.")
            return []
        if resp.status_code == 403:
            detail = resp.json().get("detail", resp.text) if resp.text else "Forbidden"
            st.error(f"Access denied: {detail}")
            return []
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def api_post(path: str, data: dict, tenant: str = None):
    try:
        resp = httpx.post(f"{API_URL}{path}", json=data,
                          headers=_headers(tenant), timeout=30)
        return resp.json() if resp.status_code == 200 else {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


st.sidebar.title("AI Receptionist Admin")
page = st.sidebar.radio("Navigation", [
    "Dashboard", "Live Agent Runs", "Appointments", "Customers",
    "Staff", "Services", "Handoffs", "Analytics",
])

tenant_id = st.sidebar.text_input("Tenant ID", value="clinic_001")

if page == "Dashboard":
    st.title("Dashboard")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Conversations", "0")
    with col2:
        st.metric("Appointments Booked", "0")
    with col3:
        st.metric("Human Handoffs", "0")
    with col4:
        st.metric("Tool Failures", "0")

    st.subheader("Recent Activity")
    st.info("Connect to the API to see live data.")

elif page == "Live Agent Runs":
    st.title("Live Agent Runs")
    runs = api_get("/agent-runs", tenant=tenant_id)
    if runs:
        for run in runs[:10]:
            with st.expander(f"Run {run['id'][:12]} - {run['status']}"):
                st.write(f"Conversation: {run['conversation_id']}")
                st.write(f"Started: {run['started_at']}")
                if run.get('completed_at'):
                    st.write(f"Completed: {run['completed_at']}")
    else:
        st.info("No agent runs found.")

elif page == "Appointments":
    st.title("Appointments")
    appointments = api_get("/appointments", tenant=tenant_id)
    if appointments:
        for apt in appointments[:20]:
            st.write(f"**{apt['id'][:12]}** | {apt['start_time']} | {apt['status']}")
    else:
        st.info("No appointments found.")

elif page == "Customers":
    st.title("Customers")
    customers = api_get("/customers", tenant=tenant_id)
    if customers:
        for cust in customers[:20]:
            st.write(f"**{cust['first_name']} {cust['last_name']}** | {cust.get('email', 'N/A')}")
    else:
        st.info("No customers found.")

elif page == "Staff":
    st.title("Staff")
    staff = api_get("/staff", tenant=tenant_id)
    if staff:
        for s in staff:
            st.write(f"**{s['name']}** | {s.get('role', 'N/A')} | {s.get('department', 'N/A')}")
    else:
        st.info("No staff found.")

elif page == "Services":
    st.title("Services")
    services = api_get("/services", tenant=tenant_id)
    if services:
        for svc in services:
            st.write(f"**{svc['name']}** | {svc['duration_minutes']}min | ${svc.get('price', 'N/A')}")
    else:
        st.info("No services found.")

elif page == "Handoffs":
    st.title("Human Handoffs")
    st.info("Handoff management interface coming soon.")

elif page == "Analytics":
    st.title("Analytics")
    st.info("Analytics dashboard coming soon.")

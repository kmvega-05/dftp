import sys
import os

# Ensure project root is on sys.path so `import client` resolves when Streamlit runs
# (Streamlit runs the script from its directory which can make package imports fail)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from datetime import datetime
import threading
import time
import traceback
import logging

from core.connection import ControlConnectionManager
from core.parser import Parser
from core.commands import ClientCommandHandler
from levenstein import get_suggestion

import streamlit as st

# Configure logging for Streamlit app
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


st.set_page_config(page_title="dFTP Client UI", layout="wide")

# --- Helpers -----------------------------------------------------------------

@st.cache_resource
def make_conn(host: str, port: int, timeout: float = 10.0):
    return ControlConnectionManager(host, port, timeout)


# A lightweight wrapper to run blocking network calls in a thread and capture exceptions
def run_in_thread(fn, *args, **kwargs):
    result = {"value": None, "error": None}
    def target():
        try:
            result["value"] = fn(*args, **kwargs)
        except Exception as e:
            result["error"] = e
    t = threading.Thread(target=target)
    t.start()
    return t, result


# --- UI ----------------------------------------------------------------------
st.title("dFTP — Streamlit Client")

with st.sidebar:
    st.header("Connection")
    host = st.text_input("Host", value="0.0.0.0")
    port = st.number_input("Port", min_value=1, max_value=65535, value=2121)
    timeout = st.number_input("Timeout (s)", min_value=1.0, max_value=60.0, value=10.0)
    if st.button("Connect"):
        try:
            logger.info(f"[UI] Connect button clicked: {host}:{port}")
            conn = make_conn(host, int(port), float(timeout))
            logger.info(f"[UI] Connecting to {host}:{port}...")
            conn.connect()
            st.session_state["conn"] = conn
            logger.info(f"[UI] Connection successful")
            logger.info(str(st.session_state["conn"]))
            handler = ClientCommandHandler(conn, Parser())
            st.session_state["handler"] = handler
            # Read and record the server banner (welcome message) immediately
            try:
                logger.debug("[UI] Reading server banner")
                banner = handler.read_banner()
                if banner:
                    logger.info(f"[UI] Banner received: {banner.code} - {banner.message}")
                    st.info(f"{banner.code} — {banner.message}")
            except Exception as e:
                logger.warning(f"[UI] Banner read error: {e}")
                # ignore banner read errors
                pass
            # record successful connect in history
            handler.history.append({
                "time": datetime.utcnow(),
                "command": f"CONNECT {host}:{port}",
                "raw": f"Connected to {host}:{port}",
                "parsed": None,
                "error": False
            })
            st.success(f"Connected to {host}:{port}")
        except Exception as e:
            logger.error(f"[UI] Connection failed: {e}")
            st.session_state["conn"] = None
            st.session_state["handler"] = None
            # put connection failure into a small temp history in session
            tmp = st.session_state.get("tmp_history", [])
            tmp.append({
                "time": datetime.utcnow(),
                "command": f"CONNECT {host}:{port}",
                "raw": str(e),
                "parsed": None,
                "error": True
            })
            st.session_state["tmp_history"] = tmp
            st.error(f"Connection failed: {e}")
    if st.button("Disconnect"):
        logger.info("[UI] Disconnect button clicked")
        logger.info(st.session_state.get("conn"))
        conn = st.session_state.get("conn")
        if conn:
            try:
                logger.debug("[UI] Disconnecting...")
                conn.disconnect()
                handler = st.session_state.get("handler")
                if handler:
                    handler.history.append({
                        "time": datetime.utcnow(),
                        "command": "DISCONNECT",
                        "raw": "Disconnected by user",
                        "parsed": None,
                        "error": False
                    })
                st.session_state["conn"] = None
                st.session_state["handler"] = None
                logger.info("[UI] Disconnect successful")
                st.info("Disconnected")
            except Exception as e:
                logger.error(f"[UI] Error disconnecting: {e}")
                st.error(f"Error disconnecting: {e}")


if "handler" not in st.session_state:
    st.session_state["handler"] = None

col1, col2 = st.columns([3, 1])

with col1:
    st.subheader("Terminal")
    output_box = st.empty()
    # Command input
    cmd = st.text_input("Command", placeholder="e.g. USER anonymous", key="cmd_input")
    cmd_run = st.button("Run")

    # File upload for STOR
    uploaded_file = st.file_uploader("Upload file for STOR", key="upload_file")

    # A simple area to show last output
    if cmd_run and cmd:
        logger.info(f"[UI] Command executed: {cmd}")
        handler: ClientCommandHandler = st.session_state.get("handler")
        if not handler:
            logger.warning("[UI] Not connected")
            st.error("Not connected. Connect first.")
        else:
            try:
                parts = cmd.strip().split()
                verb = parts[0].lower()
                # Handle commands that require additional UI inputs
                if verb == "stor":
                    logger.info("[UI] STOR command handler")
                    # expect optional: STOR remote_name
                    remote = parts[1] if len(parts) > 1 else None
                    if uploaded_file is None:
                        logger.warning("[UI] No file uploaded for STOR")
                        st.error("Select a file to upload using the uploader above.")
                    else:
                        # save to a temporary path
                        local_path = f"/tmp/streamlit_upload_{int(time.time())}_{uploaded_file.name}"
                        logger.debug(f"[UI] STOR temp file: {local_path}")
                        with open(local_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())
                        # run stor in a thread to avoid blocking
                        t, result = run_in_thread(handler._stor, local_path, remote)
                        with st.spinner("Uploading..."):
                            # create a single progress bar and update it until the upload thread finishes
                            p = st.progress(0)
                            start = time.time()
                            while t.is_alive():
                                time.sleep(0.1)
                                # animate progress while the upload runs. Keep value <100 until finished
                                elapsed = time.time() - start
                                value = min(99, int((elapsed * 10) % 100))
                                p.progress(value)
                            # ensure progress shows complete when done
                            p.progress(100)
                        if result["error"]:
                            logger.error(f"[UI] STOR error: {result['error']}")
                            st.error(f"Error: {result['error']}")
                        else:
                            out = result["value"]
                            logger.info(f"[UI] STOR completed: {out}")
                            # Expecting (remote_filename, parsed)
                            if isinstance(out, tuple) and len(out) == 2:
                                filename, parsed = out
                                # show preliminary message if available in history
                                last = handler.get_history()[-1] if handler.get_history() else None
                                if last and last.get("prelim"):
                                    p = last.get("prelim")
                                    st.info(f"{p.code} - {p.message}")
                                # show final parsed message (2xx or error)
                                if hasattr(parsed, "code"):
                                    if parsed.type in ("error", "unknown"):
                                        st.error(f"{parsed.code} - {parsed.message}")
                                    else:
                                        st.success(f"{parsed.code} - {parsed.message}")
                                else:
                                    st.success(f"STOR finished: {filename}")
                            else:
                                st.success(f"STOR finished: {out}")
                elif verb == "retr":
                    logger.info("[UI] RETR command handler")
                    if len(parts) < 2:
                        logger.error("[UI] Invalid RETR syntax")
                        st.error("Usage: RETR remote_filename [local_path]")
                    else:
                        remote = parts[1]
                        local = parts[2] if len(parts) > 2 else f"/tmp/{remote}"
                        logger.debug(f"[UI] RETR: {remote} -> {local}")
                        t, result = run_in_thread(handler._retr, remote, local)
                        with st.spinner("Downloading..."):
                            p = st.progress(0)
                            i = 0
                            while t.is_alive():
                                time.sleep(0.15)
                                i = min(100, i+5)
                                p.progress(i)
                        if result["error"]:
                            logger.error(f"[UI] RETR error: {result['error']}")
                            st.error(f"Error: {result['error']}")
                        else:
                            out = result["value"]
                            logger.info(f"[UI] RETR completed: {out}")
                            # Expecting (local_path, parsed)
                            if isinstance(out, tuple) and len(out) == 2:
                                local_path, parsed = out
                                last = handler.get_history()[-1] if handler.get_history() else None
                                if last and last.get("prelim"):
                                    p = last.get("prelim")
                                    st.info(f"{p.code} - {p.message}")
                                # show final parsed message
                                if hasattr(parsed, "code"):
                                    if parsed.type in ("error", "unknown"):
                                        st.error(f"{parsed.code} - {parsed.message}")
                                    else:
                                        st.success(f"{parsed.code} - {parsed.message}")
                                else:
                                    st.success(f"RETR finished: {local_path}")
                            else:
                                st.success(f"RETR finished: {out}")
                elif verb in ("list", "nlst"):
                    logger.info(f"[UI] {verb.upper()} command handler")
                    if verb == "list":
                        t, result = run_in_thread(handler._list, "")
                    else:
                        t, result = run_in_thread(handler._nlst, "")
                    with st.spinner("Fetching listing..."):
                        while t.is_alive():
                            time.sleep(0.05)
                    if result["error"]:
                        logger.error(f"[UI] {verb.upper()} error: {result['error']}")
                        st.error(f"Error: {result['error']}")
                    else:
                        val = result["value"]
                        logger.debug(f"[UI] {verb.upper()} result received")
                        # When handler._list returns (listing, parsed)
                        if isinstance(val, tuple) and len(val) == 2:
                            listing, parsed = val
                            # show preliminary 1xx message if present in the last history entry
                            last = handler.get_history()[-1] if handler.get_history() else None
                            if last and last.get("prelim"):
                                p = last.get("prelim")
                                st.info(f"{p.code} - {p.message}")
                            st.text_area("Listing", value=listing)
                            # show final parsed message (2xx or error)
                            if hasattr(parsed, "code"):
                                if parsed.type in ("error", "unknown"):
                                    st.error(f"{parsed.code} - {parsed.message}")
                                else:
                                    st.success(f"{parsed.code} - {parsed.message}")
                        else:
                            st.write(val)
                else:
                    logger.info(f"[UI] Generic command handler for: {verb}")
                    # default: run _execute via mapping
                    # try to call a corresponding method on handler
                    method_name = f"_{verb}"
                    method = getattr(handler, method_name, None)
                    if method is None:
                        logger.warning(f"[UI] Unknown command: {verb}")
                        st.error(f"Unknown command: {verb}")
                        st.write(f"Try with {get_suggestion(verb)}")
                    else:
                        args = parts[1:]
                        logger.debug(f"[UI] Calling {method_name} with args: {args}")
                        t, result = run_in_thread(method, *args)
                        with st.spinner("Running..."):
                            while t.is_alive():
                                time.sleep(0.05)
                        if result["error"]:
                            logger.error(f"[UI] Command error: {result['error']}")
                            st.error(f"Error: {result['error']}")
                        else:
                            out = result["value"]
                            logger.debug(f"[UI] Command result: {out}")
                            # parsed MessageStructure
                            if hasattr(out, "code"):
                                st.write(f"{out.code} — {out.message}")
                            else:
                                st.write(out)
            except Exception as e:
                logger.error(f"[UI] Unhandled exception: {traceback.format_exc()}")
                st.error(f"Unhandled exception:\n{traceback.format_exc()}")

with col2:
    st.subheader("History")
    handler: ClientCommandHandler = st.session_state.get("handler")
    if handler is None:
        st.info("No history: not connected")
        tmp = st.session_state.get("tmp_history", [])
        for entry in reversed(tmp[-50:]):
            t = entry.get("time")
            time_str = t.isoformat() if isinstance(t, datetime) else str(t)
            with st.expander(f"{time_str} — {entry.get('command')}"):
                if entry.get("raw"):
                    st.code(entry.get("raw"))
                if entry.get("error"):
                    st.error("This entry had an error")
    else:
        hist = handler.get_history()
        if st.button("Clear History"):
            handler.clear_history()
            st.experimental_rerun()
        for entry in reversed(hist[-100:]):
            t = entry.get("time")
            if isinstance(t, datetime):
                time_str = t.isoformat()
            else:
                time_str = str(t)
            with st.expander(f"{time_str} — {entry.get('command')}"):
                if entry.get("data") is not None:
                    st.text_area("Data", value=str(entry.get("data")), height=150)
                parsed = entry.get("parsed")
                if parsed:
                    st.write(f"Code: {parsed.code}")
                    st.write(f"Message: {parsed.message}")
                    st.write(f"Type: {parsed.type}")
                if entry.get("raw"):
                    st.code(entry.get("raw"))
                if entry.get("error"):
                    st.error("This entry had an error")


# Footer
st.markdown("---")
st.caption("dFTP Streamlit UI — showing command history, progress and errors.")

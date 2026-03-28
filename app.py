import streamlit as st
import json
import tempfile
import os
import zipfile
import shutil
from parsers.tiktok import parse_tiktok_export
from parsers.instagram import parse_instagram_export
from report import generate_report

# --- UI Setup ---
st.set_page_config(
    page_title="SYS.TEARDOWN // Social Media Forensics",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for the "Premium" look
st.markdown("""
<style>
    .main {
        background-color: #0f172a;
        color: #e2e8f0;
    }
    .stApp {
        background-color: #0f172a;
    }
    [data-testid="stHeader"] {
        background-color: #0f172a;
        border-bottom: 1px solid #1e293b;
    }
    .stMarkdown h1 {
        color: #06b6d4;
        font-family: 'JetBrains Mono', monospace;
        letter-spacing: -0.05em;
        text-shadow: 0 0 20px rgba(6, 182, 212, 0.3);
    }
    .stMarkdown h2, .stMarkdown h3 {
        color: #cbd5e1;
        font-family: 'Inter', sans-serif;
    }
    .reportview-container .main .block-container {
        padding-top: 2rem;
    }
    .stButton>button {
        background-color: rgba(6, 182, 212, 0.1);
        color: #06b6d4;
        border: 1px solid rgba(6, 182, 212, 0.4);
        border-radius: 8px;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        background-color: rgba(6, 182, 212, 0.2);
        border-color: #06b6d4;
        box-shadow: 0 0 20px rgba(6, 182, 212, 0.2);
    }
    /* Glassmorphism card effect */
    .css-1r6slb0, .css-ke7v68 {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 12px;
        padding: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.image("https://img.icons8.com/isometric/512/cyber-security.png", width=100)
    st.title("SYS.TEARDOWN")
    st.markdown("### Social Media Forensic Analyzer")
    st.markdown("---")
    st.markdown("Analyze your data exports locally in your browser session.")
    st.info("🔒 **Privacy First**: All processing happens in this session's memory. No data is stored or transmitted.")
    
    st.markdown("---")
    st.markdown("### Platform Status")
    st.success("TikTok: Active")
    st.success("Instagram/Meta: Active")
    st.warning("YouTube: Coming Soon")

# --- Main App ---
st.title("SYS.TEARDOWN // SOCIAL MEDIA FORENSICS")
st.markdown("Upload your exports to reveal how platforms profile and track you.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 1. Upload TikTok data")
    tt_file = st.file_uploader("Upload 'user_data_tiktok.json'", type=['json'], key="tt")

with col2:
    st.markdown("### 2. Upload Instagram data")
    ig_file = st.file_uploader("Upload Meta export (.zip or multiple files)", type=['zip', 'json'], accept_multiple_files=False, key="ig")

if st.button("RUN FORENSIC ANALYSIS", use_container_width=True):
    if not tt_file and not ig_file:
        st.error("Please upload at least one platform export to begin.")
    else:
        with st.spinner("Analyzing data patterns..."):
            tiktok_data = None
            instagram_data = None
            
            # Temporary directory for processing
            with tempfile.TemporaryDirectory() as tmp_dir:
                # Handle TikTok
                if tt_file:
                    tt_path = os.path.join(tmp_dir, "tiktok_data.json")
                    with open(tt_path, "wb") as f:
                        f.write(tt_file.getbuffer())
                    tiktok_data = parse_tiktok_export(tt_path)
                    
                # Handle Instagram
                if ig_file:
                    ig_path = os.path.join(tmp_dir, "instagram_export")
                    os.makedirs(ig_path, exist_ok=True)
                    
                    if ig_file.name.endswith(".zip"):
                        zip_path = os.path.join(tmp_dir, "ig_data.zip")
                        with open(zip_path, "wb") as f:
                            f.write(ig_file.getbuffer())
                        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                            zip_ref.extractall(ig_path)
                        # IG export can be nested
                        instagram_data = parse_instagram_export(ig_path)
                    else:
                        # Fallback for single json file if it's the ad categories
                        pass # Need to refine single-file IG upload if needed
                
                if tiktok_data or instagram_data:
                    # Generate the JSON report (in-memory if possible, but existing report.py writes to file)
                    report_path = os.path.join(tmp_dir, "report.json")
                    generate_report(tiktok_data, instagram_data, report_path)
                    
                    # Load results back for display
                    with open(report_path, "r") as f:
                        full_report = json.load(f)
                    
                    st.success("Analysis Complete!")
                    st.balloons()
                    
                    # Store report in session state to persist through re-renders
                    st.session_state['report'] = full_report

import streamlit.components.v1 as components

# --- Results Rendering ---
if 'report' in st.session_state:
    report = st.session_state['report']
    
    # Load dashboard.html
    with open("dashboard.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # Inject report data as 'window.embeddedData'
    injection = f"<script>window.embeddedData = {json.dumps(report)};</script>"
    combined_html = html_content.replace("<head>", f"<head>\n{injection}")
    
    st.markdown("---")
    st.subheader("🔍 Visual Forensic Analysis")
    
    # Embed the original premium dashboard
    components.html(combined_html, height=1200, scrolling=True)
    
    st.markdown("---")
    st.download_button(
        label="Download Full Forensic Report (JSON)",
        data=json.dumps(report, indent=2),
        file_name="systeardown_report.json",
        mime="application/json"
    )

else:
    st.info("Ready for analysis. Please upload your data files and click 'Run Forensic Analysis'.")

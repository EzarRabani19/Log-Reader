import streamlit as st
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from streamlit_drawable_canvas import st_canvas
import io

st.set_page_config(page_title="Stratigraphic Log Digitizer", layout="wide")

st.title("🪨 Stratigraphic Column & Lithology Log Digitizer")
st.markdown(
    "Ekstrak batas lapisan, jenis litologi, dan profil ukuran butir dari gambar log stratigrafi "
    "menjadi **Kolom Stratigrafi Digital**, **CSV**, dan **LAS 2.0 (Lithology Code)**."
)

# --- STANDAR WARNA, KODE PETREL, & SKALA UKURAN BUTIR (LEBAR POLIGON) ---
LITHOLOGY_STANDARDS = {
    "Batulempung (Claystone / Shale)": {"color": "#7F8C8D", "hatch": "--", "grain_width": 0.25, "code": 1},
    "Batulanau (Siltstone)": {"color": "#95A5A6", "hatch": "..", "grain_width": 0.40, "code": 2},
    "Batupasir Halus (Fine Sandstone)": {"color": "#F9E79F", "hatch": ".", "grain_width": 0.55, "code": 3},
    "Batupasir Sedang (Medium Sandstone)": {"color": "#F4D03F", "hatch": "..", "grain_width": 0.70, "code": 4},
    "Batupasir Kasar (Coarse Sandstone)": {"color": "#F39C12", "hatch": "o.", "grain_width": 0.85, "code": 5},
    "Konglomerat / Breksi (Conglomerate)": {"color": "#D35400", "hatch": "O", "grain_width": 1.00, "code": 6},
    "Batugamping (Limestone)": {"color": "#5DADE2", "hatch": "+", "grain_width": 0.75, "code": 7},
    "Batubara (Coal)": {"color": "#1C2833", "hatch": "//", "grain_width": 0.30, "code": 8},
    "Tuf / Batuan Piroklastik (Tuff)": {"color": "#D7BDE2", "hatch": "vv", "grain_width": 0.60, "code": 9},
}

# --- SIDEBAR: UPLOAD & KALIBRASI ---
with st.sidebar:
    st.header("1. Upload Gambar Log Stratigrafi")
    uploaded_file = st.file_uploader("Pilih gambar log stratigrafi (PNG/JPG)", type=["png", "jpg", "jpeg"])

    st.header("2. Kalibrasi Sumbu Vertikal")
    depth_mode = st.radio(
        "Arah Pengukuran Vertikal:",
        ["Kedalaman Bawah Permukaan (Top -> Bottom)", "Ketebalan Singkapan / Measured Section (0 -> Top)"]
    )
    val_top = st.number_input("Nilai Vertikal Paling Atas (m)", value=0.0 if "Measured" in depth_mode else 1000.0, format="%.2f")
    val_bot = st.number_input("Nilai Vertikal Paling Bawah (m)", value=50.0 if "Measured" in depth_mode else 1050.0, format="%.2f")

    st.header("3. Pengaturan Deteksi Otomatis")
    color_tol = st.slider("Toleransi Kemiripan Warna Lapisan", 10, 120, 45)
    min_bed_px = st.slider("Ketebalan Minimum Lapisan (piksel)", 2, 30, 5)

# --- MAIN AREA ---
if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    orig_w, orig_h = image.size

    display_w = 550
    scale_factor = display_w / orig_w
    display_h = int(orig_h * scale_factor)
    resized_img = image.resize((display_w, display_h))
    img_np = np.array(resized_img)

    col1, col2 = st.columns([1.15, 1.15])

    with col1:
        st.subheader("1. Seleksi Kolom Litologi pada Gambar")
        st.info(
            "**Langkah:** Gambar **1 kotak merah (Rectangle)** tepat menutupi badan kolom litologi dari **batas paling atas** "
            "hingga **batas paling bawah** sesuai nilai kalibrasi di sidebar. Anda juga dapat mengedit/menambah lapisan secara manual di tabel sebelah kanan."
        )

        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.15)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=resized_img,
            update_streamlit=True,
            height=display_h,
            width=display_w,
            drawing

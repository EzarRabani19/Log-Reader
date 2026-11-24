import streamlit as st
import cv2
import numpy as np
import pandas as pd
from PIL import Image
from streamlit_drawable_canvas import st_canvas
import io

st.set_page_config(page_title="Well Log Digitizer dari Gambar", layout="wide")

st.title("🛢️ Well Log Image Digitizer")
st.markdown("Ekstrak data kurva *well log* (GR, RT, RHOB, NPHI, dll.) dari gambar menjadi file **CSV** atau **LAS**.")

# --- SIDEBAR: UPLOAD & KALIBRASI ---
with st.sidebar:
    st.header("1. Upload Gambar Log")
    uploaded_file = st.file_uploader("Pilih gambar log (PNG/JPG)", type=["png", "jpg", "jpeg"])
    
    st.header("2. Parameter Kalibrasi")
    log_name = st.text_input("Nama Kurva Log", value="GR")
    log_unit = st.text_input("Satuan Log", value="API")
    depth_unit = st.selectbox("Satuan Kedalaman", ["M", "FT"])
    
    st.subheader("Batas Sumbu X (Nilai Log)")
    is_log_scale = st.checkbox("Skala Logaritmik (misal: Resistivity)", value=False)
    x_min_val = st.number_input("Nilai X Kiri (Min)", value=0.0, format="%.4f")
    x_max_val = st.number_input("Nilai X Kanan (Max)", value=150.0, format="%.4f")
    
    st.subheader("Batas Sumbu Y (Kedalaman)")
    y_top_depth = st.number_input("Kedalaman Atas (Top)", value=1000.0, format="%.2f")
    y_bot_depth = st.number_input("Kedalaman Bawah (Bottom)", value=1100.0, format="%.2f")
    
    st.header("3. Metode Ekstraksi")
    mode = st.radio(
        "Pilih Mode:",
        ["Otomatis (Deteksi Warna Kurva)", "Manual (Klik Titik Kurva)"]
    )
    
    if mode == "Otomatis (Deteksi Warna Kurva)":
        target_color = st.color_picker("Pilih Warna Garis Kurva pada Gambar", "#000000")
        color_tol = st.slider("Toleransi Warna", 10, 150, 50)
        step_px = st.slider("Interval Sampling (piksel vertikal)", 1, 10, 2)

# --- MAIN AREA ---
if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    orig_w, orig_h = image.size
    
    # Resize gambar agar muat nyaman di layar namun rasio tetap terjaga
    display_w = 650
    scale_factor = display_w / orig_w
    display_h = int(orig_h * scale_factor)
    resized_img = image.resize((display_w, display_h))
    img_np = np.array(resized_img)

    col1, col2 = st.columns([1.3, 1])

    with col1:
        st.subheader("Area Kerja & Kalibrasi")
        
        if mode == "Otomatis (Deteksi Warna Kurva)":
            st.info(
                "**Langkah Kalibrasi:** Gambar **1 buah kotak (Rectangle)** yang membentang tepat dari "
                "**Nilai X Min (kiri)** ke **Nilai X Max (kanan)**, serta dari **Kedalaman Top (atas)** ke **Kedalaman Bottom (bawah)**."
            )
            drawing_mode = "rect"
        else:
            st.info(
                "**Langkah Manual:** Klik **2 titik pertama** sebagai batas kotak kalibrasi (Titik 1: Pojok Kiri-Atas [X_min, Top], "
                "Titik 2: Pojok Kanan-Bawah [X_max, Bottom]). Titik ke-3 dan seterusnya adalah **titik kurva log**."
            )
            drawing_mode = "point"

        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.2)",
            stroke_width=2,
            stroke_color="#FF0000",
            background_image=resized_img,
            update_streamlit=True,
            height=display_h,
            width=display_w,
            drawing_mode=drawing_mode,
            key="log_canvas",
        )

    with col2:
        st.subheader("Hasil Digitalisasi")
        df_result = None

        if canvas_result.json_data is not None:
            objects = canvas_result.json_data["objects"]

            # --- LOGIKA MODE OTOMATIS ---
            if mode == "Otomatis (Deteksi Warna Kurva)" and len(objects) > 0:
                rect = objects[-1]  # Ambil kotak terakhir yang digambar
                x0 = int(rect["left"])
                y0 = int(rect["top"])
                x1 = int(x0 + rect["width"] * rect["scaleX"])
                y1 = int(y0 + rect["height"] * rect["scaleY"])

                # Pastikan koordinat berada dalam batas gambar
                x0, x1 = max(0, min(x0, x1)), min(display_w, max(x0, x1))
                y0, y1 = max(0, min(y0

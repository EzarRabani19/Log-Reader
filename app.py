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
                y0, y1 = max(0, min(y0, y1)), min(display_h, max(y0, y1))

                if (x1 - x0) > 10 and (y1 - y0) > 10:
                    roi = img_np[y0:y1, x0:x1]
                    
                    # Konversi hex color picker ke RGB
                    hex_c = target_color.lstrip('#')
                    rgb_target = np.array([int(hex_c[i:i+2], 16) for i in (0, 2, 4)])

                    # Hitung jarak warna Euclidean di dalam kotak ROI
                    diff = np.linalg.norm(roi.astype(float) - rgb_target.astype(float), axis=2)
                    mask = diff <= color_tol

                    depths, values = [], []
                    for row_idx in range(0, roi.shape[0], step_px):
                        matched_x = np.where(mask[row_idx, :])[0]
                        if len(matched_x) > 0:
                            # Ambil median posisi piksel X jika garis kurva tebal
                            px_x = np.median(matched_x)
                            norm_x = px_x / (x1 - x0)
                            norm_y = row_idx / (y1 - y0)

                            depth = y_top_depth + norm_y * (y_bot_depth - y_top_depth)
                            if is_log_scale and x_min_val > 0 and x_max_val > 0:
                                log_min, log_max = np.log10(x_min_val), np.log10(x_max_val)
                                val = 10 ** (log_min + norm_x * (log_max - log_min))
                            else:
                                val = x_min_val + norm_x * (x_max_val - x_min_val)

                            depths.append(round(depth, 3))
                            values.append(round(val, 4))

                    if depths:
                        df_result = pd.DataFrame({"DEPTH": depths, log_name: values})
                    else:
                        st.warning("Tidak ada piksel warna yang cocok di dalam kotak. Coba naikkan 'Toleransi Warna' atau periksa warna target.")

            # --- LOGIKA MODE MANUAL ---
            elif mode == "Manual (Klik Titik Kurva)" and len(objects) >= 3:
                pts = [(obj["left"], obj["top"]) for obj in objects]
                x0, y0 = pts[0]  # Pojok kiri atas kalibrasi
                x1, y1 = pts[1]  # Pojok kanan bawah kalibrasi
                curve_pts = pts[2:]

                if abs(x1 - x0) > 5 and abs(y1 - y0) > 5:
                    depths, values = [], []
                    for px, py in curve_pts:
                        norm_x = (px - x0) / (x1 - x0)
                        norm_y = (py - y0) / (y1 - y0)

                        depth = y_top_depth + norm_y * (y_bot_depth - y_top_depth)
                        if is_log_scale and x_min_val > 0 and x_max_val > 0:
                            log_min, log_max = np.log10(x_min_val), np.log10(x_max_val)
                            val = 10 ** (log_min + norm_x * (log_max - log_min))
                        else:
                            val = x_min_val + norm_x * (x_max_val - x_min_val)

                        depths.append(round(depth, 3))
                        values.append(round(val, 4))

                    df_result = pd.DataFrame({"DEPTH": depths, log_name: values}).sort_values("DEPTH")

        # --- TAMPILKAN PLOT & TOMBOL DOWNLOAD ---
        if df_result is not None and not df_result.empty:
            st.success(f"Berhasil mengekstrak **{len(df_result)}** titik data!")
            
            # Preview grafik terbalik (kedalaman bertambah ke bawah)
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4, 6))
            ax.plot(df_result[log_name], df_result["DEPTH"], color="blue", linewidth=1.2)
            ax.set_ylim(y_bot_depth, y_top_depth)
            ax.set_xlim(x_min_val, x_max_val)
            if is_log_scale:
                ax.set_xscale("log")
            ax.set_xlabel(f"{log_name} ({log_unit})")
            ax.set_ylabel(f"Depth ({depth_unit})")
            ax.grid(True, which="both", linestyle="--", alpha=0.5)
            st.pyplot(fig)

            st.dataframe(df_result.head(10), use_container_width=True)

            # Export CSV
            csv_data = df_result.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download CSV",
                data=csv_data,
                file_name=f"digitized_{log_name}.csv",
                mime="text/csv"
            )

            # Export LAS 2.0
            las_buffer = io.StringIO()
            las_buffer.write("~VERSION INFORMATION\n")
            las_buffer.write(" VERS.                  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n")
            las_buffer.write(" WRAP.                   NO : ONE LINE PER DEPTH STEP\n")
            las_buffer.write("~WELL INFORMATION\n")
            las_buffer.write(f" STRT.{depth_unit}         {df_result['DEPTH'].min():.4f} : START DEPTH\n")
            las_buffer.write(f" STOP.{depth_unit}         {df_result['DEPTH'].max():.4f} : STOP DEPTH\n")
            las_buffer.write(f" STEP.{depth_unit}         {df_result['DEPTH'].diff().median():.4f} : STEP\n")
            las_buffer.write(" NULL.            -999.2500 : NULL VALUE\n")
            las_buffer.write("~CURVE INFORMATION\n")
            las_buffer.write(f" DEPT.{depth_unit}                  : 1  DEPTH\n")
            las_buffer.write(f" {log_name}.{log_unit}                  : 2  {log_name} CURVE\n")
            las_buffer.write("~ASCII LOG DATA\n")
            for _, row in df_result.iterrows():
                las_buffer.write(f" {row['DEPTH']:10.4f} {row[log_name]:12.4f}\n")

            st.download_button(
                label="⬇️ Download LAS 2.0 (Siap Import ke Petrel)",
                data=las_buffer.getvalue().encode("utf-8"),
                file_name=f"digitized_{log_name}.las",
                mime="text/plain"
            )
else:
    st.info("Silakan unggah gambar *well log* melalui panel di sebelah kiri untuk memulai.")

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
            drawing_mode="rect",
            key="strat_canvas",
        )

    with col2:
        st.subheader("2. Tabel Interval & Interpretasi Litologi")
        detected_beds = []

        if canvas_result.json_data is not None and len(canvas_result.json_data["objects"]) > 0:
            rect = canvas_result.json_data["objects"][-1]
            x0 = int(rect["left"])
            y0 = int(rect["top"])
            x1 = int(x0 + rect["width"] * rect["scaleX"])
            y1 = int(y0 + rect["height"] * rect["scaleY"])

            x0, x1 = max(0, min(x0, x1)), min(display_w, max(x0, x1))
            y0, y1 = max(0, min(y0, y1)), min(display_h, max(y0, y1))

            if (x1 - x0) > 5 and (y1 - y0) > 10:
                roi = img_np[y0:y1, x0:x1]
                roi_h, roi_w, _ = roi.shape

                # Ambil warna dominan (median) per baris horizontal untuk mendeteksi perubahan lapisan
                row_colors = np.median(roi, axis=1)

                bed_start_px = 0
                ref_color = row_colors[0]
                raw_segments = []

                for r in range(1, roi_h):
                    dist = np.linalg.norm(row_colors[r] - ref_color)
                    if dist > color_tol:
                        if (r - bed_start_px) >= min_bed_px:
                            raw_segments.append((bed_start_px, r, row_colors[bed_start_px:r].mean(axis=0)))
                        bed_start_px = r
                        ref_color = row_colors[r]

                if (roi_h - bed_start_px) >= min_bed_px:
                    raw_segments.append((bed_start_px, roi_h, row_colors[bed_start_px:roi_h].mean(axis=0)))

                # Pemetaan warna piksel ke jenis litologi terdekat & estimasi lebar poligon
                for idx, (seg_top, seg_bot, avg_rgb) in enumerate(raw_segments):
                    top_m = val_top + (seg_top / roi_h) * (val_bot - val_top)
                    bot_m = val_top + (seg_bot / roi_h) * (val_bot - val_top)

                    # Tebak litologi berdasarkan kecerahan & rona RGB dasar
                    r_val, g_val, b_val = avg_rgb
                    if r_val < 60 and g_val < 60 and b_val < 60:
                        guessed_lith = "Batubara (Coal)"
                    elif b_val > r_val + 15:
                        guessed_lith = "Batugamping (Limestone)"
                    elif r_val > 180 and g_val > 150 and b_val < 130:
                        guessed_lith = "Batupasir Sedang (Medium Sandstone)"
                    elif r_val > 160 and g_val < 130:
                        guessed_lith = "Konglomerat / Breksi (Conglomerate)"
                    else:
                        guessed_lith = "Batulempung (Claystone / Shale)"

                    detected_beds.append({
                        "Top (m)": round(top_m, 2),
                        "Bottom (m)": round(bot_m, 2),
                        "Litologi": guessed_lith,
                        "Struktur Sedimen / Fosil": "-"
                    })

        # Jika belum menarik kotak, sediakan template default agar tetap bisa diedit langsung
        if not detected_beds:
            detected_beds = [
                {"Top (m)": val_top, "Bottom (m)": round(val_top + (val_bot - val_top)*0.3, 2), "Litologi": "Batulempung (Claystone / Shale)", "Struktur Sedimen / Fosil": "Laminasi sejajar"},
                {"Top (m)": round(val_top + (val_bot - val_top)*0.3, 2), "Bottom (m)": round(val_top + (val_bot - val_top)*0.7, 2), "Litologi": "Batupasir Sedang (Medium Sandstone)", "Struktur Sedimen / Fosil": "Cross-bedding"},
                {"Top (m)": round(val_top + (val_bot - val_top)*0.7, 2), "Bottom (m)": val_bot, "Litologi": "Konglomerat / Breksi (Conglomerate)", "Struktur Sedimen / Fosil": "Graded bedding"},
            ]

        df_beds = pd.DataFrame(detected_beds)

        # Tabel interaktif agar user bisa mengoreksi litologi & kedalaman secara presisi
        edited_df = st.data_editor(
            df_beds,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Top (m)": st.column_config.NumberColumn(format="%.2f"),
                "Bottom (m)": st.column_config.NumberColumn(format="%.2f"),
                "Litologi": st.column_config.SelectboxColumn(
                    "Litologi",
                    options=list(LITHOLOGY_STANDARDS.keys()),
                    required=True,
                ),
                "Struktur Sedimen / Fosil": st.column_config.TextColumn("Struktur Sedimen / Fosil"),
            },
        )

    # --- SECTION 3: RENDER ULANG KOLOM STRATIGRAFI DIGITAL ---
    st.markdown("---")
    st.subheader("3. Hasil Rekonstruksi Kolom Stratigrafi Digital")

    if not edited_df.empty:
        edited_df["Ketebalan (m)"] = (edited_df["Bottom (m)"] - edited_df["Top (m)"]).abs().round(2)
        edited_df["Kode_Litologi"] = edited_df["Litologi"].map(lambda x: LITHOLOGY_STANDARDS[x]["code"])

        res_col1, res_col2 = st.columns([1.2, 1])

        with res_col1:
            fig, ax = plt.subplots(figsize=(5.5, 8))

            for _, row in edited_df.iterrows():
                y_start = row["Top (m)"]
                y_end = row["Bottom (m)"]
                height = y_end - y_start
                lith_info = LITHOLOGY_STANDARDS.get(
                    row["Litologi"],
                    {"color": "#BDC3C7", "hatch": "", "grain_width": 0.5}
                )

                rect_patch = patches.Rectangle(
                    (0, y_start),
                    lith_info["grain_width"],
                    height,
                    facecolor=lith_info["color"],
                    edgecolor="black",
                    linewidth=1.0,
                    hatch=lith_info["hatch"]
                )
                ax.add_patch(rect_patch)

                # Tambahkan anotasi struktur sedimen di samping kanan lapisan jika ada
                note = str(row["Struktur Sedimen / Fosil"]).strip()
                if note and note != "-":
                    mid_y = (y_start + y_end) / 2.0
                    ax.text(
                        lith_info["grain_width"] + 0.04,
                        mid_y,
                        note,
                        va="center",
                        fontsize=8.5,
                        color="#2C3E50"
                    )

            # Atur batas sumbu vertikal sesuai arah pengukuran
            y_min_plot = min(edited_df["Top (m)"].min(), edited_df["Bottom (m)"].min())
            y_max_plot = max(edited_df["Top (m)"].max(), edited_df["Bottom (m)"].max())

            if "Top -> Bottom" in depth_mode:
                ax.set_ylim(y_max_plot, y_min_plot)
                ax.set_ylabel("Kedalaman (m)", fontweight="bold")
            else:
                ax.set_ylim(y_min_plot, y_max_plot)
                ax.set_ylabel("Ketebalan Kumulatif / Measured Section (m)", fontweight="bold")

            ax.set_xlim(0, 1.45)
            ax.set_xticks([0.25, 0.40, 0.55, 0.70, 0.85, 1.00])
            ax.set_xticklabels(["Clay", "Silt", "vf-f", "m", "c-vc", "Congl"], fontsize=8.5)
            ax.set_xlabel("Profil Ukuran Butir (Grain Size)", fontweight="bold")
            ax.set_title("Kolom Stratigrafi Terdigitalisasi", fontweight="bold", pad=12)
            ax.grid(axis="x", linestyle=":", alpha=0.5)

            st.pyplot(fig)

        with res_col2:
            st.markdown("#### Ringkasan Proporsi Litologi & Ekspor Data")
            summary = edited_df.groupby("Litologi")["Ketebalan (m)"].sum().reset_index()
            summary["Persentase (%)"] = (summary["Ketebalan (m)"] / summary["Ketebalan (m)"].sum() * 100).round(1)
            st.dataframe(summary, use_container_width=True, hide_index=True)

            # 1. Export CSV Interval Stratigrafi
            csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="⬇️ Download Tabel Stratigrafi (CSV)",
                data=csv_bytes,
                file_name="stratigraphic_column_intervals.csv",
                mime="text/csv"
            )

            # 2. Export LAS 2.0 (Discrete Lithology Log setiap 0.1 m untuk Petrel)
            step_m = 0.1
            d_start = min(edited_df["Top (m)"].min(), edited_df["Bottom (m)"].min())
            d_stop = max(edited_df["Top (m)"].max(), edited_df["Bottom (m)"].max())
            depths_grid = np.arange(d_start, d_stop + step_m, step_m)

            las_buf = io.StringIO()
            las_buf.write("~VERSION INFORMATION\n")
            las_buf.write(" VERS.                  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n")
            las_buf.write(" WRAP.                   NO : ONE LINE PER DEPTH STEP\n")
            las_buf.write("~WELL INFORMATION\n")
            las_buf.write(f" STRT.M              {d_start:.4f} : START DEPTH\n")
            las_buf.write(f" STOP.M              {d_stop:.4f} : STOP DEPTH\n")
            las_buf.write(f" STEP.M              {step_m:.4f} : STEP\n")
            las_buf.write(" NULL.            -999.2500 : NULL VALUE\n")
            las_buf.write("~CURVE INFORMATION\n")
            las_buf.write(" DEPT.M                     : 1  DEPTH\n")
            las_buf.write(" LITH_CODE.NONE             : 2  DISCRETE LITHOLOGY CODE\n")
            las_buf.write("~ASCII LOG DATA\n")

            for d in depths_grid:
                code_val = -999.25
                for _, r in edited_df.iterrows():
                    low, high = min(r["Top (m)"], r["Bottom (m)"]), max(r["Top (m)"], r["Bottom (m)"])
                    if low <= d <= high:
                        code_val = r["Kode_Litologi"]
                        break
                las_buf.write(f" {d:10.4f} {code_val:12.4f}\n")

            st.download_button(
                label="⬇️ Download Discrete Lithology Log (LAS 2.0 untuk Petrel)",
                data=las_buf.getvalue().encode("utf-8"),
                file_name="lithology_facies_log.las",
                mime="text/plain"
            )
else:
    st.info("Unggah foto singkapan terukur (*measured section*) atau gambar kolom stratigrafi di sidebar untuk memulai.")

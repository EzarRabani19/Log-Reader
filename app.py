import streamlit as st
import numpy as np
import pandas as pd
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
from streamlit_drawable_canvas import st_canvas
import io

st.set_page_config(page_title="Detailed Stratigraphic Log Digitizer", layout="wide")

st.title("🪨 Detailed Stratigraphic Column & Lithology Log Digitizer")
st.markdown(
    "Digitalisasi gambar log stratigrafi menjadi **Kolom Stratigrafi Multi-Track Detail** "
    "(Skala Kedalaman, Litologi & Profil Ukuran Butir Wentworth, Simbol Struktur Sedimen/Fosil, "
    "Kurva Tren Sikuen FU/CU, dan Lingkungan Pengendapan) serta ekspor ke **PNG/PDF, CSV, dan LAS 2.0**."
)

# --- STANDAR LITOLOGI & SKALA WENTWORTH ---
LITHOLOGY_STANDARDS = {
    "Batulempung (Claystone / Shale)": {"color": "#7F8C8D", "hatch": "--", "grain_width": 0.20, "code": 1, "short": "Clst"},
    "Batulanau (Siltstone)": {"color": "#95A5A6", "hatch": "..", "grain_width": 0.32, "code": 2, "short": "Slst"},
    "Batupasir Sangat Halus (Very Fine Sst)": {"color": "#FCF3CF", "hatch": ".", "grain_width": 0.44, "code": 3, "short": "vf-Sst"},
    "Batupasir Halus (Fine Sandstone)": {"color": "#F9E79F", "hatch": ".", "grain_width": 0.56, "code": 4, "short": "f-Sst"},
    "Batupasir Sedang (Medium Sandstone)": {"color": "#F4D03F", "hatch": "..", "grain_width": 0.68, "code": 5, "short": "m-Sst"},
    "Batupasir Kasar (Coarse Sandstone)": {"color": "#F39C12", "hatch": "o.", "grain_width": 0.80, "code": 6, "short": "c-Sst"},
    "Batupasir Sangat Kasar (Very Coarse Sst)": {"color": "#E67E22", "hatch": "oo", "grain_width": 0.90, "code": 7, "short": "vc-Sst"},
    "Konglomerat / Breksi (Conglomerate)": {"color": "#D35400", "hatch": "O", "grain_width": 1.00, "code": 8, "short": "Cgl"},
    "Batugamping Klastik / Kalkarenit": {"color": "#5DADE2", "hatch": "+.", "grain_width": 0.68, "code": 9, "short": "Calcar"},
    "Batugamping Terumbu / Boundstone": {"color": "#2E86C1", "hatch": "++", "grain_width": 0.85, "code": 10, "short": "Lst-R"},
    "Napal (Marl)": {"color": "#76D7C4", "hatch": "-+", "grain_width": 0.35, "code": 11, "short": "Marl"},
    "Batubara (Coal)": {"color": "#1C2833", "hatch": "//", "grain_width": 0.22, "code": 12, "short": "Coal"},
    "Tuf / Batuan Piroklastik (Tuff)": {"color": "#D7BDE2", "hatch": "vv", "grain_width": 0.55, "code": 13, "short": "Tuff"},
}

SED_STRUCTURES = [
    "Tidak ada (-)",
    "Laminasi Sejajar (Parallel Lamination)",
    "Cross-Bedding (Silang Siur)",
    "Ripple Marks (Gelembur Gelombang)",
    "Graded Bedding (Perlapisan Bersusun)",
    "Bioturbasi / Ichnofossil",
    "Fosil Cangkang / Foraminifera",
    "Sisa Tumbuhan / Rootlets",
    "Nodul / Konkresi"
]

CONTACT_TYPES = ["Tajam (Sharp)", "Erosional (Scoured)", "Gradasi (Gradational)"]

# --- FUNGSI GAMBAR IKON STRUKTUR SEDIMEN & FOSIL ---
def draw_sedimentary_symbol(ax, x_center, y_center, structure_name):
    if "Parallel" in structure_name:
        for dy in [-0.15, 0, 0.15]:
            ax.plot([x_center - 0.28, x_center + 0.28], [y_center + dy, y_center + dy], color="black", lw=1.0)
    elif "Cross-Bedding" in structure_name:
        ax.plot([x_center - 0.28, x_center + 0.28], [y_center - 0.18, y_center - 0.18], color="black", lw=1.0)
        ax.plot([x_center - 0.28, x_center + 0.28], [y_center + 0.18, y_center + 0.18], color="black", lw=1.0)
        x_curve = np.linspace(x_center - 0.25, x_center + 0.25, 20)
        y_curve = y_center - 0.18 + 0.36 * ((x_curve - (x_center - 0.25)) / 0.50) ** 1.8
        ax.plot(x_curve, y_curve, color="black", lw=1.1)
    elif "Ripple" in structure_name:
        x_w = np.linspace(x_center - 0.28, x_center + 0.28, 40)
        y_w = y_center + 0.08 * np.sin((x_w - x_center) * 22)
        ax.plot(x_w, y_w, color="black", lw=1.1)
    elif "Graded" in structure_name:
        ax.scatter([x_center - 0.15, x_center, x_center + 0.15], [y_center - 0.12]*3, s=16, color="black")
        ax.scatter([x_center - 0.1, x_center + 0.1], [y_center]*2, s=7, color="black")
        ax.scatter([x_center - 0.12, x_center, x_center + 0.12], [y_center + 0.12]*3, s=2, color="black")
    elif "Bioturbasi" in structure_name:
        ax.plot([x_center - 0.1, x_center - 0.1, x_center + 0.1, x_center + 0.1],
                [y_center + 0.15, y_center - 0.15, y_center - 0.15, y_center + 0.15], color="#6E2C00", lw=1.3)
    elif "Fosil" in structure_name:
        arc = patches.Arc((x_center, y_center - 0.05), 0.32, 0.28, angle=0, theta1=0, theta2=180, color="#154360", lw=1.3)
        ax.add_patch(arc)
        ax.plot([x_center - 0.16, x_center + 0.16], [y_center - 0.05, y_center - 0.05], color="#154360", lw=1.1)
    elif "Tumbuhan" in structure_name:
        ax.plot([x_center, x_center], [y_center + 0.18, y_center - 0.18], color="#145A32", lw=1.2)
        ax.plot([x_center, x_center - 0.15], [y_center, y_center - 0.12], color="#145A32", lw=1.0)
        ax.plot([x_center, x_center + 0.15], [y_center - 0.04, y_center - 0.16], color="#145A32", lw=1.0)
    elif "Nodul" in structure_name:
        ell = patches.Ellipse((x_center, y_center), 0.34, 0.18, facecolor="#5D6D7E", edgecolor="black", lw=1.0)
        ax.add_patch(ell)

# --- SIDEBAR: UPLOAD & KALIBRASI ---
with st.sidebar:
    st.header("1. Informasi Header Log")
    well_or_section_name = st.text_input("Nama Sumur / Lintasan Singkapan", value="Lintasan Sungai Citarum - MS 01")
    location_info = st.text_input("Lokasi / Formasi", value="Formasi Jatiluhur / Cekungan Jawa Barat Utara")

    st.header("2. Upload Gambar Log Stratigrafi")
    uploaded_file = st.file_uploader("Pilih gambar log stratigrafi (PNG/JPG)", type=["png", "jpg", "jpeg"])

    st.header("3. Kalibrasi Sumbu Vertikal")
    depth_mode = st.radio(
        "Arah Pengukuran Vertikal:",
        ["Ketebalan Singkapan / Measured Section (0 -> Top)", "Kedalaman Bawah Permukaan (Top -> Bottom)"]
    )
    val_top = st.number_input("Nilai Vertikal Paling Atas (m)", value=25.0 if "Measured" in depth_mode else 1000.0, format="%.2f")
    val_bot = st.number_input("Nilai Vertikal Paling Bawah (m)", value=0.0 if "Measured" in depth_mode else 1025.0, format="%.2f")

    st.header("4. Pengaturan Deteksi Otomatis")
    color_tol = st.slider("Toleransi Kemiripan Warna Lapisan", 10, 120, 45)
    min_bed_px = st.slider("Ketebalan Minimum Lapisan (piksel)", 2, 30, 5)

# --- MAIN AREA ---
if uploaded_file is not None:
    image = Image.open(uploaded_file).convert("RGB")
    orig_w, orig_h = image.size

    display_w = 500
    scale_factor = display_w / orig_w
    display_h = int(orig_h * scale_factor)
    resized_img = image.resize((display_w, display_h))
    img_np = np.array(resized_img)

    col1, col2 = st.columns([1.0, 1.35])

    with col1:
        st.subheader("1. Seleksi Kolom Litologi pada Gambar")
        st.info(
            "Tarik **1 kotak merah** menutupi badan kolom litologi dari **batas paling atas** hingga **batas paling bawah** "
            "sesuai nilai kalibrasi di sidebar."
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
            key="strat_canvas_detail",
        )

    with col2:
        st.subheader("2. Tabel Interval & Atribut Geologi")
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

                for idx, (seg_top, seg_bot, avg_rgb) in enumerate(raw_segments):
                    top_m = val_top + (seg_top / roi_h) * (val_bot - val_top)
                    bot_m = val_top + (seg_bot / roi_h) * (val_bot - val_top)

                    r_val, g_val, b_val = avg_rgb
                    if r_val < 60 and g_val < 60 and b_val < 60:
                        guessed_lith = "Batubara (Coal)"
                    elif b_val > r_val + 15:
                        guessed_lith = "Batugamping Klastik / Kalkarenit"
                    elif r_val > 180 and g_val > 150 and b_val < 130:
                        guessed_lith = "Batupasir Sedang (Medium Sandstone)"
                    elif r_val > 160 and g_val < 130:
                        guessed_lith = "Konglomerat / Breksi (Conglomerate)"
                    else:
                        guessed_lith = "Batulempung (Claystone / Shale)"

                    detected_beds.append({
                        "Top (m)": round(top_m, 2),
                        "Bottom (m)": round(bot_m, 2),
                        "Formasi / Satuan": "Satuan A",
                        "Litologi": guessed_lith,
                        "Kontak Bawah": "Tajam (Sharp)",
                        "Struktur & Fosil": "Tidak ada (-)",
                        "Lingkungan & Deskripsi": "Endapan klastik"
                    })

        if not detected_beds:
            # Template realistis sikuen delta/fluvial jika user belum menggambar kotak
            span = val_bot - val_top
            detected_beds = [
                {
                    "Top (m)": round(val_top, 2),
                    "Bottom (m)": round(val_top + span * 0.25, 2),
                    "Formasi / Satuan": "Anggota Atas",
                    "Litologi": "Batulempung (Claystone / Shale)",
                    "Kontak Bawah": "Gradasi (Gradational)",
                    "Struktur & Fosil": "Sisa Tumbuhan / Rootlets",
                    "Lingkungan & Deskripsi": "Floodplain / Marsh: lempung abu-abu gelap karbonan"
                },
                {
                    "Top (m)": round(val_top + span * 0.25, 2),
                    "Bottom (m)": round(val_top + span * 0.50, 2),
                    "Formasi / Satuan": "Anggota Atas",
                    "Litologi": "Batupasir Halus (Fine Sandstone)",
                    "Kontak Bawah": "Gradasi (Gradational)",
                    "Struktur & Fosil": "Ripple Marks (Gelembur Gelombang)",
                    "Lingkungan & Deskripsi": "Point Bar (Upper): pasir halus kuarsa, sortasi baik"
                },
                {
                    "Top (m)": round(val_top + span * 0.50, 2),
                    "Bottom (m)": round(val_top + span * 0.80, 2),
                    "Formasi / Satuan": "Anggota Bawah",
                    "Litologi": "Batupasir Kasar (Coarse Sandstone)",
                    "Kontak Bawah": "Erosional (Scoured)",
                    "Struktur & Fosil": "Cross-Bedding (Silang Siur)",
                    "Lingkungan & Deskripsi": "Fluvial Channel: pasir kasar kecokelatan, trough cross-bed"
                },
                {
                    "Top (m)": round(val_top + span * 0.80, 2),
                    "Bottom (m)": round(val_bot, 2),
                    "Formasi / Satuan": "Anggota Bawah",
                    "Litologi": "Batugamping Klastik / Kalkarenit",
                    "Kontak Bawah": "Tajam (Sharp)",
                    "Struktur & Fosil": "Fosil Cangkang / Foraminifera",
                    "Lingkungan & Deskripsi": "Shallow Marine: kalkarenit bioklastik"
                },
            ]

        df_beds = pd.DataFrame(detected_beds)

        edited_df = st.data_editor(
            df_beds,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Top (m)": st.column_config.NumberColumn(format="%.2f"),
                "Bottom (m)": st.column_config.NumberColumn(format="%.2f"),
                "Formasi / Satuan": st.column_config.TextColumn("Formasi / Satuan"),
                "Litologi": st.column_config.SelectboxColumn(
                    "Litologi",
                    options=list(LITHOLOGY_STANDARDS.keys()),
                    required=True,
                ),
                "Kontak Bawah": st.column_config.SelectboxColumn(
                    "Kontak Bawah",
                    options=CONTACT_TYPES,
                    required=True,
                ),
                "Struktur & Fosil": st.column_config.SelectboxColumn(
                    "Struktur & Fosil",
                    options=SED_STRUCTURES,
                    required=True,
                ),
                "Lingkungan & Deskripsi": st.column_config.TextColumn("Lingkungan & Deskripsi"),
            },
        )

    # --- SECTION 3: REKONSTRUKSI KOLOM STRATIGRAFI DIGITAL MULTI-TRACK ---
    st.markdown("---")
    st.subheader("3. Hasil Rekonstruksi Kolom Stratigrafi Digital (Multi-Track)")

    if not edited_df.empty:
        edited_df["Ketebalan (m)"] = (edited_df["Bottom (m)"] - edited_df["Top (m)"]).abs().round(2)
        edited_df["Kode_Litologi"] = edited_df["Litologi"].map(lambda x: LITHOLOGY_STANDARDS[x]["code"])

        # Urutkan dari elevasi atas ke bawah untuk rendering yang konsisten
        is_subsurface = "Top -> Bottom" in depth_mode
        df_plot = edited_df.sort_values("Top (m)", ascending=is_subsurface).reset_index(drop=True)

        y_min_plot = min(df_plot["Top (m)"].min(), df_plot["Bottom (m)"].min())
        y_max_plot = max(df_plot["Top (m)"].max(), df_plot["Bottom (m)"].max())

        # Buat Figure Multi-Track dengan GridSpec
        fig = plt.figure(figsize=(13, 10), dpi=150)
        gs = fig.add_gridspec(1, 4, width_ratios=[0.9, 2.3, 1.1, 2.7], wspace=0.06)

        ax_fm = fig.add_subplot(gs[0])
        ax_lith = fig.add_subplot(gs[1], sharey=ax_fm)
        ax_struct = fig.add_subplot(gs[2], sharey=ax_fm)
        ax_desc = fig.add_subplot(gs[3], sharey=ax_fm)

        # Judul Utama Header Log
        fig.suptitle(
            f"KOLOM STRATIGRAFI TERUKUR: {well_or_section_name.upper()}\n{location_info}",
            fontsize=13, fontweight="bold", y=0.97
        )

        # --- TRACK 1: FORMASI & SKALA VERTIKAL ---
        ax_fm.set_xlim(0, 1)
        ax_fm.set_xticks([])
        ax_fm.set_title("Formasi &\nSkala (m)", fontsize=9.5, fontweight="bold", pad=10)
        ax_fm.set_ylabel("Kedalaman (m)" if is_subsurface else "Ketebalan Kumulatif (m)", fontweight="bold", fontsize=10)

        # Gabungkan blok formasi yang berurutan
        fm_groups = []
        for _, r in df_plot.iterrows():
            fm_name = str(r["Formasi / Satuan"]).strip()
            y1_b, y2_b = r["Top (m)"], r["Bottom (m)"]
            if fm_groups and fm_groups[-1]["fm"] == fm_name:
                fm_groups[-1]["y2"] = y2_b
            else:
                fm_groups.append({"fm": fm_name, "y1": y1_b, "y2": y2_b})

        for grp in fm_groups:
            y_lo, y_hi = min(grp["y1"], grp["y2"]), max(grp["y1"], grp["y2"])
            rect_fm = patches.Rectangle((0, y_lo), 1, y_hi - y_lo, facecolor="#F8F9F9", edgecolor="black", lw=1.0)
            ax_fm.add_patch(rect_fm)
            ax_fm.text(0.5, (y_lo + y_hi) / 2, grp["fm"], ha="center", va="center", rotation=90, fontsize=8.5, fontweight="bold")

        # --- TRACK 2: KOLOM LITOLOGI, PROFIL UKURAN BUTIR & KURVA TREN ---
        ax_lith.set_xlim(0, 1.15)
        ax_lith.set_xticks([0.20, 0.32, 0.44, 0.56, 0.68, 0.80, 0.90, 1.00])
        ax_lith.set_xticklabels(["Cl", "Si", "vf", "f", "m", "c", "vc", "Cgl"], fontsize=8, fontweight="bold")
        ax_lith.set_title("Litologi & Profil Ukuran Butir\n(Skala Wentworth + Tren Sikuen)", fontsize=9.5, fontweight="bold", pad=10)
        ax_lith.grid(axis="x", linestyle=":", color="#BDC3C7", alpha=0.8)
        plt.setp(ax_lith.get_yticklabels(), visible=False)

        trend_x, trend_y = [], []

        for idx, row in df_plot.iterrows():
            y_t, y_b = row["Top (m)"], row["Bottom (m)"]
            y_lo, y_hi = min(y_t, y_b), max(y_t, y_b)
            h_bed = y_hi - y_lo
            lith_info = LITHOLOGY_STANDARDS[row["Litologi"]]
            w_grain = lith_info["grain_width"]

            # Poligon utama lapisan
            rect_bed = patches.Rectangle(
                (0, y_lo), w_grain, h_bed,
                facecolor=lith_info["color"],
                edgecolor="black",
                linewidth=0.9,
                hatch=lith_info["hatch"],
                zorder=2
            )
            ax_lith.add_patch(rect_bed)

            # Gambar variasi garis kontak bawah lapisan (Sharp, Erosional/Bergelombang, atau Gradational/Putus-putus)
            contact = row["Kontak Bawah"]
            if "Erosional" in contact:
                xw_c = np.linspace(0, w_grain, 35)
                yw_c = y_b + (h_bed * 0.04) * np.sin(xw_c * 45)
                ax_lith.plot(xw_c, yw_c, color="black", lw=1.4, zorder=4)
            elif "Gradasi" in contact:
                ax_lith.plot([0, w_grain], [y_b, y_b], color="black", lw=1.1, linestyle="--", zorder=4)

            # Titik tengah lapisan untuk kurva tren ukuran butir
            trend_x.append(w_grain)
            trend_y.append((y_lo + y_hi) / 2.0)

        # Plot Kurva Tren Ukuran Butir & Label FU / CU
        if len(trend_x) >= 2:
            ax_lith.plot(trend_x, trend_y, color="#C0392B", linewidth=1.8, marker="o", markersize=4, zorder=5, label="Tren Butir")
            for i in range(len(trend_x) - 1):
                # Bandingkan lapisan bawah (i+1) ke lapisan atas (i) dalam urutan vertikal dari atas ke bawah
                w_upper, w_lower = trend_x[i], trend_x[i + 1]
                y_mid_pair = (trend_y[i] + trend_y[i + 1]) / 2.0
                if w_upper < w_lower - 0.05:
                    ax_lith.text(1.03, y_mid_pair, "FU ▲", fontsize=7.5, color="#1F618D", fontweight="bold", va="center")
                elif w_upper > w_lower + 0.05:
                    ax_lith.text(1.03, y_mid_pair, "CU ▼", fontsize=7.5, color="#B03A2E", fontweight="bold", va="center")

        # --- TRACK 3: SIMBOL STRUKTUR SEDIMEN & FOSIL ---
        ax_struct.set_xlim(0, 1)
        ax_struct.set_xticks([])
        ax_struct.set_title("Struktur &\nFosil", fontsize=9.5, fontweight="bold", pad=10)
        plt.setp(ax_struct.get_yticklabels(), visible=False)

        for _, row in df_plot.iterrows():
            y_lo, y_hi = min(row["Top (m)"], row["Bottom (m)"]), max(row["Top (m)"], row["Bottom (m)"])
            ax_struct.add_patch(patches.Rectangle((0, y_lo), 1, y_hi - y_lo, facecolor="white", edgecolor="#D5D8DC", lw=0.7))
            draw_sedimentary_symbol(ax_struct, 0.5, (y_lo + y_hi) / 2.0, row["Struktur & Fosil"])

        # --- TRACK 4: DESKRIPSI LITOLOGI & LINGKUNGAN PENGENDAPAN ---
        ax_desc.set_xlim(0, 1)
        ax_desc.set_xticks([])
        ax_desc.set_title("Deskripsi Litologi &\nLingkungan Pengendapan", fontsize=9.5, fontweight="bold", pad=10)
        plt.setp(ax_desc.get_yticklabels(), visible=False)

        for _, row in df_plot.iterrows():
            y_lo, y_hi = min(row["Top (m)"], row["Bottom (m)"]), max(row["Top (m)"], row["Bottom (m)"])
            ax_desc.add_patch(patches.Rectangle((0, y_lo), 1, y_hi - y_lo, facecolor="white", edgecolor="#D5D8DC", lw=0.7))
            short_lith = LITHOLOGY_STANDARDS[row["Litologi"]]["short"]
            desc_text = f"[{short_lith} | {row['Ketebalan (m)']}m] {row['Lingkungan & Deskripsi']}"
            ax_desc.text(0.03, (y_lo + y_hi) / 2.0, desc_text, va="center", ha="left", fontsize=8, wrap=True)

        # Atur orientasi sumbu Y global
        if is_subsurface:
            ax_fm.set_ylim(y_max_plot, y_min_plot)
        else:
            ax_fm.set_ylim(y_min_plot, y_max_plot)

        # Legenda Litologi yang digunakan di bawah figure
        used_liths = df_plot["Litologi"].unique()
        legend_handles = [
            patches.Patch(
                facecolor=LITHOLOGY_STANDARDS[l]["color"],
                edgecolor="black",
                hatch=LITHOLOGY_STANDARDS[l]["hatch"],
                label=l
            ) for l in used_liths
        ]
        fig.legend(
            handles=legend_handles,
            loc="lower center",
            ncol=3,
            fontsize=8,
            frameon=True,
            bbox_to_anchor=(0.5, -0.02)
        )

        st.pyplot(fig, use_container_width=True)

        # --- PANEL RINGKASAN & EKSPOR MULTI-FORMAT ---
        st.markdown("#### Ringkasan Statistik Fasies & Ekspor File")
        exp_col1, exp_col2 = st.columns([1.2, 1])

        with exp_col1:
            summary = edited_df.groupby("Litologi")["Ketebalan (m)"].sum().reset_index()
            summary["Proporsi (%)"] = (summary["Ketebalan (m)"] / summary["Ketebalan (m)"].sum() * 100).round(1)
            st.dataframe(summary, use_container_width=True, hide_index=True)

        with exp_col2:
            # 1. Export Gambar Resolusi Tinggi (PNG)
            img_buf = io.BytesIO()
            fig.savefig(img_buf, format="png", dpi=300, bbox_inches="tight")
            st.download_button(
                label="🖼️ Download Kolom Stratigrafi Resolusi Tinggi (PNG 300 DPI)",
                data=img_buf.getvalue(),
                file_name="kolom_stratigrafi_detail.png",
                mime="image/png"
            )

            # 2. Export CSV
            csv_bytes = edited_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📄 Download Data Interval Stratigrafi (CSV)",
                data=csv_bytes,
                file_name="data_stratigrafi_detail.csv",
                mime="text/csv"
            )

            # 3. Export LAS 2.0 (Petrel Discrete Facies Log)
            step_m = 0.1
            depths_grid = np.arange(y_min_plot, y_max_plot + step_m, step_m)
            las_buf = io.StringIO()
            las_buf.write("~VERSION INFORMATION\n")
            las_buf.write(" VERS.                  2.0 : CWLS LOG ASCII STANDARD - VERSION 2.0\n")
            las_buf.write(" WRAP.                   NO : ONE LINE PER DEPTH STEP\n")
            las_buf.write("~WELL INFORMATION\n")
            las_buf.write(f" WELL.               {well_or_section_name} : WELL OR SECTION NAME\n")
            las_buf.write(f" STRT.M              {y_min_plot:.4f} : START DEPTH\n")
            las_buf.write(f" STOP.M              {y_max_plot:.4f} : STOP DEPTH\n")
            las_buf.write(f" STEP.M              {step_m:.4f} : STEP\n")
            las_buf.write(" NULL.            -999.2500 : NULL VALUE\n")
            las_buf.write("~CURVE INFORMATION\n")
            las_buf.write(" DEPT.M

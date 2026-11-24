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
    elif "Tumbuhan"

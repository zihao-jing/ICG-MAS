import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd
import numpy as np
import matplotlib.font_manager as font_manager


_FONT_REG  = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
_FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf"

prop            = font_manager.FontProperties(fname=_FONT_REG,  size=38)
prop_bold       = font_manager.FontProperties(fname=_FONT_BOLD, size=32)
prop_bold_large = font_manager.FontProperties(fname=_FONT_BOLD, size=44)

# Table 4 — Local importance failure (AUC for predicting gold criticality)
# One panel per model; 4 rings = Relevance / Uniqueness / Importance / Overall AUC.
# Overall Spearman is noted as a text annotation below each panel label, not plotted.

model_data = [
    {
        "METRIC": ["", "Relevance", "Uniqueness", "Importance", "Overall AUC"],
        "AUC":    [0,  0.519,       0.855,         0.791,        0.885],
        "MODEL":  "Gemma-4-31B",
        "SPEARMAN": "+0.51",
    },
    {
        "METRIC": ["", "Relevance", "Uniqueness", "Importance", "Overall AUC"],
        "AUC":    [0,  0.505,       0.790,         0.728,        0.757],
        "MODEL":  "Gemini-FL",
        "SPEARMAN": "+0.34",
    },
    {
        "METRIC": ["", "Relevance", "Uniqueness", "Importance", "Overall AUC"],
        "AUC":    [0,  0.501,       0.761,         0.696,        0.744],
        "MODEL":  "Qwen-235B",
        "SPEARMAN": "+0.33",
    },
    {
        "METRIC": ["", "Relevance", "Uniqueness", "Importance", "Overall AUC"],
        "AUC":    [0,  0.518,       0.795,         0.729,        0.746],
        "MODEL":  "Mistral-S",
        "SPEARMAN": "+0.33",
    },
]

# Exact color sequence from polar_round_4.py (index 0 = dummy, never drawn)
ring_colours = [
    "#a05195",
    "#d45087",
    "#f95d6a",
    "#ff7c43",
    "#ffa600",
]

data_len = 5  # 1 dummy + 4 real rings
MAX_VALUE = 1.0  # AUC full ring = 1.0; ticks shown at 0.0, 0.2, 0.4, 0.6, 0.8
# Angular offsets (radians) to push value labels past the bar-end dot.
# AUC bars range from ~π (0.5) to ~5.6 rad (0.885), so a small offset suffices.
number_offset = [1.6, 0.14, 0.12, 0.12, 0.10]

fig, axes = plt.subplots(
    1, 4, figsize=(50, 18), subplot_kw=dict(polar=True, frameon=False)
)
plt.subplots_adjust(wspace=0.10)


def draw_figure(model_dict, ax):
    df = pd.DataFrame({"METRIC": model_dict["METRIC"], "AUC": model_dict["AUC"]})
    model_name = model_dict["MODEL"]
    spearman = model_dict["SPEARMAN"]

    ring_height = 0.8
    r = ring_height / 2.0
    s = np.pi * (r**2) * 4300  # scatter dot area
    angle_max = 2  # full ring = 2π

    def pct2rad(p):
        return (np.asarray(p) / MAX_VALUE) * 2 * np.pi

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ticks_pct = np.array([0.0, 0.2, 0.4, 0.6, 0.8])
    ax.set_xticks(pct2rad(ticks_pct))
    ax.set_xticklabels([f"{t:.1f}" for t in ticks_pct], fontproperties=prop)
    ax.yaxis.grid(False)
    ax.set_yticklabels([])

    # Grey background rings + coloured origin dot
    for i in range(data_len):
        full_arc = MAX_VALUE * angle_max * np.pi / MAX_VALUE  # = 2π
        if i == 0:
            ax.barh(i, full_arc, color="none", height=ring_height)
            continue
        ax.barh(i, full_arc, color="grey", alpha=0.1, height=ring_height)
        ax.scatter(0, i, s=s, color=ring_colours[i], zorder=3)

    # Coloured data bars
    for i in range(data_len):
        val = df["AUC"][i] * angle_max * np.pi / MAX_VALUE
        if i == 0:
            ax.barh(i, val, color="none", height=ring_height)
            continue
        ax.barh(i, val, color=ring_colours[i], height=ring_height, label=df["METRIC"][i])
        ax.scatter(val, i, s=s, color=ring_colours[i], zorder=3)
        ax.text(
            val + number_offset[i],
            i + 0.5,
            f"{df['AUC'][i]:.3f}",
            ha="left", va="center",
            color="black", fontweight="bold",
            fontproperties=prop_bold, fontsize=40,
        )

    # Model name label (centre-bottom of panel)
    ax.text(
        0, -0.6, model_name,
        ha="center", va="center",
        color="black", fontweight="bold",
        fontproperties=prop_bold, fontsize=48,
        bbox=dict(
            boxstyle="round,pad=0.1,rounding_size=0.5",
            facecolor="lightgreen", edgecolor="lightgreen",
            linewidth=0.1, alpha=0.5,
        ),
    )

    # Overall Spearman annotation — below model name, not plotted as a ring
    ax.text(
        0, -1.15,
        f"ρ = {spearman}",
        ha="center", va="center",
        color="#444444",
        fontproperties=prop, fontsize=36,
    )


for ax, model_dict in zip(axes, model_data):
    draw_figure(model_dict, ax)

# Global legend: one swatch per metric
handles = [
    FancyBboxPatch(
        (0, 0), 1, 2,
        boxstyle="round,rounding_size=0.5,pad=0.2",
        facecolor=ring_colours[i],
        edgecolor="none",
    )
    for i in range(1, data_len)
]
fig.legend(
    handles,
    ["Relevance", "Uniqueness", "Importance", "Overall AUC"],
    loc="lower left",
    bbox_to_anchor=(0.20, 0.78, 0.60, 0.06),
    mode="expand",
    ncol=4,
    frameon=True,
    edgecolor="lightblue",
    fancybox=True,
    handlelength=2.5,
    handleheight=1.5,
    handletextpad=0.4,
    prop=prop_bold_large,
    borderpad=0.3,
)

plt.savefig(
    "local_importance.pdf",
    dpi=600, bbox_inches="tight",
)
plt.close()

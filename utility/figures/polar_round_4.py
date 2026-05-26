import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd
import numpy as np
import matplotlib.font_manager as font_manager


prop = font_manager.FontProperties(fname="./results/Times New Roman.ttf", size=38)
prop_bold = font_manager.FontProperties(
    fname="./results/Times New Roman - Bold.ttf", size=32
)
prop_bold_large = font_manager.FontProperties(
    fname="./results/Times New Roman - Bold.ttf", size=44
)
# Load data into pandas dataframe

lith_dict1 = {
    "LITH": [
        "Leave Blank",
        "Sandstone",
        "Sandstone/Shale",
        "Chalk",
        "Limestone",
    ],
    "COUNT": [0, 57.8, 67.0, 66.5, 74.5],
    "TASK": "Strct."
}

lith_dict2 = {
    "LITH": [
        "Leave Blank",
        "Sandstone",
        "Sandstone/Shale",
        "Chalk",
        "Limestone",
    ],
    "COUNT": [0, 47.0, 66.7, 64.7, 72.3],
    "TASK": "Src."
}

lith_dict3 = {
    "LITH": [
        "Leave Blank",
        "Sandstone",
        "Sandstone/Shale",
        "Chalk",
        "Limestone",
    ],
    "COUNT": [0, 32.4, 41.0, 42.1, 50.7],
    "TASK": "Prop."
}

lith_dict4 = {
    "LITH": [
        "",
        "w/o Modality Fusion (-26.3%)",
        "w/o Dynamic Query (-10.7%)",
        "w/o Entropy Pathcing (-11.5%)",
        "EDT-Former", 
    ],
    "COUNT": [0, 40.7, 40.8, 42.0, 48.5],
    "TASK": "App."
}

number_offset1 = [1.6, 0.5, 0.27, 0.15, 0.1]
number_offset2 = [1.6, 0.8, 0.28, 0.21, 0.1]
number_offset3 = [1.6, 0.75, 0.28, 0.29, 0.1]
number_offset4 = [1.6, 0.75, 0.28, 0.29, 0.1]
number_offset = number_offset1
ring_colours = [
        # "#2f4b7c",
        # "#665191",
        "#a05195",
        "#d45087",
        "#f95d6a",
        "#ff7c43",
        "#ffa600",
    ]
dicts = [lith_dict1, lith_dict2, lith_dict3, lith_dict4]
offsets = [number_offset1, number_offset2, number_offset3, number_offset4]
max_values = [90, 90, 60, 60]
fig, axes = plt.subplots(1, 4, figsize=(50, 18), subplot_kw=dict(polar=True, frameon=False))
plt.subplots_adjust(wspace=0.10) 
data_len = 5


def draw_figure(lith_dict, number_offset, max_value_full_ring, ax):
    name = lith_dict["TASK"]   
    df = pd.DataFrame.from_dict(lith_dict)
    max_value_full_ring = max_value_full_ring
    ring_labels = [f"   {x} ({v}) " for x, v in zip(list(df["LITH"]), list(df["COUNT"]))]
    data_len = len(df)

    # Begin creating the figure
    # fig = plt.figure(figsize=(10, 10), linewidth=10, edgecolor="white", facecolor="white")

    rect = [0.1, 0.1, 0.8, 0.8]

    # Add axis for radial backgrounds
    PCT_MAX = max_value_full_ring


    def pct2rad(p):  # p 可以是标量或 numpy 数组
        return (np.asarray(p) / PCT_MAX) * 2 * np.pi


    # ax = fig.add_axes(rect, polar=True, frameon=False)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    if max_value_full_ring == 90:
        ticks_pct = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80])
    else:
        ticks_pct = np.array([0, 10, 20, 30, 40, 50])
    ax.set_xticks(pct2rad(ticks_pct))
    ax.set_xticklabels([str(t) for t in ticks_pct], fontproperties=prop)
    ax.yaxis.grid(False)
    ax.set_yticklabels([]) 

    # Loop through each entry in the dataframe and plot a grey
    # ring to create the background for each one
    ring_height = 0.8
    r = ring_height / 2.0
    s = np.pi * (r**2) * 4300  # 自动面积
    angle_max = 2

    for i in range(data_len):
        if i == 0:
            ax.barh(
                i,
                max_value_full_ring * angle_max * np.pi / max_value_full_ring,
                color="none",
                height=ring_height,
            )
            continue

        ax.barh(
            i,
            max_value_full_ring * angle_max * np.pi / max_value_full_ring,
            color="grey",
            alpha=0.1,
            height=ring_height,
        )
        ax.scatter(0, i, s=s, color=ring_colours[i], zorder=3)

    # Hide all axis items
    # ax_polar_bg.axis("off")


    # Add axis for radial chart for each entry in the dataframe
    # ax = fig.add_axes(rect, polar=True, frameon=False)
    # ax.xaxis.grid(True)
    # ax_polar.set_rgrids([0, 1, 2, 3, 4],
    #                     # labels=ring_labels,
    #                     angle=0,
    #                     fontweight='bold',
    #                     color='black', verticalalignment='center', fontproperties=prop_bold)


    # Loop through each entry in the dataframe and create a coloured
    # ring for each entry
    for i in range(data_len):
        val = df["COUNT"][i] * angle_max * np.pi / max_value_full_ring
        if i == 0:
            ax.barh(i, val, color="none", height=ring_height)
            continue
        ax.barh(i, val, color=ring_colours[i], height=ring_height, label=df["LITH"][i])

        # 在末端加一个小圆
        ax.scatter(val, i, s=s, color=ring_colours[i], zorder=3)
        
        ax.text(
            val + number_offset[i],  # θ角度稍微往外偏移，避免和圆点重叠
            i + 0.5,  # 半径位置就是第 i 个环
            f"{df['COUNT'][i]}",
            ha="left",
            va="center",
            color="black",
            fontweight="bold",
            fontproperties=prop_bold,
            fontsize=40,
        )

    ax.text(
        0,
        -0.6,
        name,
        ha="center",
        va="center",
        color="black",
        fontweight="bold",
        fontproperties=prop_bold,
        fontsize=54,
        bbox=dict(
            boxstyle="round,pad=0.1,rounding_size=0.5",  # 圆角 + 内边距
            facecolor="lightgreen",  # 背景色
            edgecolor="lightgreen",  # 边框颜色
            linewidth=0.1,  # 边框粗细
            alpha=0.5,  # 透明度（可选）
        ),
    )

    # ax.tick_params(
    #     axis="both", left=False, bottom=False, labelbottom=False, labelleft=False
    # )


handles = [
    FancyBboxPatch(
        (0, 0), 1, 2,              # (x, y), 宽, 高
        boxstyle="round,rounding_size=0.5,pad=0.2",  # 圆角矩形
        facecolor=ring_colours[i],
        edgecolor="none"
    )
    for i in range(1, data_len)
]
fig.legend(
    handles,
    [
        "W/O Modality Fusion (-26.3%)",
        "W/O Dynamic Query (-10.7%)",
        "W/O Entropy Pathcing (-11.5%)",
        "EDT-Former", 
    ],     
    loc="upper center",         # 位置
    bbox_to_anchor=(0.5, 0.87), # 偏移
    ncol=4,                    # 每行显示的图例数量
    frameon=True,              # 是否显示边框
    edgecolor="lightblue",        # 边框颜色
    fancybox=True,
    handlelength=2.5,       # 颜色条长度 (默认1.5)
    handleheight=1.5,       # 颜色条高度
    handletextpad=0.4,      # 颜色条与文字的间距
    prop=prop_bold_large,
    borderpad=0.3           # 图例框内
)

for ax, lith_dict, offset, max_value in zip(axes, dicts, offsets, max_values):
    draw_figure(lith_dict, offset, max_value, ax)

# plt.savefig(f"./utils/figures/results/{str(name).lower()[:-1]}.png", dpi=600, bbox_inches="tight")
# plt.savefig(f"./utils/figures/results/{str(name).lower()[:-1]}.pdf", dpi=600, bbox_inches="tight")

plt.savefig(f"./utils/figures/results/main_ablation.pdf", dpi=600, bbox_inches="tight")
plt.close()

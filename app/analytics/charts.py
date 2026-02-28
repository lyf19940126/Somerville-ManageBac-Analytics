from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt


def generate_student_trend_chart(student_name: str, points: list[tuple[str, str, float | None]], output_path: str) -> str:
    """points: [(date_iso, course_name, overall_value)]"""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    valid_points = [p for p in points if p[2] is not None]
    if not valid_points:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No numeric OVERALL data available", ha="center", va="center")
        ax.set_axis_off()
        fig.tight_layout()
        fig.savefig(output_path)
        plt.close(fig)
        return output_path

    series: dict[str, list[tuple[str, float]]] = {}
    for date_iso, course_name, value in valid_points:
        series.setdefault(course_name, []).append((date_iso, float(value)))

    fig, ax = plt.subplots(figsize=(10, 5))
    for course_name, values in sorted(series.items()):
        values_sorted = sorted(values, key=lambda x: x[0])
        x = [v[0] for v in values_sorted]
        y = [v[1] for v in values_sorted]
        ax.plot(x, y, marker="o", label=course_name)

    ax.set_title(f"OVERALL Trend - {student_name}")
    ax.set_xlabel("Date")
    ax.set_ylabel("OVERALL")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.2)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
    return output_path

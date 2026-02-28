from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def generate_student_report(
    *,
    student_name: str,
    chart_path: str | None,
    behaviour: list[dict],
    attendance: list[dict],
    output_file: str,
) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    template = env.get_template("student_report.html")

    html = template.render(
        student_name=student_name,
        generated_at=datetime.utcnow().isoformat() + "Z",
        chart_path=chart_path,
        behaviour=behaviour,
        attendance=attendance,
    )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)

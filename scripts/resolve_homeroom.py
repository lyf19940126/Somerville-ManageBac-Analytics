from app.config import load_settings
from app.managebac.client import ManageBacClient
from app.managebac.service import ManageBacService


def main() -> None:
    settings = load_settings()
    client = ManageBacClient(settings.managebac_base_url, settings.managebac_token)
    service = ManageBacService(client)
    try:
        students = service.list_students_for_homeroom(
            advisor_id=settings.homeroom_advisor_id,
            target_graduating_year=settings.target_graduating_year,
        )
        sample = students[0] if students else {}
        print(
            "Resolved homeroom student scope: "
            f"advisor_id={settings.homeroom_advisor_id} "
            f"graduating_year={settings.target_graduating_year} "
            f"student_count={len(students)} "
            f"sample_id={sample.get('student_id')}"
        )
    finally:
        client.close()


if __name__ == "__main__":
    main()

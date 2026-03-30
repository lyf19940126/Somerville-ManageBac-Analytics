from app.config import load_settings
from app.managebac.client import ManageBacClient
from app.managebac.service import ManageBacService


def main() -> None:
    settings = load_settings()
    client = ManageBacClient(settings.managebac_base_url, settings.managebac_token)
    service = ManageBacService(client)
    try:
        students = service.select_target_students(
            advisor_id=settings.homeroom_advisor_id,
            target_graduating_year=settings.target_graduating_year,
            include_archived=False,
        )
        print(f"selected_students={len(students)}")
        if students:
            sample = students[0]
            print(
                "sample:",
                {
                    "id": sample.get("id") or sample.get("student_id"),
                    "name": sample.get("full_name")
                    or " ".join(
                        part for part in [sample.get("first_name"), sample.get("last_name")] if part
                    ).strip(),
                    "graduating_year": sample.get("graduating_year"),
                },
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()

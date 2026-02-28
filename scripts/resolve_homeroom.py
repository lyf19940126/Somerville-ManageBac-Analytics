from app.config import load_settings
from app.managebac.client import ManageBacClient
from app.managebac.service import ManageBacService


def main() -> None:
    settings = load_settings(require_term_id=False)
    client = ManageBacClient(settings.managebac_base_url, settings.managebac_token)
    service = ManageBacService(client)
    try:
        homeroom_id = service.resolve_homeroom_id(settings.homeroom_name, settings.homeroom_id)
        students = service.fetch_homeroom_students(homeroom_id)
        print(f"Resolved homeroom_id={homeroom_id} student_count={len(students)}")
    finally:
        client.close()


if __name__ == "__main__":
    main()

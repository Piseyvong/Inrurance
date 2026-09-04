from sqlalchemy import inspect

from app.database import engine

EXPECTED_TABLES = {
    "claims",
    "documents",
    "extracted_fields",
    "rule_results",
    "audit_log",
}


def main() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(EXPECTED_TABLES - existing_tables)

    if missing_tables:
        print("Missing tables:")
        for table in missing_tables:
            print(f"- {table}")
        raise SystemExit(1)

    print("All Phase 1 tables exist:")
    for table in sorted(EXPECTED_TABLES):
        print(f"- {table}")


if __name__ == "__main__":
    main()

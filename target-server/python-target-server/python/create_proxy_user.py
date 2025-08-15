import argparse
from database import Database
from simple_logger import log

def main():
    parser = argparse.ArgumentParser(description="Add a new proxy user to the database.")
    parser.add_argument("--id", required=True, help="The Admin 'id' for the proxy.")
    parser.add_argument("--secret", required=True, help="The Admin 'secret' for the proxy.")
    args = parser.parse_args()

    if not args.id or not args.secret:
        log("ERROR", "Admin ID and secret cannot be empty.")
        return

    db = Database()
    if db.add_user(args.id, args.secret):
        log("SUCCESS", f"Added admin user", extras=f"Admin ID: '{args.id}'")
    else:
        log("ERROR", f"Failed to add user", extras=f"Admin ID: '{args.id}'")
    db.close()

if __name__ == "__main__":
    main()
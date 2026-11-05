import argparse
import csv
import datetime
import json
import sys
import tempfile
import time
from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from colorama import Fore

LIMIT = 60
STANDARD_PROPERTIES = (
    "Username",
    "UserCreateDate",
    "UserLastModifiedDate",
    "Enabled",
    "UserStatus",
)


def validate_and_prepare_filename(filename):
    """Prepare the path without opening or deleting an existing export."""
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"CognitoUsers_{timestamp}.csv"
    file_path = Path(filename)
    if file_path.suffix.lower() != ".csv":
        file_path = file_path.with_name(file_path.name + ".csv")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    return file_path


def get_list_cognito_users(cognito_idp_client, user_pool_id, token, limit):
    """Fetch one page with the supplied client and optional resume token."""
    parameters = {"UserPoolId": user_pool_id, "Limit": limit}
    if token:
        parameters["PaginationToken"] = token
    return cognito_idp_client.list_users(**parameters)


def main():
    """Export the requested records and return a process exit status."""
    parser = argparse.ArgumentParser(
        description="Export Cognito User Pool records to CSV",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "-attr",
        "--export-attributes",
        nargs="+",
        help="List of attributes to save in CSV",
    )
    parser.add_argument(
        "--all-attributes",
        action="store_true",
        help="Export all attributes (overrides --export-attributes)",
    )
    parser.add_argument("--user-pool-id", required=True, help="The user pool ID")
    parser.add_argument("--region", default="us-east-1", help="The user pool region")
    parser.add_argument("--profile", default="", help="The AWS profile")
    parser.add_argument(
        "--starting-token", default="", help="Starting pagination token"
    )
    parser.add_argument("-f", "--file-name", help="CSV file name or path")
    parser.add_argument(
        "--num-records",
        type=int,
        default=0,
        help="Maximum records to export; 0 exports all records",
    )
    args = parser.parse_args()
    if not args.all_attributes and not args.export_attributes:
        parser.error("Either --all-attributes or --export-attributes must be specified")
    if args.num_records < 0:
        parser.error("--num-records must be zero or greater")

    try:
        output = validate_and_prepare_filename(args.file_name)
        print(Fore.CYAN + f"INFO: Output file will be: {output}")
        if args.profile:
            client = boto3.Session(profile_name=args.profile).client(
                "cognito-idp", region_name=args.region
            )
        else:
            client = boto3.client("cognito-idp", region_name=args.region)

        attributes = set(STANDARD_PROPERTIES)
        exported_records = 0
        token = args.starting_token
        # Spool records to disk: discover every column without holding the pool
        # in memory or making a second, potentially inconsistent AWS scan.
        with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as records:
            while True:
                limit = (
                    min(LIMIT, args.num_records - exported_records)
                    if args.num_records
                    else LIMIT
                )
                page = get_list_cognito_users(client, args.user_pool_id, token, limit)
                for user in page["Users"]:
                    row = {
                        item["Name"]: item["Value"]
                        for item in user.get("Attributes", [])
                    }
                    row.update(
                        {
                            key: value
                            for key, value in user.items()
                            if key != "Attributes"
                        }
                    )
                    if args.all_attributes:
                        attributes.update(row)
                    records.write(json.dumps(row, default=str) + "\n")
                    exported_records += 1
                print(Fore.YELLOW + f"INFO: Fetched records: {exported_records}")
                if args.num_records and exported_records >= args.num_records:
                    print(Fore.GREEN + "INFO: Maximum number of records reached")
                    break
                token = page.get("PaginationToken")
                if not token:
                    print(Fore.GREEN + "INFO: End of Cognito User Pool reached")
                    break
                time.sleep(0.15)

            columns = (
                sorted(attributes) if args.all_attributes else args.export_attributes
            )
            records.seek(0)
            # Do not touch the destination until every requested AWS page succeeds.
            with output.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(
                    csv_file, fieldnames=columns, extrasaction="ignore"
                )
                writer.writeheader()
                for line in records:
                    row = json.loads(line)
                    writer.writerow({key: str(value) for key, value in row.items()})
        print(
            Fore.GREEN + f"INFO: Export completed successfully! File saved as: {output}"
        )
        print(Fore.CYAN + f"INFO: Total records exported: {exported_records}")
        return 0
    except ClientError as error:
        details = error.response.get("Error", {})
        print(
            Fore.RED
            + f"ERROR: {details.get('Code', 'Unknown')}: {details.get('Message', str(error))}",
            file=sys.stderr,
        )
    except (BotoCoreError, OSError, ValueError) as error:
        print(Fore.RED + f"ERROR: Export failed: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())

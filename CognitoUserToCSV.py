import boto3
import json
import datetime
import time
import sys
import argparse
import os
from pathlib import Path
from colorama import Fore

REGION = ''
USER_POOL_ID = ''
LIMIT = 60
MAX_NUMBER_RECORDS = 0
REQUIRED_ATTRIBUTE = None
CSV_FILE_NAME = 'CognitoUsers.csv'
PROFILE = ''
STARTING_TOKEN = ''
ALL_ATTRIBUTES = False

""" Parse All Provided Arguments """
parser = argparse.ArgumentParser(description='Cognito User Pool export records to CSV file', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('-attr', '--export-attributes', nargs='+', type=str, help="List of Attributes to be saved in CSV")
parser.add_argument('--all-attributes', action='store_true', help="Export all user attributes (overrides --export-attributes)")
parser.add_argument('--user-pool-id', type=str, help="The user pool ID", required=True)
parser.add_argument('--region', type=str, default='us-east-1', help="The user pool region")
parser.add_argument('--profile', type=str, default='', help="The aws profile")
parser.add_argument('--starting-token', type=str, default='', help="Starting pagination token")
parser.add_argument('-f', '--file-name', type=str, help="CSV file name or path (automatically adds .csv extension if not provided)")
parser.add_argument('--num-records', type=int, help="Max Number of Cognito Records to be exported")
args = parser.parse_args()

# Validate arguments
if not args.all_attributes and not args.export_attributes:
    parser.error("Either --all-attributes or --export-attributes must be specified")

if args.all_attributes:
    ALL_ATTRIBUTES = True
    print(Fore.CYAN + "INFO: All attributes mode enabled - will discover and export all user attributes")
elif args.export_attributes:
    REQUIRED_ATTRIBUTE = list(args.export_attributes)

def validate_and_prepare_filename(filename):
    """Validate and prepare the output filename with proper path handling"""
    if not filename:
        # Generate default filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"CognitoUsers_{timestamp}.csv"

    # Convert to Path object for better handling
    file_path = Path(filename)

    # Add .csv extension if not present
    if not file_path.suffix.lower() == '.csv':
        file_path = file_path.with_suffix('.csv')

    # Create directory if it doesn't exist
    if file_path.parent != Path('.'):
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            print(Fore.CYAN + f"INFO: Created directory: {file_path.parent}")
        except Exception as e:
            print(Fore.RED + f"ERROR: Cannot create directory {file_path.parent}: {str(e)}")
            exit(1)

    # Validate filename
    try:
        # Test if we can create/write to the file
        test_file = open(file_path, 'w')
        test_file.close()
        os.remove(file_path)  # Clean up test file
    except Exception as e:
        print(Fore.RED + f"ERROR: Cannot write to file {file_path}: {str(e)}")
        exit(1)

    return str(file_path)

if args.user_pool_id:
    USER_POOL_ID = args.user_pool_id
if args.region:
    REGION = args.region
if args.file_name:
    CSV_FILE_NAME = validate_and_prepare_filename(args.file_name)
else:
    CSV_FILE_NAME = validate_and_prepare_filename(None)
if args.num_records:
    MAX_NUMBER_RECORDS = args.num_records
if args.profile:
    PROFILE = args.profile
if args.starting_token:
    STARTING_TOKEN = args.starting_token

print(Fore.CYAN + f"INFO: Output file will be: {CSV_FILE_NAME}")

def datetimeconverter(o):
    if isinstance(o, datetime.datetime):
        return str(o)

def get_list_cognito_users(cognito_idp_cliend, next_pagination_token ='', Limit = LIMIT):
    return client.list_users(
        UserPoolId = USER_POOL_ID,
        Limit = Limit,
        PaginationToken = next_pagination_token
    ) if next_pagination_token else client.list_users(
        UserPoolId = USER_POOL_ID,
        Limit = Limit
    )

def discover_all_attributes(user_records):
    """Discover all unique attributes from the user records"""
    all_attrs = set()

    # Standard user properties that are always available
    standard_props = ['Username', 'UserCreateDate', 'UserLastModifiedDate', 'Enabled', 'UserStatus']

    for user in user_records['Users']:
        # Add standard user properties
        for prop in standard_props:
            if prop in user:
                all_attrs.add(prop)

        # Add custom attributes
        if 'Attributes' in user:
            for attr in user['Attributes']:
                all_attrs.add(attr['Name'])

    return sorted(list(all_attrs))

if PROFILE:
    session = boto3.Session(profile_name=PROFILE)
    client = session.client('cognito-idp', REGION)
else:
    client = boto3.client('cognito-idp', REGION)

# If all attributes mode, we need to discover attributes first
if ALL_ATTRIBUTES:
    print(Fore.YELLOW + "Discovering all available attributes...")
    try:
        # Get a small sample to discover attributes
        sample_records = get_list_cognito_users(
            cognito_idp_cliend = client,
            Limit = min(LIMIT, 10)  # Use smaller sample for discovery
        )
        REQUIRED_ATTRIBUTE = discover_all_attributes(sample_records)
        print(Fore.GREEN + f"Found {len(REQUIRED_ATTRIBUTE)} unique attributes: {', '.join(REQUIRED_ATTRIBUTE)}")
    except client.exceptions.ClientError as err:
        error_message = err.response["Error"]["Message"]
        print(Fore.RED + "Please Check your Cognito User Pool configs")
        print("Error Reason: " + error_message)
        exit()
    except Exception as err:
        print(Fore.RED + "Error during attribute discovery: " + str(err))
        exit()

csv_new_line = {REQUIRED_ATTRIBUTE[i]: '' for i in range(len(REQUIRED_ATTRIBUTE))}
try:
    csv_file = open(CSV_FILE_NAME, 'w' ,encoding="utf-8")
    csv_file.write(",".join(csv_new_line.keys()) + '\n')
    print(Fore.GREEN + f"INFO: Successfully created CSV file: {CSV_FILE_NAME}")
except Exception as err:
    error_message = repr(err)
    print(Fore.RED + f"\nERROR: Cannot create file: {CSV_FILE_NAME}")
    print(f"\tError Reason: {error_message}")
    exit()

pagination_counter = 0
exported_records_counter = 0
pagination_token = STARTING_TOKEN

while pagination_token is not None:
    csv_lines = []
    try:
        user_records = get_list_cognito_users(
            cognito_idp_cliend = client,
            next_pagination_token = pagination_token,
            Limit = LIMIT if LIMIT < MAX_NUMBER_RECORDS else MAX_NUMBER_RECORDS
        )
    except client.exceptions.ClientError as err:
        error_message = err.response["Error"]["Message"]
        print(Fore.RED + "Please Check your Cognito User Pool configs")
        print("Error Reason: " + error_message)
        csv_file.close()
        exit()
    except:
        print(Fore.RED + "Something else went wrong")
        csv_file.close()
        exit()

    """ Check if there next paginatioon is exist """
    if set(["PaginationToken","NextToken"]).intersection(set(user_records)):
        pagination_token = user_records['PaginationToken'] if "PaginationToken" in user_records else user_records['NextToken']
    else:
        pagination_token = None

    for user in user_records['Users']:
        """ Fetch Required Attributes Provided """
        csv_line = csv_new_line.copy()
        for requ_attr in REQUIRED_ATTRIBUTE:
            csv_line[requ_attr] = ''
            if requ_attr in user.keys():
                csv_line[requ_attr] = str(user[requ_attr])
                continue
            if 'Attributes' in user:
                for usr_attr in user['Attributes']:
                    if usr_attr['Name'] == requ_attr:
                        csv_line[requ_attr] = str(usr_attr['Value'])

        csv_lines.append(",".join(csv_line.values()) + '\n')

    csv_file.writelines(csv_lines)

    """ Display Proccess Infor """
    pagination_counter += 1
    exported_records_counter += len(csv_lines)
    print(Fore.YELLOW + "Page: #{} \n Total Exported Records: #{} \n".format(str(pagination_counter), str(exported_records_counter)))

    if MAX_NUMBER_RECORDS and exported_records_counter >= MAX_NUMBER_RECORDS:
        print(Fore.GREEN + "INFO: Max Number of Exported Reached")
        break

    if pagination_token is None:
        print(Fore.GREEN + "INFO: End of Cognito User Pool reached")

    """ Cool Down before next batch of Cognito Users """
    time.sleep(0.15)

""" Close File """
csv_file.close()
print(Fore.GREEN + f"✅ Export completed successfully! File saved as: {CSV_FILE_NAME}")
print(Fore.CYAN + f"📊 Total records exported: {exported_records_counter}")
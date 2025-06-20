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

def list_available_user_pools(client, region):
    """List available user pools in the region for debugging"""
    try:
        print(Fore.YELLOW + f"DEBUG: Listing user pools in region '{region}'...")
        response = client.list_user_pools(MaxResults=60)

        if response.get('UserPools'):
            print(Fore.CYAN + f"DEBUG: Found {len(response['UserPools'])} user pools:")
            for pool in response['UserPools']:
                pool_id = pool.get('Id', 'Unknown')
                pool_name = pool.get('Name', 'Unknown')
                creation_date = pool.get('CreationDate', 'Unknown')
                print(Fore.CYAN + f"  - ID: {pool_id}, Name: {pool_name}, Created: {creation_date}")
        else:
            print(Fore.YELLOW + f"DEBUG: No user pools found in region '{region}'")

    except Exception as e:
        print(Fore.YELLOW + f"DEBUG: Could not list user pools: {str(e)}")

# Enhanced AWS session setup with debugging
print(Fore.CYAN + f"INFO: Setting up AWS connection...")
print(Fore.CYAN + f"INFO: User Pool ID: {USER_POOL_ID}")
print(Fore.CYAN + f"INFO: Region: {REGION}")
print(Fore.CYAN + f"INFO: Profile: {PROFILE if PROFILE else 'default'}")

try:
    if PROFILE:
        print(Fore.YELLOW + f"DEBUG: Creating session with profile '{PROFILE}'...")
        session = boto3.Session(profile_name=PROFILE)

        # Check credentials
        credentials = session.get_credentials()
        if credentials:
            print(Fore.GREEN + f"DEBUG: Successfully loaded credentials for profile '{PROFILE}'")
            print(Fore.CYAN + f"DEBUG: Access Key ID: {credentials.access_key[:8]}..." if credentials.access_key else "DEBUG: No access key found")
        else:
            print(Fore.RED + f"ERROR: No credentials found for profile '{PROFILE}'")
            print(Fore.YELLOW + "HINT: Check if the profile exists in ~/.aws/credentials or ~/.aws/config")
            exit(1)

        # Get actual region being used
        actual_region = session.region_name or REGION
        print(Fore.CYAN + f"DEBUG: Session region: {actual_region}")

        client = session.client('cognito-idp', region_name=REGION)
    else:
        print(Fore.YELLOW + f"DEBUG: Using default AWS credentials...")
        client = boto3.client('cognito-idp', region_name=REGION)

        # Try to get credentials info
        try:
            sts_client = boto3.client('sts', region_name=REGION)
            identity = sts_client.get_caller_identity()
            print(Fore.GREEN + f"DEBUG: Using AWS account: {identity.get('Account', 'Unknown')}")
            print(Fore.CYAN + f"DEBUG: User ARN: {identity.get('Arn', 'Unknown')}")
        except Exception as e:
            print(Fore.RED + f"DEBUG: Could not get caller identity: {str(e)}")

    print(Fore.GREEN + f"INFO: AWS client created successfully")
    print(Fore.CYAN + f"DEBUG: Client region: {client.meta.region_name}")

except Exception as e:
    print(Fore.RED + f"ERROR: Failed to create AWS client: {str(e)}")
    exit(1)

# Validate user pool exists first
print(Fore.YELLOW + f"DEBUG: Validating user pool access...")
try:
    # Try to describe the user pool to validate it exists and we have access
    user_pool_info = client.describe_user_pool(UserPoolId=USER_POOL_ID)
    print(Fore.GREEN + f"DEBUG: User pool found successfully!")
    print(Fore.CYAN + f"DEBUG: User pool name: {user_pool_info['UserPool'].get('Name', 'Unknown')}")
    print(Fore.CYAN + f"DEBUG: User pool domain: {user_pool_info['UserPool'].get('Domain', 'None')}")
    print(Fore.CYAN + f"DEBUG: User pool creation date: {user_pool_info['UserPool'].get('CreationDate', 'Unknown')}")
    print(Fore.CYAN + f"DEBUG: Estimated number of users: {user_pool_info['UserPool'].get('EstimatedNumberOfUsers', 'Unknown')}")
except client.exceptions.ClientError as err:
    error_code = err.response["Error"]["Code"]
    error_message = err.response["Error"]["Message"]
    print(Fore.RED + f"ERROR: Failed to access user pool")
    print(Fore.RED + f"Error Code: {error_code}")
    print(Fore.RED + f"Error Message: {error_message}")

    # Provide specific debugging hints
    if error_code == "ResourceNotFoundException":
        print(Fore.YELLOW + "DEBUGGING HINTS:")
        print(Fore.YELLOW + f"  1. Verify the user pool ID '{USER_POOL_ID}' is correct")
        print(Fore.YELLOW + f"  2. Ensure the user pool exists in region '{REGION}'")
        print(Fore.YELLOW + f"  3. Check if you have the correct AWS account/profile")

        # List available user pools for comparison
        list_available_user_pools(client, REGION)

    elif error_code == "AccessDeniedException":
        print(Fore.YELLOW + "DEBUGGING HINTS:")
        print(Fore.YELLOW + f"  1. Check if your AWS credentials have cognito-idp permissions")
        print(Fore.YELLOW + f"  2. Required permissions: cognito-idp:DescribeUserPool, cognito-idp:ListUsers")
        print(Fore.YELLOW + f"  3. Verify the IAM policy attached to your user/role")

    exit(1)
except Exception as err:
    print(Fore.RED + f"ERROR: Unexpected error while validating user pool: {str(err)}")
    exit(1)

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
        error_code = err.response["Error"]["Code"]
        error_message = err.response["Error"]["Message"]
        print(Fore.RED + "ERROR: Failed to list users for attribute discovery")
        print(Fore.RED + f"Error Code: {error_code}")
        print(Fore.RED + f"Error Message: {error_message}")
        exit(1)
    except Exception as err:
        print(Fore.RED + "Error during attribute discovery: " + str(err))
        exit(1)

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
        error_code = err.response["Error"]["Code"]
        error_message = err.response["Error"]["Message"]
        print(Fore.RED + f"ERROR: Failed to list users during export")
        print(Fore.RED + f"Error Code: {error_code}")
        print(Fore.RED + f"Error Message: {error_message}")
        print(Fore.RED + f"Pagination Token: {pagination_token}")
        csv_file.close()
        exit(1)
    except Exception as err:
        print(Fore.RED + f"ERROR: Unexpected error during export: {str(err)}")
        csv_file.close()
        exit(1)

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
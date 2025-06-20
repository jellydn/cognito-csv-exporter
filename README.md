# Export Amazon Cognito User Pool records into CSV

This project allows to export user records to CSV file from [Amazon Cognito User Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html)

## Installation

### Option 1: Using UV (Recommended)

UV is a fast Python package installer and resolver. It's much faster than pip and provides better dependency management.

1. Install UV:

   ```bash
   # On macOS (using Homebrew)
   brew install uv

   # Or using curl
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Install dependencies and create virtual environment:
   ```bash
   uv sync
   ```

### Option 2: Using pip (Traditional)

In order to use this script you should have Python 2 or Python 3 installed on your platform

- run `pip install -r requirements.txt` (Python 2) or `pip3 install -r requirements.txt` (Python 3)

## Run export

### Using UV

```bash
# Export all user attributes automatically
uv run python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes

# Export specific attributes
uv run python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' -attr Username email_verified given_name family_name UserCreateDate

# Export with custom file name
uv run python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes -f my_users.csv

# Export to specific directory
uv run python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes -f exports/users_backup
```

### Using pip/traditional method

To start export proccess you shout run next command (**Note**: use `python3` if you have Python 3 instaled)

- Export all attributes: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes`
- Export specific attributes: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' -attr Username email_verified given_name family_name UserCreateDate`
- Export with custom file name: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes -f my_export.csv`

### Output

- Wait until you see output `INFO: End of Cognito User Pool reached`
- Find file `CognitoUsers.csv` that contains all exported users. [Example](https://github.com/hawkerfun/cognito-csv-exporter/blob/master/CognitoUsers.csv)

### Script Arguments

- `--user-pool-id` [__Required__] - The user pool ID for the user pool on which the export should be performed
- `--all-attributes` [_Optional_] - Export all user attributes automatically (discovers all available attributes)
- `-attr` or `--export-attributes` [_Optional_] - List of specific attributes to be saved in CSV file
- `--region` [_Optional_] - The user pool region the user pool on which the export should be performed _Default_: `us-east-1`
- `-f` or `--file-name` [_Optional_] - CSV file name or path (automatically adds .csv extension if not provided, creates directories if needed). _Default_: `CognitoUsers_TIMESTAMP.csv`
- `--num-records` [_Optional_] - Max Number of Cognito Records tha will be exported. _Default_: **0** - All
- `--profile` [_Optional_] - The AWS profile to use, if not provided the default one will be used
- `--starting-token` [_Optional_] - The starting pagination token to continue from if provided

**Note**: Either `--all-attributes` or `--export-attributes` must be specified. The `--all-attributes` flag will automatically discover and export all available user properties and custom attributes.

###### Note:

If you need to Back up your intire cognito instance pool, take a look for this tool: https://www.npmjs.com/package/cognito-backup-restore

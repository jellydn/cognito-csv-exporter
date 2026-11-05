# Export Amazon Cognito User Pool records into CSV

Export user records to a CSV file from [Amazon Cognito User Pool](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-identity-pools.html).

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

Use Python 3.7 or later.

- Run `python3 -m pip install -r requirements.txt`.

Configure AWS credentials with permission to call `cognito-idp:ListUsers` for the target pool.

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

To start the export process, run one of these commands with Python 3.

- Export all attributes: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes`
- Export specific attributes: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' -attr Username email_verified given_name family_name UserCreateDate`
- Export with custom file name: `$ python CognitoUserToCSV.py --user-pool-id 'us-east-1_XXXXXXXXX' --all-attributes -f my_export.csv`

### Output

- Wait for `INFO: Export completed successfully!`.
- The output path is printed at completion. The default is `CognitoUsers_TIMESTAMP.csv`.
- All-attributes mode discovers columns across every exported page, including properties and custom attributes. With `--num-records` or `--starting-token`, it discovers columns only from the selected records.
- Records are stored in a temporary file before CSV output. Ensure that the temporary directory has enough free space. An AWS failure leaves an existing output file unchanged. A successful export overwrites it.

### Script Arguments

- `--user-pool-id` [__Required__] - The user pool ID for the user pool on which the export should be performed
- `--all-attributes` [_Optional_] - Export all user attributes automatically (discovers all available attributes)
- `-attr` or `--export-attributes` [_Optional_] - List of specific attributes to be saved in CSV file
- `--region` [_Optional_] - The user pool region the user pool on which the export should be performed _Default_: `us-east-1`
- `-f` or `--file-name` [_Optional_] - CSV file name or path (automatically adds .csv extension if not provided, creates directories if needed). _Default_: `CognitoUsers_TIMESTAMP.csv`
- `--num-records` [_Optional_] - Maximum number of records to export. Must be zero or greater. _Default_: **0** - All
- `--profile` [_Optional_] - The AWS profile to use, if not provided the default one will be used
- `--starting-token` [_Optional_] - The starting pagination token to continue from if provided

**Note**: Either `--all-attributes` or `--export-attributes` must be specified. If both are supplied, `--all-attributes` takes precedence.

## Development checks

```bash
uv run python -m unittest -v
uvx ruff check CognitoUserToCSV.py test_export.py
uvx ruff format --check CognitoUserToCSV.py test_export.py
```

### Amp orbs

`.agents/setup` installs the Python dependencies and caches Ruff and cspell for fresh orbs. Amp can reuse these dependencies in project snapshots. The script uses Python, uv, and Bun from the orb base image.

`.agents/resume` checks the restored Python dependencies without installing packages or contacting AWS. Tests use stubbed AWS responses and need no credentials. To export real users, configure AWS credentials separately.

###### Note:

To back up your entire Cognito user pool, see [cognito-backup-restore](https://www.npmjs.com/package/cognito-backup-restore).

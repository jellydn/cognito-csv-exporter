import contextlib
import csv
import datetime
import io
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
from botocore.exceptions import ClientError
from botocore.stub import Stubber

SCRIPT = Path(__file__).with_name("CognitoUserToCSV.py")


class ExportTests(unittest.TestCase):
    def run_export(self, output, pages, *options, fail=False):
        client = MagicMock()
        client.exceptions.ClientError = ClientError

        def list_users(**kwargs):
            if fail:
                raise ClientError(
                    {"Error": {"Code": "AccessDeniedException", "Message": "Denied"}},
                    "ListUsers",
                )
            index = int(kwargs.get("PaginationToken", "0"))
            users = pages[index][: kwargs["Limit"]]
            response = {"Users": users}
            if index + 1 < len(pages):
                response["PaginationToken"] = str(index + 1)
            return response

        client.list_users.side_effect = list_users
        args = [
            str(SCRIPT),
            "--user-pool-id",
            "us-east-1_test",
            "-f",
            str(output),
            *options,
        ]
        with patch.object(sys, "argv", args), patch(
            "boto3.client", return_value=client
        ), patch("boto3.Session") as session, patch(
            "time.sleep"
        ), contextlib.redirect_stdout(io.StringIO()):
            session.return_value.client.return_value = client
            try:
                runpy.run_path(str(SCRIPT), run_name="__main__")
            except SystemExit as error:
                if error.code:
                    raise

    def test_all_attributes_across_pages_and_csv_escaping(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "users.csv"
            self.run_export(
                output,
                [
                    [{"Username": "first", "Enabled": False}],
                    [
                        {
                            "Username": "second",
                            "Attributes": [
                                {
                                    "Name": "custom:note",
                                    "Value": 'comma, quote" and\nnewline',
                                }
                            ],
                        }
                    ],
                ],
                "--all-attributes",
            )
            with output.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["Enabled"], "False")
            self.assertEqual(rows[0]["custom:note"], "")
            self.assertEqual(rows[1]["custom:note"], 'comma, quote" and\nnewline')

    def test_aws_failure_preserves_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            output.write_text("keep this export\n")
            with self.assertRaises(SystemExit) as error:
                self.run_export(output, [], "-attr", "Username", fail=True)
            self.assertNotEqual(error.exception.code, 0)
            self.assertEqual(output.read_text(), "keep this export\n")

    def test_record_limit_uses_remaining_count_and_starting_token(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            pages = [
                [{"Username": "skip"}],
                [{"Username": str(i)} for i in range(60)],
                [{"Username": "last"}, {"Username": "too many"}],
            ]
            self.run_export(
                output,
                pages,
                "-attr",
                "Username",
                "--num-records",
                "61",
                "--starting-token",
                "1",
            )
            with output.open(newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), 62)
            self.assertEqual(rows[-1], ["last"])
            self.assertEqual(rows[1], ["0"])

    def test_empty_pool_has_standard_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            self.run_export(output, [[]], "--all-attributes")
            with output.open(newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertIn("Username", rows[0])
            self.assertEqual(len(rows), 1)

    def test_selected_columns_preserve_order_and_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            self.run_export(
                output,
                [
                    [
                        {
                            "Username": "Zoë",
                            "Enabled": False,
                            "Attributes": [
                                {"Name": "email", "Value": "a,b@example.com"}
                            ],
                        }
                    ]
                ],
                "-attr",
                "email",
                "Username",
                "Enabled",
                "missing",
                "--profile",
                "test-profile",
                "--num-records",
                "0",
            )
            with output.open(newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(
                rows,
                [
                    ["email", "Username", "Enabled", "missing"],
                    ["a,b@example.com", "Zoë", "False", ""],
                ],
            )

    def test_invalid_arguments_do_not_touch_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            output.write_text("keep")
            for options in [(), ("-attr", "Username", "--num-records", "-1")]:
                with self.subTest(options=options), self.assertRaises(
                    SystemExit
                ) as error:
                    self.run_export(output, [], *options)
                self.assertEqual(error.exception.code, 2)
                self.assertEqual(output.read_text(), "keep")

    def test_sdk_export_with_empty_page_and_late_attribute(self):
        client = boto3.client(
            "cognito-idp",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        with Stubber(client) as stub, tempfile.TemporaryDirectory() as directory:
            stub.add_response(
                "list_users",
                {"Users": [], "PaginationToken": "next"},
                {"UserPoolId": "us-east-1_test", "Limit": 60},
            )
            stub.add_response(
                "list_users",
                {
                    "Users": [
                        {
                            "Username": "last",
                            "UserCreateDate": datetime.datetime(2026, 1, 2),
                            "Attributes": [{"Name": "custom:late", "Value": "found"}],
                        }
                    ]
                },
                {
                    "UserPoolId": "us-east-1_test",
                    "Limit": 60,
                    "PaginationToken": "next",
                },
            )
            output = Path(directory) / "users.csv"
            args = [
                str(SCRIPT),
                "--user-pool-id",
                "us-east-1_test",
                "--all-attributes",
                "-attr",
                "ignored",
                "-f",
                str(output),
            ]
            with patch.object(sys, "argv", args), patch(
                "boto3.client", return_value=client
            ), patch("time.sleep"), contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    runpy.run_path(str(SCRIPT), run_name="__main__")
                self.assertEqual(error.exception.code, 0)
            with output.open(newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["custom:late"], "found")
            self.assertEqual(rows[0]["UserCreateDate"], "2026-01-02 00:00:00")
            self.assertNotIn("ignored", rows[0])

    def test_dotted_filename_keeps_existing_name(self):
        with tempfile.TemporaryDirectory() as directory:
            unrelated = Path(directory) / "users.csv"
            unrelated.write_text("keep")
            self.run_export(
                Path(directory) / "users.v2",
                [[{"Username": "one"}]],
                "-attr",
                "Username",
            )
            self.assertEqual(unrelated.read_text(), "keep")
            with (Path(directory) / "users.v2.csv").open(newline="") as stream:
                self.assertEqual(list(csv.reader(stream)), [["Username"], ["one"]])


if __name__ == "__main__":
    unittest.main()

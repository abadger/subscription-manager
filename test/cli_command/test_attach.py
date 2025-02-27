import contextlib
import os
import sys
import tempfile

from ..test_managercli import TestCliProxyCommand
from subscription_manager import managercli

from unittest.mock import patch


# Test Attach and Subscribe are the same
class TestAttachCommand(TestCliProxyCommand):
    command_class = managercli.AttachCommand
    tempdir = None
    tempfiles = []

    @classmethod
    def setUpClass(cls):
        # Create temp file(s) for processing pool IDs
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.tempfiles = [
            tempfile.mkstemp(dir=cls.tempdir.name),
            tempfile.mkstemp(dir=cls.tempdir.name),
            tempfile.mkstemp(dir=cls.tempdir.name),
        ]

        os.write(cls.tempfiles[0][0], b"pool1 pool2   pool3 \npool4\npool5\r\npool6\t\tpool7\n  pool8\n\n\n")
        os.close(cls.tempfiles[0][0])
        os.write(cls.tempfiles[1][0], b"pool1 pool2   pool3 \npool4\npool5\r\npool6\t\tpool7\n  pool8\n\n\n")
        os.close(cls.tempfiles[1][0])
        # The third temp file intentionally left empty for testing empty sets of data
        os.close(cls.tempfiles[2][0])

    @classmethod
    def tearDownClass(cls):
        cls.tempdir = None
        cls.tempfiles = []

    def setUp(self):
        super(TestAttachCommand, self).setUp()
        argv_patcher = patch.object(sys, "argv", ["subscription-manager", "attach"])
        argv_patcher.start()
        self.addCleanup(argv_patcher.stop)

    def _test_quantity_exception(self, arg):
        try:
            self.cc.main(["--pool", "test-pool-id", "--quantity", arg])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_USAGE)
        else:
            self.fail("No Exception Raised")

    def _test_auto_and_quantity_exception(self):
        try:
            self.cc.main(["--auto", "--quantity", "6"])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_USAGE)
        else:
            self.fail("No Exception Raised")

    def _test_auto_default_and_quantity_exception(self):
        try:
            self.cc.main(["--quantity", "3"])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_USAGE)
        else:
            self.fail("No Exception Raised")

    def test_zero_quantity(self):
        self._test_quantity_exception("0")

    def test_negative_quantity(self):
        self._test_quantity_exception("-1")

    def test_text_quantity(self):
        try:
            self.cc.main(["--quantity", "JarJarBinks"])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, 2)
        else:
            self.fail("No Exception Raised")

    def test_positive_quantity(self):
        self.cc.main(["--pool", "test-pool-id", "--quantity", "1"])
        self.cc._validate_options()

    def test_positive_quantity_with_plus(self):
        self.cc.main(["--pool", "test-pool-id", "--quantity", "+1"])
        self.cc._validate_options()

    def test_positive_quantity_as_float(self):
        try:
            self.cc.main(["--quantity", "2.0"])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, 2)
        else:
            self.fail("No Exception Raised")

    def _test_pool_file_processing(self, f, expected):
        self.cc.main(["--file", f])
        self.cc._validate_options()

        self.assertEqual(expected, self.cc.options.pool)

    def test_pool_option_or_auto_option(self):
        self.cc.main(["--auto", "--pool", "1234"])
        self.assertRaises(SystemExit, self.cc._validate_options)

    def test_servicelevel_option_but_no_auto_option(self):
        with self.mock_stdin(open(self.tempfiles[1][1])):
            self.cc.main(["--servicelevel", "Super", "--file", "-"])
            self.assertRaises(SystemExit, self.cc._validate_options)

    def test_servicelevel_option_with_pool_option(self):
        self.cc.main(["--servicelevel", "Super", "--pool", "1232342342313"])
        # need a assertRaises that checks a SystemsExit code and message
        self.assertRaises(SystemExit, self.cc._validate_options)

    def test_just_pools_option(self):
        self.cc.main(["--pool", "1234"])
        self.cc._validate_options()

    def test_just_auto_option(self):
        self.cc.main(["--auto"])
        self.cc._validate_options()

    def test_no_options_defaults_to_auto(self):
        self.cc.main([])
        self.cc._validate_options()

    @contextlib.contextmanager
    def mock_stdin(self, fileobj):
        org_stdin = sys.stdin
        sys.stdin = fileobj

        try:
            yield
        finally:
            sys.stdin = org_stdin

    def test_pool_stdin_processing(self):
        with self.mock_stdin(open(self.tempfiles[1][1])):
            self._test_pool_file_processing(
                "-", ["pool1", "pool2", "pool3", "pool4", "pool5", "pool6", "pool7", "pool8"]
            )

    def test_pool_stdin_empty(self):
        try:
            with self.mock_stdin(open(self.tempfiles[2][1])):
                self.cc.main(["--file", "-"])
                self.cc._validate_options()

        except SystemExit as e:
            self.assertEqual(e.code, os.EX_DATAERR)
        else:
            self.fail("No Exception Raised")

    def test_pool_file_processing(self):
        self._test_pool_file_processing(
            self.tempfiles[0][1], ["pool1", "pool2", "pool3", "pool4", "pool5", "pool6", "pool7", "pool8"]
        )

    def test_pool_file_empty(self):
        try:
            self.cc.main(["--file", self.tempfiles[2][1]])
            self.cc._validate_options()

        except SystemExit as e:
            self.assertEqual(e.code, os.EX_DATAERR)
        else:
            self.fail("No Exception Raised")

    def test_pool_file_invalid(self):
        try:
            self.cc.main(["--file", "nonexistant_file.nope"])
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_DATAERR)
        else:
            self.fail("No Exception Raised")

    @patch("subscription_manager.cli_command.attach.is_simple_content_access")
    def test_auto_attach_sca_mode(self, mock_is_simple_content_access):
        """
        Test the case, when SCA mode is used. Auto-attach is not possible in this case
        """
        mock_is_simple_content_access.return_value = True
        try:
            self.cc.main("--auto")
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_USAGE)
        else:
            self.fail("No Exception Raised")

    @patch("subscription_manager.cli_command.attach.is_simple_content_access")
    def test_attach_sca_mode(self, mock_is_simple_content_access):
        """
        Test the case, when SCA mode is used. Attaching of pool is not possible in this case
        """
        mock_is_simple_content_access.return_value = True
        try:
            self.cc.main("--pool 123456789")
            self.cc._validate_options()
        except SystemExit as e:
            self.assertEqual(e.code, os.EX_USAGE)
        else:
            self.fail("No Exception Raised")

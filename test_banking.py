import shutil
import tempfile
import unittest

from bank_service import BankService
from database import CSVDatabase
from models import AccountStatus


class TestNationalBankingSystem(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db = CSVDatabase(data_dir=self.test_dir)
        self.service = BankService(db=self.db)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_add_customer_and_indian_phone_validation(self):
        # Invalid starting digit (must start with 6-9)
        ok, msg, _ = self.service.add_customer("Test", "1234567890", "t@test.com", "Savings", "1234", 500.0)
        self.assertFalse(ok)
        self.assertIn("Indian mobile number", msg)

        # Valid Indian number
        ok, msg, cust = self.service.add_customer("Rahul", "9876543210", "rahul@test.com", "Savings", "1234", 1000.0)
        self.assertTrue(ok)
        self.assertEqual(cust.account_no, "1001")
        self.assertEqual(self.db.load_bank_config().bank_balance, 1000.0)

        # Duplicate phone number rejected
        ok, msg, _ = self.service.add_customer("Clone", "9876543210", "clone@test.com", "Current", "4321", 500.0)
        self.assertFalse(ok)
        self.assertIn("already registered", msg)

    def test_three_failed_pins_freezes_account(self):
        _, _, cust = self.service.add_customer("Ananya", "9123456789", "a@test.com", "Savings", "5678", 2000.0)

        self.assertFalse(self.service.authenticate_customer(cust.account_no, "0000")[0])
        self.assertFalse(self.service.authenticate_customer(cust.account_no, "0000")[0])
        ok, msg, _ = self.service.authenticate_customer(cust.account_no, "0000")
        self.assertFalse(ok)
        self.assertIn("FROZEN", msg)

        refreshed = self.db.find_customer(cust.account_no)
        self.assertEqual(refreshed.status, AccountStatus.FROZEN.value)

    def test_deposit_withdraw_and_bank_reserve_check(self):
        _, _, cust = self.service.add_customer("Vikram", "9988776655", "v@test.com", "Savings", "1111", 500.0)

        ok, _, bal = self.service.deposit_money(cust.account_no, 300.0)
        self.assertTrue(ok)
        self.assertEqual(bal, 800.0)
        self.assertEqual(self.db.load_bank_config().bank_balance, 800.0)

        # Simulate lower bank reserve than customer balance
        self.db.update_bank_balance(-600.0)  # Reserve is now 200.0
        ok, msg, _ = self.service.withdraw_money(cust.account_no, 500.0)
        self.assertFalse(ok)
        self.assertIn("Bank reserve insufficient", msg)

    def test_transfer_and_delete_zero_balance(self):
        _, _, c1 = self.service.add_customer("User1", "9000000001", "u1@test.com", "Savings", "1111", 1000.0)
        _, _, c2 = self.service.add_customer("User2", "9000000002", "u2@test.com", "Current", "2222", 200.0)

        ok, _ = self.service.transfer_money(c1.account_no, c2.account_no, 1000.0)
        self.assertTrue(ok)

        # c1 now has 0 balance and can be deleted
        ok, _ = self.service.delete_customer(c1.account_no)
        self.assertTrue(ok)

        # c2 has 1200 balance and cannot be deleted
        ok, msg = self.service.delete_customer(c2.account_no)
        self.assertFalse(ok)
        self.assertIn("remaining balance", msg)


if __name__ == "__main__":
    unittest.main()
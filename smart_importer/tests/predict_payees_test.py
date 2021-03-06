"""Tests for the `PredictPostings` decorator"""

import logging
import unittest
from typing import List

from beancount.core.data import Transaction
from beancount.ingest.importer import ImporterProtocol
from beancount.parser import parser
from smart_importer import machinelearning_helpers as ml
from smart_importer.predict_payees import PredictPayees

LOG_LEVEL = logging.DEBUG
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# colorize the log output if the coloredlogs package is available
try:
    import coloredlogs
except ImportError as e:
    coloredlogs = None
if coloredlogs:
    coloredlogs.install(level=LOG_LEVEL)


class Testdata:
    test_data, errors, _ = parser.parse_string("""
        2017-01-06 * "Farmer Fresh" "Buying groceries"
          Assets:US:BofA:Checking  -2.50 USD

        2017-01-07 * "Groceries"
          Assets:US:BofA:Checking  -10.20 USD

        2017-01-10 * "" "Eating out with Joe"
          Assets:US:BofA:Checking  -38.36 USD

        2017-01-10 * "Dinner with Martin"
          Assets:US:BofA:Checking  -35.00 USD

        2017-01-10 * "Groceries"
          Assets:US:BofA:Checking  -53.70 USD

        2017-01-10 * "Gimme Coffee" "Coffee"
          Assets:US:BofA:Checking  -5.00 USD
        """)
    assert not errors

    training_data: List[Transaction]
    training_data, errors, _ = parser.parse_string("""
        2016-01-06 * "Farmer Fresh" "Buying groceries"
          Assets:US:BofA:Checking  -2.50 USD
          Expenses:Food:Groceries

        2016-01-07 * "Starbucks" "Coffee"
          Assets:US:BofA:Checking  -4.00 USD
          Expenses:Food:Coffee

        2016-01-07 * "Farmer Fresh" "Groceries"
          Assets:US:BofA:Checking  -10.20 USD
          Expenses:Food:Groceries

        2016-01-07 * "Gimme Coffee" "Coffee"
          Assets:US:BofA:Checking  -3.50 USD
          Expenses:Food:Coffee

        2016-01-08 * "Uncle Boons" "Eating out with Joe"
          Assets:US:BofA:Checking  -38.36 USD
          Expenses:Food:Restaurant

        2016-01-10 * "Walmarts" "Groceries"
          Assets:US:BofA:Checking  -53.70 USD
          Expenses:Food:Groceries

        2016-01-10 * "Gimme Coffee" "Coffee"
          Assets:US:BofA:Checking  -6.19 USD
          Expenses:Food:Coffee

        2016-01-10 * "Uncle Boons" "Dinner with Mary"
          Assets:US:BofA:Checking  -35.00 USD
          Expenses:Food:Restaurant

        2016-01-11 * "Farmer Fresh" "Groceries"
          Assets:US:BofA:Checking  -30.50 USD
          Expenses:Food:Groceries
        """)
    assert not errors

    filter_training_data_by_account = "Assets:US:BofA:Checking"

    correct_predictions = [
        'Farmer Fresh',
        'Farmer Fresh',
        'Uncle Boons',
        'Uncle Boons',
        'Farmer Fresh',
        'Gimme Coffee'
    ]


class BasicImporter(ImporterProtocol):
    def extract(self, file, existing_entries=None):
        return Testdata.test_data


class PredictPayeesTest(unittest.TestCase):
    '''
    Tests for machine learning functionality of the `PredictPayees` decorator.
    '''

    def setUp(self):
        '''
        Sets up the `PredictPayeesTest` unit test
        '''

        # define and decorate an importer:
        @PredictPayees(
            training_data=Testdata.training_data,
            filter_training_data_by_account="Assets:US:BofA:Checking",
            overwrite_existing_payees=False
        )
        class DecoratedImporter(BasicImporter):
            pass

        self.importerClass = DecoratedImporter
        self.importer = DecoratedImporter()

    def test_dummy_importer(self):
        '''
        Verifies the dummy importer
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        undecorated_importer = super(self.importerClass, self.importer)
        entries = undecorated_importer.extract('dummy-data')
        self.assertEqual(entries[0].narration, "Buying groceries")
        # print("Entries without predicted postings:")
        # printer.print_entries(entries)

    def test_unchanged_narrations(self):
        '''
        Verifies that the decorator leaves the narration intact
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        correct_narrations = [transaction.narration for transaction in Testdata.test_data]
        extracted_narrations = [transaction.narration for transaction in self.importer.extract("dummy-data")]
        self.assertEqual(extracted_narrations, correct_narrations)

    def test_unchanged_first_posting(self):
        '''
        Verifies that the decorator leaves the first posting intact
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        correct_first_postings = [transaction.postings[0] for transaction in Testdata.test_data]
        extracted_first_postings = [transaction.postings[0] for transaction in self.importer.extract("dummy-data")]
        self.assertEqual(extracted_first_postings, correct_first_postings)

    def test_predicted_payees(self):
        '''
        Verifies that the decorator adds predicted postings.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        transactions = self.importer.extract("dummy-data")
        predicted_payees = [transaction.payee for transaction in transactions]
        self.assertEqual(predicted_payees, Testdata.correct_predictions)

    def test_added_suggestions(self):
        '''
        Verifies that the decorator adds suggestions about accounts
        that are likely to be involved in the transaction.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        transactions = self.importer.extract("dummy-data")
        for transaction in transactions:
            suggestions = transaction.meta[ml.METADATA_KEY_SUGGESTED_PAYEES]
            self.assertTrue(len(suggestions),
                            msg=f"The list of suggested accounts should not be empty, "
                                f"but was found to be empty for transaction {transaction}.")


class PredictPostingsDecorationTest(unittest.TestCase):
    '''
    Tests for the different variants how the decoration can be applied.
    '''

    def test_class_decoration_with_arguments(self):
        '''
        Verifies that the decorator can be applied to importer classes,
        with training data provided as argument.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))

        @PredictPayees(
            training_data=Testdata.training_data,
            filter_training_data_by_account=Testdata.filter_training_data_by_account
        )
        class SmartImporter(BasicImporter):
            pass

        i = SmartImporter()
        self.assertIsInstance(i, SmartImporter,
                              'The decorated importer shall still be an instance of the undecorated class.')
        transactions = i.extract('file', existing_entries=Testdata.training_data)
        predicted_payees = [transaction.payee for transaction in transactions]
        self.assertEqual(predicted_payees, Testdata.correct_predictions)

    def test_method_decoration_with_arguments(self):
        '''
        Verifies that the decorator can be applied to an importer's extract method,
        with training data provided as argument.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        testcase = self

        class SmartImporter(BasicImporter):
            @PredictPayees(
                training_data=Testdata.training_data,
                filter_training_data_by_account=Testdata.filter_training_data_by_account
            )
            def extract(self, file, existing_entries=None):
                testcase.assertIsInstance(self, SmartImporter)
                return super().extract(file, existing_entries=existing_entries)

        i = SmartImporter()
        transactions = i.extract('file', existing_entries=Testdata.training_data)
        predicted_payees = [transaction.payee for transaction in transactions]
        self.assertEqual(predicted_payees, Testdata.correct_predictions)

    # TODO: implement reasonable defaults to fix this test case:
    @unittest.skip(
        "smart imports without arguments currently fail "
        "because the already known account is not filtered from the training data")
    def test_class_decoration_without_arguments(self):
        '''
        Verifies that the decorator can be applied to importer classes,
        without supplying any arguments.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))

        @PredictPayees()
        class SmartImporter(BasicImporter): pass

        i = SmartImporter()
        self.assertIsInstance(i, SmartImporter,
                              'The decorated importer shall still be an instance of the undecorated class.')
        transactions = i.extract('file', existing_entries=Testdata.training_data)
        predicted_payees = [transaction.payee for transaction in transactions]
        self.assertEqual(predicted_payees, Testdata.correct_predictions)

    # TODO: implement reasonable defaults to fix this test case:
    @unittest.skip(
        "smart imports without arguments currently fail "
        "because the already known account is not filtered from the training data")
    def test_method_decoration_without_arguments(self):
        '''
        Verifies that the decorator can be applied to an importer's extract method,
        without supplying any arguments.
        '''
        logger.info("Running Test Case: {id}".format(id=self.id().split('.')[-1]))
        testcase = self

        class SmartImporter(BasicImporter):
            @PredictPayees()
            def extract(self, file, existing_entries=None):
                testcase.assertIsInstance(self, SmartImporter)
                return super().extract(file, existing_entries=existing_entries)

        i = SmartImporter()
        transactions = i.extract('file', existing_entries=Testdata.training_data)
        predicted_payees = [transaction.payee for transaction in transactions]
        self.assertEqual(predicted_payees, Testdata.correct_predictions)


if __name__ == '__main__':
    # show test case execution output iff logging level is DEBUG or finer:
    show_output = LOG_LEVEL <= logging.DEBUG
    unittest.main(buffer=not show_output)

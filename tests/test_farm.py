#!/usr/bin/env python
#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.

import sys
import os
DIR = os.path.abspath(os.path.normpath(os.path.join(__file__,
    '..', '..', '..', '..', '..', 'trytond')))
if os.path.isdir(DIR):
    sys.path.insert(0, os.path.dirname(DIR))

import doctest
import unittest
import warnings

import trytond.tests.test_tryton
from trytond.tests.test_tryton import test_view, test_depends
from trytond.backend.sqlite.database import Database as SQLiteDatabase

SCENARIOS = [
    'scenario_move_event_test.rst',
    'scenario_feed_event_test.rst',
    'scenario_medication_event_test.rst',
    'scenario_transformation_event_test.rst',
    'scenario_removal_event_test.rst',
    'scenario_semen_extraction_event_test.rst',
    'scenario_insemination_event_test.rst',
    'scenario_pregnancy_diagnosis_event_test.rst',
    'scenario_abort_event_test.rst',
    'scenario_farrowing_event_test.rst',
    'scenario_foster_event_test.rst',
    'scenario_weaning_event_test.rst',
    'scenario_feed_inventory_test.rst',
    ]


class FarmTestCase(unittest.TestCase):
    '''
    Test Farm module.
    '''

    def setUp(self):
        trytond.tests.test_tryton.install_module('farm')

    def test0005views(self):
        '''
        Test views.
        '''
        test_view('farm')

    def test0006depends(self):
        '''
        Test depends.
        '''
        test_depends()


def doctest_dropdb(test):
    database = SQLiteDatabase().connect()
    cursor = database.cursor(autocommit=True)
    try:
        database.drop(cursor, ':memory:')
        cursor.commit()
    finally:
        cursor.close()


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FarmTestCase))
    for scenario in SCENARIOS:
        suite.addTests(doctest.DocFileSuite(scenario,
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

if __name__ == '__main__':
    warnings.filterwarnings(action='ignore', category=DeprecationWarning)
    if sys.argv and len(sys.argv) == 2 and '--only-unittest' in sys.argv:
        print "ONLY UNITTEST"
        unittest_suite = trytond.tests.test_tryton.suite()
        unittest_suite.addTests(
            unittest.TestLoader().loadTestsFromTestCase(FarmTestCase))
        unittest.TextTestRunner(verbosity=2).run(unittest_suite)
        sys.exit(0)
    if sys.argv and len(sys.argv) == 2 and '--only-scenario' in sys.argv:
        print "ONLY SCENARIO"
        scenario_suite = trytond.tests.test_tryton.suite()
        for scenario in SCENARIOS:
            scenario_suite.addTests(doctest.DocFileSuite(scenario,
                setUp=doctest_dropdb, tearDown=doctest_dropdb,
                encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
        unittest.TextTestRunner(verbosity=2).run(scenario_suite)
        sys.exit(0)
    if sys.argv and len(sys.argv) == 3 and '--only-scenario' in sys.argv:
        scenario = sys.argv[2]
        print "ONLY ONE SCENARIO: %s" % scenario
        scenario_suite = trytond.tests.test_tryton.suite()
        scenario_suite.addTests(doctest.DocFileSuite(scenario,
            setUp=doctest_dropdb, tearDown=doctest_dropdb, encoding='utf-8',
            optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
        unittest.TextTestRunner(verbosity=2).run(scenario_suite)
        sys.exit(0)
    if sys.argv and len(sys.argv) > 1:
        sys.exit("Unexpected number of params: %s.\n"
            "USAGE: test_farm.py [--only-unittest|--only-scenario]"
            % (sys.argv,))
    unittest.TextTestRunner(verbosity=2).run(suite())

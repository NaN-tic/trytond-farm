# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import doctest
import unittest

import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase
from trytond.tests.test_tryton import doctest_setup, doctest_teardown
from trytond.tests.test_tryton import doctest_checker

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


class FarmTestCase(ModuleTestCase):
    'Test Farm module'
    module = 'farm'


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FarmTestCase))
    for scenario in SCENARIOS:
        suite.addTests(doctest.DocFileSuite(scenario, setUp=doctest_setup,
                tearDown=doctest_teardown, encoding='utf-8',
                checker=doctest_checker,
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import doctest
import unittest

from trytond import backend
import trytond.tests.test_tryton
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.tests.test_tryton import doctest_setup, doctest_teardown

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

    @with_transaction()
    def test_ir_action_window(self):
        """
        Override test_ir_action_window to prevent its execution with sqlite
        backend. SQLite (v 3.16.2) has a bug that makes the process hang with
        100% CPU usage when search is executed on
        farm.feed.animal_location_date, which uses table_query.
        """
        if backend.name() == 'sqlite':
            return
        super().test_ir_action_window()

def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(FarmTestCase))
    for scenario in SCENARIOS:
        suite.addTests(doctest.DocFileSuite(scenario, setUp=doctest_setup,
                tearDown=doctest_teardown, encoding='utf-8',
                optionflags=doctest.REPORT_ONLY_FIRST_FAILURE))
    return suite

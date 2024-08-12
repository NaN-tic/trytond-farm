
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond import backend
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.modules.company.tests import CompanyTestMixin


class FarmTestCase(CompanyTestMixin, ModuleTestCase):
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
        if backend.name == 'sqlite':
            return
        super().test_ir_action_window()


del ModuleTestCase

#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Bool, Eval, Not
from trytond.pool import PoolMeta
from trytond.exceptions import UserError
from trytond.i18n import gettext

__all__ = ['QualityTest']


class QualityTest(metaclass=PoolMeta):
    __name__ = 'quality.test'

    semen_extraction = fields.One2One(
        'farm.semen_extraction.event-quality.test', 'test', 'event',
        string="Semen Extraction", readonly=True, states={
            'invisible': Not(Bool(Eval('semen_extraction', 0))),
            })

    @classmethod
    def draft(cls, tests):
        for test in tests:
            if (test.state != 'draft' and test.semen_extraction and
                    test.semen_extraction.state == 'validated'):
                raise UserError(gettext(
                        'farm.no_set_draft_semen_extraction_test',
                        test=test.rec_name))
        super(QualityTest, cls).draft(tests)

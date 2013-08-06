#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Bool, Eval, Not
from trytond.pool import PoolMeta

__all__ = ['QualityTest']
__metaclass__ = PoolMeta


class QualityTest:
    __name__ = 'quality.test'

    semen_extraction = fields.One2One(
        'farm.semen_extraction.event-quality.test', 'test', 'event',
        string="Semen Extraction", readonly=True, states={
            'invisible': Not(Bool(Eval('semen_extraction', 0))),
            })

    @classmethod
    def __setup__(cls):
        super(QualityTest, cls).__setup__()
        cls._error_messages.update({
                'no_set_draft_semen_extraction_test': ('The quality test "%s" '
                    'can\'t be set to Draft because it is related to a '
                    'validated semen extraction event.'),
                })

    @classmethod
    def draft(cls, tests):
        for test in tests:
            if (test.state != 'draft' and test.semen_extraction and
                    test.semen_extraction.state == 'validated'):
                cls.raise_user_exception('no_set_draft_semen_extraction_test',
                    test.rec_name)
        super(QualityTest, cls).draft(tests)

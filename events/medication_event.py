# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, Check
from trytond.pyson import Eval

from .feed_abstract_event import FeedEventMixin

__all__ = ['MedicationEvent']


class MedicationEvent(FeedEventMixin):
    'Medication Event'
    __name__ = 'farm.medication.event'
    _table = 'farm_medication_event'

    feed_product_uom_category = fields.Function(
        fields.Many2One('product.uom.category', 'Feed Uom Category'),
        'on_change_with_feed_product_uom_category')
    medication_start_date = fields.Function(fields.Date('Start Date'),
        'on_change_with_end_date')
    medication_end_date = fields.Date('End Date', domain=[
            ('medication_end_date', '>=', Eval('medication_start_date')),
            ], depends=['medication_start_date'])

    @classmethod
    def __setup__(cls):
        cls.feed_location.string = 'Feed/Medication Source'
        cls.feed_product.string = 'Feed/Medication Product'
        cls.feed_lot.string = 'Feed/Medication Lot'
        super(MedicationEvent, cls).__setup__()

        uom_clause = ('category', '=', Eval('feed_product_uom_category'))
        for clause in cls.feed_product.domain:
            if isinstance(clause, tuple) and clause == uom_clause:
                break
        else:
            cls.uom.domain.append(uom_clause)
        if 'feed_product_uom_category' not in cls.uom.depends:
            cls.uom.depends.append('feed_product_uom_category')

        t = cls.__table__()
        cls._sql_constraints += [
            ('quantity_positive', Check(t, t.quantity != 0),
                'farm.check_feed_quantity_non_zero'),
            ('quantity_1_for_animals',
                Check(t, (t.animal_type == 'group') | (t.quantity == 1) |
                    (t.quantity == -1)),
                'farm.check_feed_quantity_one_for_animals'),
            ('feed_quantity_positive', Check(t, t.feed_quantity != 0.0),
                'farm.check_feed_quantity_positive'),
            ]

    @fields.depends('feed_product')
    def on_change_with_feed_product_uom_category(self, name=None):
        if self.feed_product:
            return self.feed_product.default_uom_category.id

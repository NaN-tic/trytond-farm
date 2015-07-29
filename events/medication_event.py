# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields
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
    medication_end_date = fields.Date('End Date',
        domain=[
            ('medication_end_date', '>=', Eval('medication_start_date')),
            ],
        depends=['medication_start_date'])

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

        cls._error_messages.update({
                'animal_not_in_location': ('The medication event of animal '
                    '"%(animal)s" is trying to move it from location '
                    '"%(location)s" but it isn\'t there at '
                    '"%(timestamp)s".'),
                'group_not_in_location': ('The medication event of group '
                    '"%(group)s" is trying to move animals from location '
                    '"%(location)s" but there isn\'t any there at '
                    '"%(timestamp)s".'),
                'not_enought_feed_lot': ('The medication event "%(event)s" is '
                    'trying to move %(quantity)s of lot "%(lot)s" from silo '
                    '"%(location)s" but there isn\'t enought quantity there '
                    'at "%(timestamp)s".'),
                'not_enought_feed_product': ('The medication event '
                    '"%(event)s" is trying to move %(quantity)s of product '
                    '"%(product)s" from silo "%(location)s" but there isn\'t '
                    'enought quantity there at "%(timestamp)s".'),
                })
        cls._sql_constraints += [
            ('quantity_positive', 'check ( quantity != 0 )',
                'In Medication Events, the quantity can\'t be zero'),
            ('quantity_1_for_animals',
                ("check ( animal_type = 'group' or "
                    "(quantity = 1 or quantity = -1))"),
                'In Medication Events, the quantity must be 1 for Animals '
                '(not Groups).'),
            ('feed_quantity_positive', 'check ( feed_quantity != 0.0 )',
                'In Medication Events, the quantity must be positive (greater '
                'or equal to 1)'),
            ]

    @fields.depends('feed_product')
    def on_change_with_feed_product_uom_category(self, name=None):
        if self.feed_product:
            return self.feed_product.default_uom_category.id

# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pool import Pool
from trytond.pyson import Eval

from .feed_abstract_event import FeedEventMixin

__all__ = ['FeedEvent']


class FeedEvent(FeedEventMixin, ModelSQL, ModelView, Workflow):
    'Feed Event'
    __name__ = 'farm.feed.event'
    _table = 'farm_feed_event'

    feed_quantity_animal_day = fields.Numeric('Qty. per Animal-Day',
        digits=(16, 4), readonly=True,
        states={
            'required': Eval('state').in_(['validated', 'provisional']),
            }, depends=['unit_digits', 'state'])
    feed_inventory = fields.Reference('Inventory', selection='get_inventory',
        readonly=True, select=True,
        help='The inventory that generated this event automatically.')

    @classmethod
    def __setup__(cls):
        super(FeedEvent, cls).__setup__()
        cls.state.selection.append(('provisional', 'Provisional'))

        cls.feed_location.domain += [
            ('silo', '=', True),
            ('locations_to_fed', 'in', [Eval('location')]),
            ]
        cls.feed_location.depends += ['location']

        cls._sql_constraints += [
            ('quantity_positive', 'check ( quantity != 0 )',
                'In Feed Events, the quantity can\'t be zero'),
            ('quantity_1_for_animals',
                ("check ( animal_type = 'group' or "
                    "(quantity = 1 or quantity = -1))"),
                'In Feed Events, the quantity must be 1 for Animals (not '
                'Groups).'),
            ('feed_quantity_positive', 'check ( feed_quantity != 0.0 )',
                'In Feed Events, the quantity must be positive (greater or '
                'equal to 1)'),
            ]
        cls._transitions |= set((
                ('provisional', 'draft'),
                ))

    @classmethod
    def get_inventory(cls):
        IrModel = Pool().get('ir.model')
        models = IrModel.search([
                ('model', 'in', ['farm.feed.inventory',
                        'farm.feed.provisional_inventory']),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    @fields.depends('feed_location')
    def on_change_feed_location(self):
        if not self.feed_location or not self.feed_location.current_lot:
            return {
                'feed_product': None,
                'feed_lot': None,
                'feed_uom': None,
                }
        return {
            'feed_product': self.feed_location.current_lot.product.id,
            'feed_lot': self.feed_location.current_lot.id,
            'uom': self.feed_location.current_lot.product.default_uom.id,
            }

    def _validated_hook(self):
        super(FeedEvent, self)._validated_hook()
        if not self.feed_quantity_animal_day:
            qty_animal_day = self.feed_quantity / self.quantity
            if self.start_date:
                n_days = (self.timestamp.date() - self.start_date).days
                qty_animal_day = qty_animal_day / n_days

            self.feed_quantity_animal_day = qty_animal_day.quantize(
                Decimal('0.0001'))

    @classmethod
    def copy(cls, events, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['feed_quantity_animal_day'] = None
        default['feed_inventory'] = None
        return super(FeedEvent, cls).copy(events, default=default)

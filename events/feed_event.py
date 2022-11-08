# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from decimal import Decimal

from trytond.model import fields, ModelSQL, ModelView, Workflow, Check
from trytond.pool import Pool
from trytond.pyson import Eval, Id

from .feed_abstract_event import FeedEventMixin


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
        readonly=True,
        help='The inventory that generated this event automatically.')

    @classmethod
    def __setup__(cls):
        super(FeedEvent, cls).__setup__()

        product_uom_clause = ('default_uom.category', '=',
            Id('product', 'uom_cat_weight'))
        for clause in cls.feed_product.domain:
            if isinstance(clause, tuple) and clause == product_uom_clause:
                break
        else:
            cls.feed_product.domain.append(product_uom_clause)
        uom_weight_clause = ('category', '=', Id('product', 'uom_cat_weight'))
        for clause in cls.uom.domain:
            if isinstance(clause, tuple) and clause == uom_weight_clause:
                break
        else:
            cls.uom.domain.append(uom_weight_clause)

        cls.state.selection.append(('provisional', 'Provisional'))

        cls.feed_location.domain += [
            ('silo', '=', True),
            ('locations_to_fed', 'in', [Eval('location', -1)]),
            ]
        cls.feed_location.depends.add('location')

        t = cls.__table__()
        cls._sql_constraints += [
            ('quantity_positive', Check(t, t.quantity != 0),
                'farm.check_feed_quantity_non_zero'),
            ('quantity_1_for_animals',
                Check(t, (t.animal_type == 'group') | (t.quantity == 1) |
                    (t.quantity == -1)),
                'farm.check_feed_quantity_on_for_animals'),
            ('feed_quantity_positive', Check(t, t.feed_quantity != 0.0),
                'farm.check_feed_quantity_positive'),
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
            self.feed_product = None
            self.feed_lot = None
            self.uom = None
            return
        self.feed_product = self.feed_location.current_lot.product
        self.feed_lot = self.feed_location.current_lot
        self.uom = self.feed_location.current_lot.product.default_uom

    def _validated_hook(self):
        super(FeedEvent, self)._validated_hook()
        if not self.feed_quantity_animal_day:
            qty_animal_day = self.feed_quantity / self.quantity
            if self.start_date:
                n_days = (self.end_date - self.start_date).days
                if n_days != 0:
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

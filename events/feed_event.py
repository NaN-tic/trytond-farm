#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
#from trytond.model import fields
from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Eval

from .feed_abstract_event import FeedAbstractEvent

__all__ = ['FeedEvent']


class FeedEvent(FeedAbstractEvent, ModelSQL, ModelView, Workflow):
    'Feed Event'
    __name__ = 'farm.feed.event'
    _table = 'farm_feed_event'

    feed_inventory = fields.Many2One('farm.feed.inventory', 'Inventory',
        readonly=True,
        help='The inventory that generated this event automatically.')

    @classmethod
    def __setup__(cls):
        super(FeedEvent, cls).__setup__()
        cls.feed_location.domain += [
            ('silo', '=', True),
            ('locations_to_fed', 'in', [Eval('location')]),
            ]
        cls.feed_location.depends += ['location']
        cls.feed_location.on_change = ['feed_location', 'feed_product',
            'feed_lot', 'uom']
        cls._sql_constraints += [
            ('quantity_positive', 'check ( quantity != 0.0 )',
                'In Feed Events, the quantity must be positive (greater or '
                'equal to 1)'),
            ]

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

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['feed_inventory'] = None
        return super(FeedEvent, cls).copy(records, default=default)

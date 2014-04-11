#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Bool, Equal, Eval, Id, Not, Or
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN

__all__ = ['FeedAbstractEvent']


# It mustn't to be *registered* because of 'ir.model' nor 'ir.model.field' was
# created (no views related). It is implemented by Feed and Medication Event
class FeedAbstractEvent(AbstractEvent):
    'Feed Abstract Event'
    __name__ = 'farm.feed.abstract.event'
    _table = False

    location = fields.Many2One('stock.location', 'Location', required=True,
        domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ('warehouse', '=', Eval('farm')),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('farm', 0))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            }, depends=['farm', 'state'],
        context={'restrict_by_specie_animal_type': True})
    feed_location = fields.Many2One('stock.location', 'Feed Source',
        required=True, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', True),
            ('warehouse', '=', Eval('farm')),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('farm', 0))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            }, depends=['farm', 'state'])
    feed_product = fields.Many2One('product.product', 'Feed', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    feed_lot = fields.Many2One('stock.lot', 'Feed Lot', domain=[
            ('product', '=', Eval('feed_product')),
            ], states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['feed_product'])
    uom = fields.Many2One('product.uom', "UOM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        on_change_with=['feed_product'], states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['feed_product'])
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']),
        'on_change_with_unit_digits')
    quantity = fields.Numeric('Quantity', digits=(16, Eval('unit_digits', 2)),
        states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['unit_digits'])
    # TODO: start/end_date required?
    start_date = fields.Date('Start Date', states=_STATES_WRITE_DRAFT,
        help='Start date of the period in which the given quantity of product '
        'was consumed.')
    end_date = fields.Date('End Date', states=_STATES_WRITE_DRAFT,
        help='Start date of the period in which the given quantity of product '
        'was consumed.')
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN, depends=_DEPENDS_VALIDATED_ADMIN)

    @classmethod
    def __setup__(cls):
        super(FeedAbstractEvent, cls).__setup__()
        # TODO: location domain must to take date from event to allow feed
        # events (from inventories) of moved animals
        #cls.animal.domain += [
        #    If(Equal(Eval('state'), 'draft'),
        #        If(Bool(Eval('location', 0)),
        #            ('location', '=', Eval('location')),
        #            ('location.type', '=', 'storage')),
        #        ()),
        #    ]
        if 'state' not in cls.animal.depends:
            cls.animal.depends.append('state')
        if 'location' not in cls.animal.depends:
            cls.animal.depends.append('location')
        cls._sql_constraints += [
            ('check_start_date_end_date',
                'CHECK(end_date >= start_date)',
                'The End Date must be after the Start Date'),
            ]
        cls._error_messages.update({
                'animal_not_in_location': ('The feed event of animal '
                    '"%(animal)s" is trying to feed it in location '
                    '"%(location)s" but it isn\'t there at '
                    '"%(timestamp)s".'),
                'group_not_in_location': ('The feed event of group '
                    '"%(group)s" is trying to move animals from location '
                    '"%(location)s" but there isn\'t any there at '
                    '"%(timestamp)s".'),
                'not_enought_feed_lot': ('The feed event "%(event)s" is '
                    'trying to move %(quantity)s of lot "%(lot)s" from silo '
                    '"%(location)s" but there isn\'t enought quantity there '
                    'at "%(timestamp)s".'),
                'not_enought_feed_product': ('The feed event "%(event)s" is '
                    'trying to move %(quantity)s of product "%(product)s" '
                    'from silo "%(location)s" but there isn\'t enought '
                    'quantity there at "%(timestamp)s".'),
                })

    @staticmethod
    def valid_animal_types():
        return ['male', 'female', 'individual', 'group']

    def get_rec_name(self, name):
        return "%s %s to %s in %s at %s" % (self.quantity, self.uom.symbol,
            self.animal and self.animal.rec_name or self.animal_group.rec_name,
            self.location.rec_name, self.timestamp)

    def on_change_animal(self):
        res = super(FeedAbstractEvent, self).on_change_animal()
        res['location'] = (self.animal and self.animal.location.id or
            None)
        return res

    def on_change_with_uom(self, name=None):
        if self.feed_product:
            return self.feed_product.default_uom.id

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Create an stock move
        """
        pool = Pool()
        Move = pool.get('stock.move')
        Uom = pool.get('product.uom')
        todo_moves = []
        for feed_event in events:
            assert not feed_event.move, ('%s "%s" already has a related stock '
                'move: "%s"' % (type(feed_event), feed_event.id,
                    feed_event.move.id))
            if feed_event.animal_type != 'group':
                if not feed_event.animal.check_in_location(
                        feed_event.location,
                        feed_event.timestamp):
                    cls.raise_user_error('animal_not_in_location', {
                            'animal': feed_event.animal.rec_name,
                            'location': feed_event.location.rec_name,
                            'timestamp': feed_event.timestamp,
                            })
            else:
                if not feed_event.animal_group.check_in_location(
                        feed_event.location, feed_event.timestamp):
                    cls.raise_user_error('group_not_in_location', {
                            'group': feed_event.animal_group.rec_name,
                            'location': feed_event.location.rec_name,
                            'timestamp': feed_event.timestamp,
                            })

            quantity = feed_event.quantity
            if feed_event.uom.id != feed_event.feed_product.default_uom.id:
                # TODO: it uses compute_price() because quantity is a Decimal
                # quantity in feed_product default uom. The method is not for
                # this purpose but it works
                quantity = Uom.compute_price(
                    feed_event.feed_product.default_uom, feed_event.quantity,
                    feed_event.uom)
            with Transaction().set_context(
                    locations=[feed_event.feed_location.id],
                    stock_date_end=feed_event.timestamp.date()):
                if feed_event.feed_lot:
                    if feed_event.feed_lot.quantity < quantity:
                        cls.raise_user_error('not_enought_feed_lot', {
                                'event': feed_event.rec_name,
                                'lot': feed_event.feed_lot.rec_name,
                                'location': feed_event.feed_location.rec_name,
                                'quantity': feed_event.quantity,
                                'timestamp': feed_event.timestamp,
                                })
                else:
                    if feed_event.feed_product.quantity < quantity:
                        cls.raise_user_error('not_enought_feed_product', {
                                'event': feed_event._rec_name,
                                'product': feed_event.feed_product._rec_name,
                                'location': feed_event.feed_location._rec_name,
                                'quantity': feed_event.quantity,
                                'timestamp': feed_event.timestamp,
                                })

            new_move = feed_event._get_event_move()
            new_move.save()
            todo_moves.append(new_move)
            feed_event.move = new_move
            feed_event.save()
        Move.assign(todo_moves)
        Move.do(todo_moves)

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        return Move(
            product=self.feed_product.id,
            uom=self.uom.id,
            quantity=float(self.quantity),
            from_location=self.feed_location,
            to_location=self.farm.production_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.feed_lot and self.feed_lot,
            origin=self)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['move'] = None
        return super(FeedAbstractEvent, cls).copy(records, default=default)

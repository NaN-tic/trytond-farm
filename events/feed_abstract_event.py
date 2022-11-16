# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime, date

from trytond.model import fields, ModelView, Workflow, Check
from trytond.pyson import Bool, Equal, Eval, Not, Or
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_WRITE_DRAFT_VALIDATED, \
    _DEPENDS_WRITE_DRAFT_VALIDATED, _STATES_VALIDATED_ADMIN, \
    _DEPENDS_VALIDATED_ADMIN


# It mustn't to be *registered* because of 'ir.model' nor 'ir.model.field' was
# created (no views related). It is implemented by Feed and Medication Event
class FeedEventMixin(AbstractEvent):
    'Feed Event Mixin implemented by Feed and Medication events'

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
    quantity = fields.Integer('Num. of animals', required=True,
        states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['animal_type', 'animal_group', 'location', 'state'])
    feed_location = fields.Many2One('stock.location', 'Feed Source',
        required=True, domain=[
            ('type', '=', 'storage'),
            ('warehouse', '=', Eval('farm', -1)),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('farm', 0))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            }, depends=['farm', 'state'])
    feed_product = fields.Many2One('product.product', 'Feed',
        states=_STATES_WRITE_DRAFT_VALIDATED,
        depends=_DEPENDS_WRITE_DRAFT_VALIDATED)
    feed_lot = fields.Many2One('stock.lot', 'Feed Lot', domain=[
            ('product', '=', Eval('feed_product')),
            ('quantity', '>', 0.0)
            ], states={
                'readonly': (Not(Bool(Eval('farm'))) |
                    Not(Equal(Eval('state'), 'draft'))),
                },
        depends=_DEPENDS_WRITE_DRAFT + ['feed_product'],
        search_context={
            'locations': [Eval('farm')],
            'stock_date_end': date.today(),
            })
    uom = fields.Many2One('product.uom', "UOM", required=True,
        states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['feed_product'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    feed_quantity = fields.Numeric('Consumed Quantity', required=True,
        digits=(16, Eval('unit_digits', 2)), states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['unit_digits'])
    # TODO: start/end_date required?
    start_date = fields.Date('Start Date', states=_STATES_WRITE_DRAFT,
        help='Start date of the period in which the given quantity of product '
        'was consumed.', domain=[
            'OR',
                [('start_date', '=', None)],
                [('start_date', '<=', Eval('end_date'))],
            ], depends=['end_date'])
    end_date = fields.Function(fields.Date('End Date',
            help='End date of the period in which the given quantity of '
            'product was consumed. It is the date of event\'s timestamp.'),
        'on_change_with_end_date')
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN, depends=_DEPENDS_VALIDATED_ADMIN)

    @classmethod
    def __setup__(cls):
        super(FeedEventMixin, cls).__setup__()
        # TODO: location domain must to take date from event to allow feed
        # events (from inventories) of moved animals
        # cls.animal.domain += [
        #     If(Equal(Eval('state'), 'draft'),
        #         If(Bool(Eval('location', 0)),
        #             ('location', '=', Eval('location')),
        #             ('location.type', '=', 'storage')),
        #         ()),
        #     ]
        # if 'state' not in cls.animal.depends:
        #     cls.animal.depends.add('state')
        # if 'location' not in cls.animal.depends:
        #     cls.animal.depends.add('location')
        t = cls.__table__()
        cls._sql_constraints += [
            ('check_start_date_timestamp',
                Check(t, t.timestamp >= t.start_date),
                'farm.timestamp_after_start_date'),
            ]

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def valid_animal_types():
        return ['male', 'female', 'individual', 'group']

    def get_rec_name(self, name):
        animal_name = (self.animal.rec_name if self.animal
            else self.animal_group.rec_name)
        return "%s %s to %s in %s at %s" % (self.feed_quantity,
            self.uom.symbol, animal_name,
            self.location.rec_name, self.timestamp)

    def on_change_animal(self):
        super(FeedEventMixin, self).on_change_animal()
        if self.animal and self.animal.location:
            self.location = self.animal.location.id

    def on_change_animal_group(self):
        super(FeedEventMixin, self).on_change_animal_group()
        if self.animal_group and len(self.animal_group.locations) == 1:
            self.location = self.animal_group.locations[0].id

    @fields.depends('animal_type', 'animal_group', 'location', 'timestamp')
    def on_change_with_quantity(self):
        Lot = Pool().get('stock.lot')
        if self.animal_type != 'group':
            return 1
        if not self.animal_group or not self.location:
            return None
        with Transaction().set_context(
                locations=[self.location.id],
                stock_date_end=self.timestamp.date()):
            return int(Lot(self.animal_group.lot.id).quantity) or None

    @fields.depends('feed_product')
    def on_change_with_uom(self, name=None):
        if self.feed_product:
            return self.feed_product.default_uom.id

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends('timestamp')
    def on_change_with_end_date(self, name=None):
        timestamp = self.timestamp or self.default_timestamp()
        return timestamp.date()

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events, check_feed_available=True):
        """
        Create an stock move
        """
        pool = Pool()
        Move = pool.get('stock.move')
        todo_moves = []
        for feed_event in events:
            assert not feed_event.move, ('%s "%s" already has a related stock '
                'move: "%s"' % (type(feed_event), feed_event.id,
                    feed_event.move.id))

            feed_event.check_animals_available()
            if check_feed_available:
                feed_event.check_feed_available()

            new_move = feed_event._get_event_move()
            new_move.save()
            todo_moves.append(new_move)

            feed_event.move = new_move
            feed_event._validated_hook()
            feed_event.save()
        Move.assign(todo_moves)
        Move.do(todo_moves)

    def check_animals_available(self):
        if self.animal_type != 'group':
            if not self.animal.check_in_location(self.location,
                    self.timestamp):
                raise UserError(gettext('farm.animal_not_in_location',
                        animal=self.animal.rec_name,
                        location=self.location.rec_name,
                        timestamp=self.timestamp,
                        ))
        else:
            if not self.animal_group.check_in_location(self.location,
                    self.timestamp, self.quantity):
                raise UserError(gettext('farm.group_not_in_location',
                        group=self.animal_group.rec_name,
                        from_location=self.location.rec_name,
                        quantity=self.quantity,
                        timestamp=self.timestamp,
                        ))
            if self.start_date:
                start_timestamp = datetime.combine(self.start_date,
                    self.timestamp.time())
                if not self.animal_group.check_in_location(self.location,
                        start_timestamp, self.quantity):
                    raise UserError(gettext('farm.group_not_in_location',
                            group=self.animal_group.rec_name,
                            from_location=self.location.rec_name,
                            quantity=self.quantity,
                            timestamp=start_timestamp,
                            ))

    def check_feed_available(self):
        pool = Pool()
        Uom = pool.get('product.uom')
        Product = pool.get('product.product')
        Lot = pool.get('stock.lot')

        if not self.feed_product:
            return

        feed_quantity = self.feed_quantity
        if self.uom.id != self.feed_product.default_uom.id:
            # TODO: it uses compute_price() because quantity is a Decimal
            # quantity in feed_product default uom. The method is not for
            # this purpose but it works
            feed_quantity = Uom.compute_price(self.feed_product.default_uom,
                self.feed_quantity, self.uom)
        assert self.feed_location.id, self.feed_location
        with Transaction().set_context(locations=[self.feed_location.id],
                stock_date_end=self.timestamp.date()):
            if self.feed_lot:
                lot = Lot(self.feed_lot.id)
                if lot.quantity < feed_quantity:
                    raise UserError(gettext('farm.not_enough_feed_lot',
                            event=self.rec_name,
                            lot=self.feed_lot.rec_name,
                            location=self.feed_location.rec_name,
                            quantity=feed_quantity,
                            timestamp=self.timestamp,
                            ))
            else:
                product = Product(self.feed_product.id)
                if product.quantity < feed_quantity:
                    raise UserError(gettext('farm.not_enough_feed_product',
                            event=self.rec_name,
                            product=self.feed_product.rec_name,
                            location=self.feed_location.rec_name,
                            quantity=feed_quantity,
                            timestamp=self.timestamp,
                            ))

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Company = pool.get('company.company')

        context = Transaction().context
        company = Company(context['company'])

        move = Move(
            product=self.feed_product.id,
            uom=self.uom.id,
            quantity=float(self.feed_quantity),
            from_location=self.feed_location,
            to_location=self.farm.production_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=company,
            origin=self)
        if self.feed_lot:
            move.lot = self.feed_lot
            move.unit_price = self.feed_lot.cost_price
        return move

    def _validated_hook(self):
        pass

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['move'] = None
        return super(FeedEventMixin, cls).copy(records, default=default)

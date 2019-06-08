#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelSQL, ModelView, Workflow, Check
from trytond.pyson import Bool, Equal, Eval, If, Not, Or
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN

__all__ = ['RemovalType', 'RemovalReason', 'RemovalEvent']


class RemovalType(ModelSQL, ModelView):
    '''Removal Event Type'''
    __name__ = 'farm.removal.type'
    _order_name = 'name'

    name = fields.Char('Name', required=True, translate=True)


class RemovalReason(ModelSQL, ModelView):
    '''Removal Event Reason'''
    __name__ = 'farm.removal.reason'
    _order_name = 'name'

    name = fields.Char('Name', required=True, translate=True)


class RemovalEvent(AbstractEvent):
    '''Farm Removal Event'''
    __name__ = 'farm.removal.event'
    _table = 'farm_removal_event'

    from_location = fields.Many2One('stock.location', 'Origin',
        required=True, domain=[
            ('warehouse', '=', Eval('farm')),
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('farm', 0))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            }, depends=['farm', 'state'],
        context={'restrict_by_specie_animal_type': True})
    quantity = fields.Integer('Quantity', required=True,
        states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['animal_type', 'animal_group', 'timestamp', 'from_location',
            'state'])
    removal_type = fields.Many2One('farm.removal.type', 'Type',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    reason = fields.Many2One('farm.removal.reason', 'Reason',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True, domain=[
            ('lot', '=', Eval('lot')),
            ],
        states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN + ['lot'])

#    # TODO: Extra
#    customer = fields.Many2One('party.party', 'Customer',
#        help='Company that is purchasing the animal (if any).')
#    weight = fields.Float('Weight'),

    @classmethod
    def __setup__(cls):
        super(RemovalEvent, cls).__setup__()
        cls.animal.domain += [
            If(Equal(Eval('state'), 'draft'),
                If(Bool(Eval('from_location', 0)),
                    ('location', '=', Eval('from_location')),
                    ('location.type', '=', 'storage')),
                ('location.type', '=', 'lost_found')),
            ]
        if 'from_location' not in cls.animal.depends:
            cls.animal.depends.append('from_location')
        if 'farm' not in cls.animal.depends:
            cls.animal.depends.append('farm')
        t = cls.__table__()
        cls._sql_constraints += [
            ('quantity_positive', Check(t, t.quantity != 0),
                'farm.check_removal_quantity_positive'),
            ('quantity_1_for_animals', Check(t, t.animal_type == 'group' or
                    t.quantity == 1 or t.quantity == -1),
                'farm.check_removal_quantity_one_for_animals'),
            ]

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def valid_animal_types():
        return ['male', 'female', 'individual', 'group']

    @fields.depends('animal')
    def on_change_animal(self):
        super(RemovalEvent, self).on_change_animal()
        self.from_location = self.animal and self.animal.location.id or None

    @fields.depends('animal_group', 'from_location', 'farm', 'timestamp',
        'quantity')
    def on_change_animal_group(self):
        pool = Pool()
        AnimalGroup = pool.get('farm.animal.group')
        Location = pool.get('stock.location')

        if self.animal_group is None:
            self.from_location = None
            return

        locations = AnimalGroup.get_locations([self.animal_group], None)

        if len(locations) == 1:
            location_id, = locations[self.animal_group.id]
            location = Location(location_id)
            if self.farm is not None and location.warehouse != self.farm:
                self.from_location = None
                return
            with Transaction().set_context(locations=[location_id],
                    stock_date_end=self.timestamp.date()):
                quantity = None
                if not self.quantity:
                    quantity = self.animal_group.lot.quantity
                self.from_location = location
                self.quantity = quantity

    @fields.depends('animal_type')
    def on_change_with_quantity(self):
        if self.animal_type != 'group':
            return 1

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        '''
        Create stock move:
        What: production_lot_id,
            From: Current Location, To: removed_location_id from configuration,
            Quantity: 'quantity'
        Fill in field 'move_id' with the created stock move id.
        Fill in 'removal' and 'removal_date' of the animal.
        '''
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        todo_moves = []
        for removal_event in events:
            assert not removal_event.move, ('Removal Event "%s" already has a '
                'related stock move: "%s"' % (removal_event.id,
                    removal_event.move.id))
            if removal_event.animal_type != 'group':
                if not removal_event.animal.check_in_location(
                        removal_event.from_location,
                        removal_event.timestamp):
                    raise UserError(gettext('farm.animal_not_in_location',
                            animal=removal_event.animal.rec_name,
                            from_location=removal_event.from_location.rec_name,
                            timestamp=removal_event.timestamp,
                            ))
                removal_event._check_existing_validated_removal_events()
            else:
                if not removal_event.animal_group.check_in_location(
                        removal_event.from_location,
                        removal_event.timestamp,
                        removal_event.quantity):
                    raise UserError(gettext('farm.group_not_in_location',
                            group=removal_event.animal_group.rec_name,
                            from_location=removal_event.from_location.rec_name,
                            quantity=removal_event.quantity,
                            timestamp=removal_event.timestamp,
                            ))

            new_move = removal_event._get_event_move()
            new_move.save()
            todo_moves.append(new_move)

            removal_event.move = new_move
            removal_event.save()
        Move.assign(todo_moves)
        Move.do(todo_moves)

        for removal_event in events:
            if removal_event.animal_type != 'group':
                animal = removal_event.animal
                animal.removal_date = removal_event.timestamp.date()
                if removal_event.reason:
                    animal.removal_reason = removal_event.reason
                animal.active = False
                animal.save()
            else:
                animal_group = removal_event.animal_group

                to_remove = False
                storage_locations = Location.search([
                        ('type', '=', 'storage'),
                        ])
                with Transaction().set_context(
                        locations=[l.id for l in storage_locations],
                        stock_date_end=removal_event.timestamp.date()):
                    if animal_group.lot.quantity == 0:
                        to_remove = True

                if to_remove:
                    animal_group.removal_date = removal_event.timestamp.date()
                    animal_group.active = False
                    animal_group.save()

    def _check_existing_validated_removal_events(self):
        assert self.animal_type != 'group' and self.animal, (
            "_check_existing_validated_removal_events() must to be called for "
            "Removal Events of animals")
        n_validated_events = self.search([
                ('animal', '=', self.animal.id),
                ('state', '=', 'validated'),
                ], count=True)
        if n_validated_events:
            raise UserError(gettext(
                    'farm.already_exist_validated_removal_event',
                    animal=self.animal.rec_name))
        return True

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        lot = (self.animal_type != 'group' and self.animal.lot or
            self.animal_group.lot)
        return Move(
            product=lot.product.id,
            uom=lot.product.default_uom.id,
            quantity=self.quantity,
            from_location=self.from_location.id,
            to_location=self.specie.removed_location.id,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=lot.id,
            origin=self,
            )

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['move'] = None
        return super(RemovalEvent, cls).copy(records, default=default)

# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Bool, Equal, Eval, Id, If, Not, Or
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN

__all__ = ['MoveEvent']


class MoveEvent(AbstractEvent):
    '''Farm Move Event'''
    __name__ = 'farm.move.event'
    _table = 'farm_move_event'

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
    to_location = fields.Many2One('stock.location', 'Destination',
        required=True, domain=[
            ('type', 'in', ['storage', 'customer']),
            ('silo', '=', False),
            ('id', '!=', Eval('from_location')),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('from_location', 0))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            }, depends=['from_location', 'state'],
        context={'restrict_by_specie_animal_type': True})
    to_location_warehouse = fields.Function(fields.Many2One('stock.location',
        'Destination warehouse',
            states={
                'invisible': True,
            }),
        'on_change_with_to_location_warehouse')
    quantity = fields.Integer('Quantity', required=True,
        states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['animal_type', 'animal_group', 'from_location', 'state'])
    unit_price = fields.Numeric('Unit Price', required=True, digits=(16, 4),
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            'invisible': Equal(Eval('to_location_warehouse'), Eval('farm')),
            }, depends=['state', 'to_location'],
        help='Unitary cost of Animal or Group for analytical accounting.')
    uom = fields.Many2One('product.uom', "UOM",
        domain=[('category', '=', Id('product', 'uom_cat_weight'))],
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            'required': Bool(Eval('weight')),
            }, depends=['state', 'weight'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    weight = fields.Numeric('Weight', digits=(16, Eval('unit_digits', 2)),
        states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['unit_digits'])
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True, domain=[
            ('lot', '=', Eval('lot')),
            ],
        states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN + ['lot'])
    weight_record = fields.Reference('Weight Record', selection=[
            (None, ''),
            ('farm.animal.weight', 'Animal Weight'),
            ('farm.animal.group.weight', 'Group Weight'),
            ],
        readonly=True, states={
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            }, depends=['state', 'weight'])

    @classmethod
    def __setup__(cls):
        super(MoveEvent, cls).__setup__()
        cls.animal.domain += [
            If(Equal(Eval('state'), 'draft'),
                If(Bool(Eval('from_location', 0)),
                    ('location', '=', Eval('from_location')),
                    ('location.type', '=', 'storage')),
                ('location', '=', Eval('to_location'))),
            ]
        if 'state' not in cls.animal.depends:
            cls.animal.depends.append('state')
        if 'from_location' not in cls.animal.depends:
            cls.animal.depends.append('from_location')
        if 'to_location' not in cls.animal.depends:
            cls.animal.depends.append('to_location')
        cls._error_messages.update({
                'animal_not_in_location': ('The move event of animal '
                    '"%(animal)s" is trying to move it from location '
                    '"%(from_location)s" but it isn\'t there at '
                    '"%(timestamp)s".'),
                'group_not_in_location': ('The move event of group '
                    '"%(group)s" is trying to move %(quantity)s animals '
                    'from location "%(from_location)s" but there isn\'t '
                    'enough there at "%(timestamp)s".'),
                })
        cls._sql_constraints += [
            ('quantity_positive', 'check ( quantity != 0 )',
                'In Move Events, the quantity can\'t be zero'),
            ('quantity_1_for_animals',
                ("check ( animal_type = 'group' or "
                    "(quantity = 1 or quantity = -1))"),
                'In Move Events, the quantity must be 1 for Animals (not '
                'Groups).'),
            ('weight_0_or_positive', "check ( weight >= 0.0 )",
                'In Move Events, the weight can\'t be zero'),
            ]

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def default_uom():
        return Pool().get('ir.model.data').get_id('product', 'uom_kilogram')

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def valid_animal_types():
        return ['male', 'female', 'individual', 'group']

    def on_change_animal(self):
        res = super(MoveEvent, self).on_change_animal()
        res['from_location'] = (self.animal and self.animal.location.id or
            None)
        return res

    @fields.depends('animal_type', 'animal_group', 'from_location',
        'timestamp')
    def on_change_with_quantity(self):
        if self.animal_type != 'group':
            return 1
        if not self.animal_group or not self.from_location:
            return None
        with Transaction().set_context(
                locations=[self.from_location.id],
                stock_date_end=self.timestamp.date()):
            return self.animal_group.lot.quantity or None

    @fields.depends('animal_type', 'animal', 'animal_group')
    def on_change_with_unit_price(self):
        if self.animal_type != 'group' and self.animal:
            return self.animal.lot.product.cost_price
        elif self.animal_type == 'group' and self.animal_group:
            return self.animal_group.lot.product.cost_price

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @fields.depends('to_location')
    def on_change_with_to_location_warehouse(self, name=None):
        if self.to_location:
            return self.to_location.warehouse.id

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Create an stock move and, if weight > 0.0, a farm.animal[.group].weight
        """
        Move = Pool().get('stock.move')
        todo_moves, to_validate = [], []
        for move_event in events:
            assert not move_event.move, ('Move Event "%s" already has a '
                'related stock move: "%s"' % (move_event.id,
                    move_event.move.id))
            if move_event.animal_type != 'group':
                if not move_event.animal.check_in_location(
                        move_event.from_location,
                        move_event.timestamp):
                    cls.raise_user_error('animal_not_in_location', {
                            'animal': move_event.animal.rec_name,
                            'from_location':
                                move_event.from_location.rec_name,
                            'timestamp': move_event.timestamp,
                            })
                move_event.animal.check_allowed_location(
                        move_event.to_location, move_event.rec_name)
            else:
                if not move_event.animal_group.check_in_location(
                        move_event.from_location,
                        move_event.timestamp,
                        move_event.quantity):
                    cls.raise_user_error('group_not_in_location', {
                            'group': move_event.animal_group.rec_name,
                            'from_location':
                                move_event.from_location.rec_name,
                            'quantity': move_event.quantity,
                            'timestamp': move_event.timestamp,
                            })
                move_event.animal_group.check_allowed_location(
                    move_event.to_location, move_event.rec_name)

            new_move = move_event._get_event_move()
            new_move.save()
            todo_moves.append(new_move)
            move_event.move = new_move
            if move_event.weight:
                assert not move_event.weight_record, ('Move Event "%s" '
                    'already has a related weight record: "%s"'
                    % (move_event.id, move_event.weight_record))
                new_weight_record = move_event._get_weight_record()
                new_weight_record.save()
                move_event.weight_record = new_weight_record
            move_event.save()
            # We also move the farrowing group if any
            if (move_event.animal_type == 'female' and
                    move_event.animal.farrowing_group):
                farrowing_group = move_event.animal.farrowing_group
                farrowing_group.check_allowed_location(
                    move_event.to_location, move_event.rec_name)
                child_event, = cls.copy([move_event], {
                        'animal_type': 'group',
                        'animal': None,
                        'weight': None,
                        'animal_group': farrowing_group.id,
                        'quantity': farrowing_group.quantity,
                        })
                to_validate.append(child_event)
        Move.assign(todo_moves)
        Move.do(todo_moves)
        if to_validate:
            cls.validate_event(to_validate)

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('stock_lot_cost',
            'cost_category_standard_price')
        context = Transaction().context

        lot = (self.animal_type != 'group' and self.animal.lot or
            self.animal_group.lot)

        if lot and self.unit_price and lot.cost_price != self.unit_price:
            cost_line = LotCostLine()
            cost_line.lot = lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = (self.unit_price - lot.cost_price
                if lot.cost_price else self.unit_price)
            cost_line.save()

        return Move(
            product=lot.product,
            uom=lot.product.default_uom,
            quantity=self.quantity,
            from_location=self.from_location,
            to_location=self.to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=lot,
            unit_price=self.unit_price,
            origin=self)

    def _get_weight_record(self):
        pool = Pool()
        AnimalWeight = pool.get('farm.animal.weight')
        AnimalGroupWeight = pool.get('farm.animal.group.weight')
        if self.animal_type != 'group':
            return AnimalWeight(
                animal=self.animal.id,
                timestamp=self.timestamp,
                uom=self.uom,
                weight=self.weight,
                )
        else:
            return AnimalGroupWeight(
                group=self.animal_group.id,
                timestamp=self.timestamp,
                quantity=self.quantity,
                uom=self.uom,
                weight=self.weight,
                )

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'move': None,
                'weight_record': None,
                })
        return super(MoveEvent, cls).copy(records, default=default)

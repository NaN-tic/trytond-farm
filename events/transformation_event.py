#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Bool, Equal, Eval, If, Not, Or
from trytond.pool import Pool
from trytond.rpc import RPC
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, _STATES_VALIDATED_ADMIN, \
    _DEPENDS_VALIDATED_ADMIN

__all__ = ['TransformationEvent']


class TransformationEvent(AbstractEvent):
    '''Farm Transformation Event'''
    __name__ = 'farm.transformation.event'
    _table = 'farm_transformation_event'

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
    to_animal_type = fields.Selection('get_to_animal_types',
        "Animal Type to Transform", required=True, states={
            'readonly': Or(Not(Equal(Eval('state'), 'draft')),
                Bool(Eval('to_location'))),
            }, depends=['animal_type', 'state'])
    to_location = fields.Many2One('stock.location', 'Destination',
        required=True, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states={
            'readonly': Or(
                Not(Bool(Eval('from_location', 0))),
                Not(Bool(Eval('to_animal_type', ''))),
                Not(Equal(Eval('state'), 'draft')),
                ),
            },
        context={
            'restrict_by_specie_animal_type': True,
            'animal_type': Eval('to_animal_type'),
            },
        depends=['from_location', 'state', 'to_animal_type'])
    quantity = fields.Integer('Quantity', required=True,
        states={
            'invisible': Or(Not(Equal(Eval('animal_type'), 'group')),
                Not(Equal(Eval('to_animal_type'), 'group'))),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['animal_type', 'to_animal_type', 'state'])
    to_animal = fields.Many2One('farm.animal', 'Destination Animal',
        select=True, readonly=True, states={
            'invisible': Equal(Eval('to_animal_type'), 'group'),
            },
        depends=['specie', 'animal_type', 'to_animal_type'])
    to_animal_group = fields.Many2One('farm.animal.group', 'Destination Group',
        domain=[
            ('specie', '=', Eval('specie')),
            ('farms', 'in', [Eval('farm')]),
            ],
        select=True, states={
            'invisible': Not(Equal(Eval('to_animal_type'), 'group')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['specie', 'farm', 'to_animal_type', 'state'],
        help='Select a Destination Group if you want to add the transformed '
        'animals to this group. To create a new group leave it empty.')
    in_move = fields.Many2One('stock.move', 'Input Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN, depends=_DEPENDS_VALIDATED_ADMIN)
    out_move = fields.Many2One('stock.move', 'Output Stock Move',
        readonly=True, states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN)

    @classmethod
    def __setup__(cls):
        super(TransformationEvent, cls).__setup__()
        cls.animal.domain += [
            If(Equal(Eval('state'), 'draft'),
                If(Bool(Eval('from_location', 0)),
                    ('location', '=', Eval('from_location')),
                    ('location.type', '=', 'storage')),
                ('location.type', '=', 'production')),
            ]
        if 'state' not in cls.animal.depends:
            cls.animal.depends.append('state')
        if 'from_location' not in cls.animal.depends:
            cls.animal.depends.append('from_location')
        if 'to_location' not in cls.animal.depends:
            cls.animal.depends.append('to_location')
        cls.__rpc__['get_to_animal_types'] = RPC(instantiate=0)
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
                'In Transformation Events, the quantity must be positive '
                '(greater or equal to 1)'),
            ('quantity_1_for_animals',
                ("check ( animal_type = 'group' and to_animal_type = 'group' "
                    "or (quantity = 1 or quantity = -1) )"),
                'In Transformation Events, the quantity must be 1 for Animals '
                '(not Groups).'),
            ]

    @staticmethod
    def default_quantity():
        return 1

    @staticmethod
    def valid_animal_types():
        return ['male', 'female', 'individual', 'group']

    @fields.depends('animal')
    def on_change_animal(self):
        res = super(TransformationEvent, self).on_change_animal()
        res['from_location'] = (self.animal and self.animal.location.id or
            None)
        return res

    @fields.depends('animal_type', 'to_animal_type', 'animal_group',
        'from_location', 'timestamp')
    def on_change_with_quantity(self):
        if self.animal_type != 'group' or self.to_animal_type != 'group':
            return 1
        if not self.animal_group or not self.from_location:
            return None
        with Transaction().set_context(
                locations=[self.from_location.id],
                stock_date_end=self.timestamp.date()):
            return self.animal_group.lot.quantity

    @fields.depends('animal_type')
    def get_to_animal_types(self):
        """
        Returns the list of allowed destination types for the suplied 'type'
         * group -> male, female, individual, group
         * male -> individual, group
         * female -> individual, group
         * individual -> male, female, group
        """
        if self.animal_type == 'group':
            return [
                ('male', 'Male'),
                ('female', 'Female'),
                ('individual', 'Individual'),
                ('group', 'Group'),
                ]
        elif self.animal_type in ('male', 'female'):
            return [
                ('individual', 'Individual'),
                ('group', 'Group'),
                ]
        elif self.animal_type == 'individual':
            return [
                ('male', 'Male'),
                ('female', 'Female'),
                ('group', 'Group'),
                ]
        return []

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Create the input and output stock moves.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        todo_moves = []
        for transf_event in events:
            assert (not transf_event.in_move and
                not transf_event.out_move), ('Transformation Event '
                '"%s" already has the related stock moves: IN:"%s", OUT:"%s"'
                % (transf_event.id,
                    transf_event.in_move.id,
                    transf_event.out_move.id))
            if transf_event.animal_type == 'group':
                if not transf_event.animal_group.check_in_location(
                        transf_event.from_location,
                        transf_event.timestamp,
                        transf_event.quantity):
                    cls.raise_user_error('group_not_in_location', {
                            'group': transf_event.animal_group.rec_name,
                            'from_location':
                                transf_event.from_location.rec_name,
                            'quantity': transf_event.quantity,
                            'timestamp': transf_event.timestamp,
                            })
            else:
                if not transf_event.animal.check_in_location(
                        transf_event.from_location,
                        transf_event.timestamp):
                    cls.raise_user_error('animal_not_in_location', {
                            'animal': transf_event.animal.rec_name,
                            'from_location':
                                transf_event.from_location.rec_name,
                            'timestamp': transf_event.timestamp,
                            })

            if transf_event.to_animal_type == 'group':
                if transf_event.to_animal_group:
                    transf_event.to_animal_group.check_allowed_location(
                        transf_event.to_location, transf_event.rec_name)
                else:
                    with Transaction().set_context(no_create_stock_move=True):
                        new_group = transf_event._get_to_animal_group()
                        new_group.save()
                        transf_event.to_animal_group = new_group
            else:
                with Transaction().set_context(no_create_stock_move=True):
                    new_animal = transf_event._get_to_animal()
                    new_animal.save()
                    transf_event.to_animal = new_animal

            new_in_move = transf_event._get_event_input_move()
            new_in_move.save()
            new_out_move = transf_event._get_event_output_move()
            new_out_move.save()
            todo_moves += [new_in_move, new_out_move]
            transf_event.in_move = new_in_move
            transf_event.out_move = new_out_move
            transf_event.save()
        Move.assign(todo_moves)
        Move.do(todo_moves)

        for transf_event in events:
            if transf_event.animal_type != 'group':
                animal = transf_event.animal
                animal.removal_date = transf_event.timestamp.date()
                # TODO: if it deactivates the animal the domain fails
                # TODO: set removal reason?
                #animal.active = False
                animal.save()
            else:
                animal_group = transf_event.animal_group

                to_remove = False
                storage_locations = Location.search([
                        ('type', '=', 'storage'),
                        ])
                with Transaction().set_context(
                        locations=[l.id for l in storage_locations],
                        stock_date_end=transf_event.timestamp.date()):
                    if animal_group.lot.quantity == 0:
                        to_remove = True

                if to_remove:
                    animal_group.removal_date = transf_event.timestamp.date()
                    # TODO: if it deactivates the group the domain fails
                    #animal_group.active = False
                    animal_group.save()

    def _get_to_animal_group(self):
        AnimalGroup = Pool().get('farm.animal.group')

        from_animal_or_group = self.animal or self.animal_group
        return AnimalGroup(
            specie=self.specie,
            breed=from_animal_or_group.breed,
            origin=from_animal_or_group.origin,
            arrival_date=from_animal_or_group.arrival_date,
            initial_location=self.to_location,
            initial_quantity=self.quantity,
            )

    def _get_to_animal(self):
        Animal = Pool().get('farm.animal')

        from_animal_or_group = self.animal or self.animal_group
        purpose = None
        if self.animal and self.to_animal_type == 'individual':
            purpose = self.animal.purpose
        return Animal(
            type=self.to_animal_type,
            specie=self.specie,
            breed=from_animal_or_group.breed,
            origin=from_animal_or_group.origin,
            arrival_date=from_animal_or_group.arrival_date,
            initial_location=self.to_location,
            birthdate=(self.animal and self.animal.birthdate),
            sex=(self.animal.sex if self.animal else 'undetermined'),
            purpose=purpose,
            )

    def _get_event_input_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        if self.animal_type == 'group':
            lot = self.animal_group.lot
        else:
            lot = self.animal.lot
        production_location = self.farm.production_location

        return Move(
            product=lot.product.id,
            uom=lot.product.default_uom.id,
            quantity=self.quantity,
            from_location=self.from_location.id,
            to_location=production_location.id,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=lot.id,
            origin=self,
            )

    def _get_event_output_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        if self.to_animal_type == 'group':
            lot = self.to_animal_group.lot
        else:
            lot = self.to_animal.lot

        production_location = self.farm.production_location

        return Move(
            product=lot.product.id,
            uom=lot.product.default_uom.id,
            quantity=self.quantity,
            from_location=production_location.id,
            to_location=self.to_location.id,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=lot,
            unit_price=lot.product.cost_price,
            origin=self,
            )

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'to_animal': None,
                'to_animal_group': None,
                'in_move': None,
                'out_move': None,
                })
        return super(TransformationEvent, cls).copy(records, default=default)

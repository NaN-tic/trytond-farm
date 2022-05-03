# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
"""
By now, the Weaning Event will only allow weaning the group of animals
    associated with the female.
No possibility of creating individuals from here. Maybe in the future we
    could consider several options:
- Farrowing creates individuals and weaning is for individuals
- Farrowing creates groups and weaning is for groups (current implementation)
- Farrowing creates groups and weaning is for individuals
"""
from trytond.model import fields, ModelView, ModelSQL, Workflow, Unique
from trytond.pyson import Eval, Id, If, Equal, Or
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, ImportedEventMixin, \
    _STATES_WRITE_DRAFT, _DEPENDS_WRITE_DRAFT, \
    _STATES_VALIDATED, _DEPENDS_VALIDATED

__all__ = ['WeaningEvent', 'WeaningEventFemaleCycle']

_INVISIBLE_NOT_GROUP = {
    'invisible': ~Equal(Eval('produced_animal_type'), 'group')
    }

_REQUIRED_IF_GROUP = {'required': Equal(Eval('produced_animal_type'), 'group')}


class WeaningEvent(AbstractEvent, ImportedEventMixin):
    '''Farm Weaning Event'''
    __name__ = 'farm.weaning.event'
    _table = 'farm_weaning_event'

    farrowing_group = fields.Function(fields.Many2One('farm.animal.group',
            'Farrowing Group', states=_INVISIBLE_NOT_GROUP,
            depends=['produced_animal_type']),
        'get_farrowing_group')
    farrowing_animals = fields.Function(fields.Many2Many('farm.animal', None,
        None, 'Farrowing Animals'), 'get_farrowing_animals')
    born_alive = fields.Function(fields.Integer('Born Alive'),
        'on_change_with_born_alive')
    quantity = fields.Integer('Quantity', required=True,
        states={**_STATES_WRITE_DRAFT, **_INVISIBLE_NOT_GROUP},
        depends=_DEPENDS_WRITE_DRAFT + ['produced_animal_type'])
    fostered = fields.Function(fields.Integer(
            'Fostered', states=_INVISIBLE_NOT_GROUP,
            depends=['produced_animal_type']),
        'on_change_with_fostered')
    last_minute_fostered = fields.Integer(
        'Last minute fostered',
        states={
            **_STATES_WRITE_DRAFT,
            **_INVISIBLE_NOT_GROUP,
            **_REQUIRED_IF_GROUP
            },
        depends=_DEPENDS_WRITE_DRAFT+['produced_animal_type'])
    casualties = fields.Function(fields.Integer(
            'Casualties', states=_INVISIBLE_NOT_GROUP,
            depends=['produced_animal_type']),
        'on_change_with_casualties')
    female_to_location = fields.Many2One('stock.location',
        'Female Destination', required=True, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ('warehouse', '=', Eval('farm')),
            ],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT + ['farm'])
    weaned_to_location = fields.Many2One('stock.location',
        'Weaned Destination', required=True, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ('warehouse', '=', Eval('farm')),
            ],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT + ['farm'])
    weaned_group = fields.Many2One('farm.animal.group', 'Weaned Group',
        domain=[
            ('farms', 'in', [Eval('farm', -1)]),
            ],
        states={**_STATES_WRITE_DRAFT, **_INVISIBLE_NOT_GROUP},
        depends=_DEPENDS_WRITE_DRAFT + ['farm', 'produced_animal_type'],
        help='Group in which weaned animals should be added to. If left blank '
        'they will keep the same group.')
    female_cycle = fields.One2One(
        'farm.weaning.event-farm.animal.female_cycle', 'event', 'cycle',
        string='Female Cycle', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    produced_animal_type = fields.Function(fields.Selection([
                ('individual', 'Individual'),
                ('group', 'Group'),
                ], 'Produced Animal Type'), 'on_change_with_produced_animal_type')
    weaned_animals = fields.One2Many(
        'farm.weaning.event-farm.animal',
        'event', 'Weaned Animals',
        domain=[
            ('specie', '=', Eval('specie')),
            ('animal', 'in', Eval('farrowing_animals')),
            ],
        states={
            'invisible':  ~Equal(Eval('produced_animal_type'), 'individual'),
            }, readonly=True,
        depends=['produced_animal_type', 'specie', 'farrowing_animals'])
    female_move = fields.Many2One('stock.move', 'Female Stock Move',
        readonly=True, domain=[
            ('lot', '=', Eval('lot')),
            ],
        states={
            'invisible': ~Eval('context', {}).get('groups', []).contains(
                    Id('farm', 'group_farm_admin')),
            },
        depends=['lot'])
    lost_move = fields.Many2One('stock.move', 'Lost Stock Move',
        readonly=True, domain=[
            ('lot.animal_group', '=', Eval('farrowing_group', 0)),
            ],
        states={
            'invisible': Or((~Eval('context', {}).get('groups', []).contains(
                    Id('farm', 'group_farm_admin'))),
                    (~Equal(Eval('produced_animal_type'), 'group'))),
            },
        depends=['farrowing_group', 'produced_animal_type'])
    weaned_move = fields.Many2One('stock.move', 'Weaned Stock Move',
        readonly=True, domain=[
            ('lot.animal_group', '=', Eval('farrowing_group', 0)),
            ],
        states={
            'invisible': Or(
                (~Eval('context', {}).get('groups', []).contains(
                    Id('farm', 'group_farm_admin'))),
                (~Equal(Eval('produced_animal_type'), 'group'))),
            },
        depends=['farrowing_group', 'produced_animal_type'])
    transformation_event = fields.Many2One('farm.transformation.event',
        'Transformation Event', readonly=True, states={
            'invisible': ~Eval('context', {}).get('groups', []).contains(
                    Id('farm', 'group_farm_admin')),
            })

    # TODO: Extra 'weight': fields.float('Weight'),

    @classmethod
    def __setup__(cls):
        super(WeaningEvent, cls).__setup__()
        cls.animal.domain += [
            ('farm', '=', Eval('farm')),
            ('location.type', '=', 'storage'),
            ('type', '=', 'female'),
            If(~Eval('imported', True),
                ('current_cycle', '!=', None),
                ()),
            ]
        if 'farm' not in cls.animal.depends:
            cls.animal.depends.add('farm')
        if 'imported' not in cls.animal.depends:
            cls.animal.depends.add('imported')
        # TODO: not added constraint for non negative quantity but negative
        # quantities are not suported

    @staticmethod
    def default_animal_type():
        return 'female'

    @staticmethod
    def default_last_minute_fostered():
        return 0

    @staticmethod
    def valid_animal_types():
        return ['female']

    def get_rec_name(self, name):
        cycle = (self.female_cycle and self.female_cycle.sequence or
            self.animal.current_cycle and self.animal.current_cycle.sequence
            or None)
        if cycle:
            return "%s on cycle %s %s" % (self.animal.rec_name, cycle,
                self.timestamp)
        return super(WeaningEvent, self).get_rec_name(name)

    @fields.depends('specie')
    def on_change_with_produced_animal_type(self, name=None):
        if self.specie and self.specie.produced_animal_type:
            return self.specie.produced_animal_type

    def get_farrowing_group(self, name=None):
        '''
        Return the farm.animal.group produced on Farrowing Event of this event
        cycle
        '''
        farrowing_event = (self.female_cycle and
            self.female_cycle.farrowing_event or
            self.animal.current_cycle.farrowing_event)
        if (farrowing_event and farrowing_event.state == 'validated' and
                farrowing_event.produced_group):
            return farrowing_event.produced_group.id
        return None

    def get_farrowing_animals(self, name=None):
        '''
        Return the farm.animals produced on Farrowing Event of this event
        cycle
        '''
        farrowing_event = (self.female_cycle and
            self.female_cycle.farrowing_event or
            self.animal.current_cycle.farrowing_event)
        if (farrowing_event and farrowing_event.state == 'validated' and
                farrowing_event.produced_animals):
            return [a.animal.id for a in farrowing_event.produced_animals]

    @fields.depends('animal', 'farrowing_group', 'timestamp', 'quantity')
    def on_change_with_quantity(self):
        if not self.animal or not self.farrowing_group:
            return self.quantity
        with Transaction().set_context(
                locations=[self.animal.location.id],
                stock_date_end=self.timestamp.date()):
            quantity = self.farrowing_group.lot.quantity
        return quantity or None

    @fields.depends('born_alive', 'quantity', 'fostered',
        'last_minute_fostered')
    def on_change_with_casualties(self, name=None):
        return ((self.born_alive or 0) + (self.fostered or 0) +
            (self.last_minute_fostered or 0) - (self.quantity or 0))

    @fields.depends('animal')
    def on_change_with_fostered(self, name=None):
        'Returns the sum of foster event quantity for the current farrowing '
        'group. Used to display and check'
        if self.animal:
            current_cycle = self.animal.current_cycle
            return current_cycle.fostered or 0

    @fields.depends('animal')
    def on_change_with_born_alive(self, name=None):
        'Returns the number of alive in the current farrowing event. Used to '
        'display and check'
        if self.animal:
            current_cycle = self.animal.current_cycle
            return current_cycle.live or 0

    @fields.depends('animal', 'weaned_animals', 'farrowing_animals')
    def on_change_animal(self):
        if not self.animal:
            return
        super(WeaningEvent, self).on_change_animal()
        current_cycle = self.animal.current_cycle
        self.female_cycle = current_cycle
        self.quantity = current_cycle.live + current_cycle.fostered
        self.last_minute_fostered = 0
        if not self.get_farrowing_group():
            self.farrowing_group = None

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Allow the event only if the female has an open cycle and it's in the
            state of 'lactating'.
        Create stock move for the female:
        What: animal_id, From: animal's location, To: female_location_dest

        Create a production move with:
            What: animal_id.last_produced_group_id,
                From: animal's location, To: production location
            What: weaned_group_id.production_lot_id, Qty: 'quantity' value,
                From: production location, To: weaned_location_dest
            What: animal_id.last_produced_group_id, Qty: difference between
                the stock of produced group and number of weaned ('quantity')
                FROM: production location, To: specie_id.lost_found_location_id
        """
        pool = Pool()
        Move = pool.get('stock.move')
        TransformationEvent = pool.get('farm.transformation.event')
        AnimalMove = pool.get('farm.weaning.event-farm.animal')
        todo_moves = []
        todo_trans_events = []
        for weaning_event in events:
            assert (not weaning_event.female_move and
                not weaning_event.weaned_move), ('Weaning Event %s already '
                'has related stock moves when it is to validate.'
                % weaning_event.id)

            current_cycle = weaning_event.animal.current_cycle
            weaning_event.female_cycle = current_cycle
            maximum = (current_cycle.live + current_cycle.fostered +
                weaning_event.last_minute_fostered)
            if weaning_event.quantity > maximum:
                raise UserError(gettext('farm.incorrect_quantity',
                        quantity=maximum))

            if (weaning_event.female_to_location and
                    weaning_event.female_to_location !=
                    weaning_event.animal.location):
                weaning_event.animal.check_allowed_location(
                    weaning_event.female_to_location, weaning_event.rec_name)

                female_move = weaning_event._get_female_move()
                female_move.save()
                weaning_event.female_move = female_move
                todo_moves.append(female_move)

            if weaning_event.casualties != 0:
                lost_move = weaning_event._get_lost_move(
                    weaning_event.casualties)
                lost_move.save()
                weaning_event.lost_move = lost_move
                todo_moves.append(lost_move)

            if weaning_event.last_minute_fostered !=0:
                last_minute_fostered_move = (
                    weaning_event._get_last_minute_fostered_move(
                        weaning_event.last_minute_fostered))
                last_minute_fostered_move.save()
                todo_moves.append(last_minute_fostered_move)

            if weaning_event.produced_animal_type == 'individual':
                to_save = []

                for animal in weaning_event.farrowing_animals:
                    animalMove = AnimalMove()
                    animalMove.event = weaning_event
                    animalMove.animal = animal
                    to_save.append(animalMove)
                AnimalMove.save(to_save)

            if (weaning_event.quantity and weaning_event.weaned_group and
                    weaning_event.weaned_group !=
                    weaning_event.farrowing_group):
                transformation_event = (
                    weaning_event._get_transformation_event())
                transformation_event.save()
                weaning_event.transformation_event = transformation_event
                todo_trans_events.append(transformation_event)
            elif (weaning_event.quantity and weaning_event.animal.location !=
                    weaning_event.weaned_to_location):
                # same group but different locations
                if weaning_event.produced_animal_type == 'individual':
                    for animalMove in weaning_event.weaned_animals:
                        animal = animalMove.animal
                        animal.check_allowed_location(
                            weaning_event.weaned_to_location,
                            weaning_event.rec_name)
                        move = weaning_event._get_weaned_move(animal)
                        move.save()
                        animalMove.move = move
                        animalMove.save()
                        todo_moves.append(move)
                else:
                    weaning_event.farrowing_group.check_allowed_location(
                        weaning_event.weaned_to_location,
                        weaning_event.rec_name)
                    weaned_move = weaning_event._get_weaned_move()
                    weaned_move.save()

                    weaning_event.weaned_move = weaned_move
                    todo_moves.append(weaned_move)
            if weaning_event.produced_animal_type == 'individual':
                for animal in weaning_event.weaned_animals:
                    cost_line = (
                        weaning_event._get_weaning_animal_cost_line(
                            animal.animal))
                    if cost_line:
                        cost_line.save()
            else:
                cost_line = weaning_event._get_weaning_cost_line()
                if cost_line:
                    cost_line.save()

            weaning_event.save()
            current_cycle.update_state(weaning_event)
        if todo_moves:
            Move.assign(todo_moves)
            Move.do(todo_moves)
        if todo_trans_events:
            with Transaction().set_context(create_cost_lines=False):
                TransformationEvent.validate_event(todo_trans_events)

    def _get_female_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
        return Move(
            product=self.lot.product,
            uom=self.lot.product.default_uom,
            quantity=1.0,
            from_location=self.animal.location,
            to_location=self.female_to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.lot,
            origin=self)

    def _get_last_minute_fostered_move(self, last_minute_fostered):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
        if last_minute_fostered < 0:
            from_location = self.animal.location
            to_location = self.specie.foster_location
        else:
            # recover lost units
            from_location = self.specie.foster_location
            to_location = self.animal.location

        if not self.farrowing_group:
            raise UserError(gettext('farm.not_farrowing_group', event=self))
        return Move(
            product=self.farrowing_group.lot.product,
            uom=self.farrowing_group.lot.product.default_uom,
            quantity=abs(last_minute_fostered),
            from_location=from_location,
            to_location=to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.farrowing_group.lot,
            origin=self)

    def _get_lost_move(self, lost_qty):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
        if lost_qty > 0:
            from_location = self.animal.location
            to_location = self.specie.lost_found_location
        else:
            # recover lost units
            from_location = self.specie.lost_found_location
            to_location = self.animal.location
        if not self.farrowing_group:
            raise UserError(gettext('farm.not_farrowing_group', event=self))
        return Move(
            product=self.farrowing_group.lot.product,
            uom=self.farrowing_group.lot.product.default_uom,
            quantity=abs(lost_qty),
            from_location=from_location,
            to_location=to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.farrowing_group.lot,
            origin=self)

    def _get_weaning_animal_cost_line(self, animal):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('farm', 'cost_category_weaning_cost')

        if (animal.lot and animal.lot.product.template.weaning_price and
                animal.lot.product.template.weaning_price !=
                animal.lot.cost_price):
            cost_line = LotCostLine()
            cost_line.lot = animal.lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = (animal.lot.product.template.weaning_price -
                animal.lot.cost_price)
            return cost_line

    def _get_weaning_cost_line(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('farm', 'cost_category_weaning_cost')
        group = (self.weaned_group if self.weaned_group
            else self.farrowing_group)
        if not group:
            raise UserError(gettext('farm.not_farrowing_group', event=self))
        if (group.lot and group.lot.product.template.weaning_price and
                group.lot.product.template.weaning_price !=
                group.lot.cost_price):
            cost_line = LotCostLine()
            cost_line.lot = group.lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = (group.lot.product.template.weaning_price -
                group.lot.cost_price)
            return cost_line

    def _get_weaned_move(self, animal=None):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
        if animal:
            return Move(
                product=animal.lot.product,
                uom=animal.lot.product.default_uom,
                quantity=1,
                from_location=self.animal.location,
                to_location=self.weaned_to_location,
                planned_date=self.timestamp.date(),
                effective_date=self.timestamp.date(),
                company=context.get('company'),
                lot=animal.lot,
                origin=self)
        else:
            if not self.farrowing_group:
                raise UserError(gettext('farm.not_farrowing_group', event=self))
            return Move(
                product=self.farrowing_group.lot.product,
                uom=self.farrowing_group.lot.product.default_uom,
                quantity=self.quantity,
                from_location=self.animal.location,
                to_location=self.weaned_to_location,
                planned_date=self.timestamp.date(),
                effective_date=self.timestamp.date(),
                company=context.get('company'),
                lot=self.farrowing_group.lot,
                origin=self)

    def _get_transformation_event(self):
        TransformationEvent = Pool().get('farm.transformation.event')
        return TransformationEvent(
            animal_type='group',
            specie=self.specie,
            farm=self.farm,
            timestamp=self.timestamp,
            animal_group=self.farrowing_group,
            from_location=self.animal.location,
            to_animal_type='group',
            to_location=self.weaned_to_location,
            quantity=self.quantity,
            to_animal_group=self.weaned_group)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'weaned_group': None,
                'female_cycle': None,
                'female_move': None,
                'lost_move': None,
                'weaned_move': None,
                'transformation_event': None,
                })
        return super(WeaningEvent, cls).copy(records, default=default)


class WeaningEventFemaleCycle(ModelSQL):
    "Weaning Event - Female Cycle"
    __name__ = 'farm.weaning.event-farm.animal.female_cycle'

    event = fields.Many2One('farm.weaning.event', 'Weaning Event',
        required=True, ondelete='RESTRICT')
    cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        required=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(WeaningEventFemaleCycle, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('event_unique', Unique(t, t.event), 'farm.weaning_event_unique'),
            ('cycle_unique', Unique(t, t.cycle), 'farm.weaning_cycle_unique'),
            ]


class WeaningEventAnimal(ModelSQL, ModelView):
    "Weaning Event - Animal"
    __name__ = 'farm.weaning.event-farm.animal'

    event = fields.Many2One('farm.weaning.event', 'Weaning Event',
        required=True, ondelete='RESTRICT')
    animal = fields.Many2One('farm.animal', 'Animal',
        required=True, ondelete='RESTRICT')
    specie = fields.Function(
        fields.Many2One('farm.specie', 'Specie'), 'get_specie',
        searcher='search_specie')
    move = fields.Many2One('stock.move', 'Move', ondelete='RESTRICT')

    def get_specie(self):
        if self.animal and self.animal.specie:
            return self.animal.specie

    @classmethod
    def search_specie(cls, name, clause):
        return [('animal.specie',) + tuple(clause[1:])]

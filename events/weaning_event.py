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
from trytond.model import fields, ModelView, ModelSQL, Workflow
from trytond.pyson import Equal, Eval, Id, If, Not
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, ImportedEventMixin, \
    _STATES_WRITE_DRAFT, _DEPENDS_WRITE_DRAFT, \
    _STATES_VALIDATED, _DEPENDS_VALIDATED

__all__ = ['WeaningEvent', 'WeaningEventFemaleCycle']


class WeaningEvent(AbstractEvent, ImportedEventMixin):
    '''Farm Weaning Event'''
    __name__ = 'farm.weaning.event'
    _table = 'farm_weaning_event'

    farrowing_group = fields.Function(fields.Many2One('farm.animal.group',
            'Farrowing Group'),
        'get_farrowing_group')
    quantity = fields.Integer('Quantity', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
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
            ('farms', 'in', [Eval('farm')]),
            ],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT + ['farm'],
        help='Group in which weaned animals should be added to. If left blank '
        'they will keep the same group.')
    female_cycle = fields.One2One(
        'farm.weaning.event-farm.animal.female_cycle', 'event', 'cycle',
        string='Female Cycle', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    female_move = fields.Many2One('stock.move', 'Female Stock Move',
        readonly=True, domain=[
            ('lot', '=', Eval('lot')),
            ],
        states={
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            },
        depends=['lot'])
    lost_move = fields.Many2One('stock.move', 'Lost Stock Move',
        readonly=True, domain=[
            ('lot.animal_group', '=', Eval('farrowing_group', 0)),
            ],
        states={
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            },
        depends=['farrowing_group'])
    weaned_move = fields.Many2One('stock.move', 'Weaned Stock Move',
        readonly=True, domain=[
            ('lot.animal_group', '=', Eval('farrowing_group', 0)),
            ],
        states={
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            },
        depends=['farrowing_group'])
    transformation_event = fields.Many2One('farm.transformation.event',
        'Transformation Event', readonly=True, states={
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            })

    # TODO: Extra 'weight': fields.float('Weight'),

    @classmethod
    def __setup__(cls):
        super(WeaningEvent, cls).__setup__()
        cls._error_messages.update({
            'incorrect_quantity': 'The entered quantity is incorrect, '
            'the maximum allowed quantity is: %s'
            })
        cls.animal.domain += [
            ('farm', '=', Eval('farm')),
            ('location.type', '=', 'storage'),
            ('type', '=', 'female'),
            If(~Eval('imported', True),
                ('current_cycle', '!=', None),
                ()),
            If(Equal(Eval('state'), 'draft') & ~Eval('imported', True),
                ('current_cycle.state', '=', 'lactating'),
                ()),
            ]
        if 'farm' not in cls.animal.depends:
            cls.animal.depends.append('farm')
        if 'imported' not in cls.animal.depends:
            cls.animal.depends.append('imported')
        # TODO: not added constraint for non negative quantity but negative
        # quantities are not suported

    @staticmethod
    def default_animal_type():
        return 'female'

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

    def get_farrowing_group(self, name):
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

    @fields.depends('animal', 'farrowing_group', 'timestamp')
    def on_change_with_quantity(self):
        if not self.animal or not self.farrowing_group:
            return None
        with Transaction().set_context(
                locations=[self.animal.location.id],
                stock_date_end=self.timestamp.date()):
            quantity = self.farrowing_group.lot.quantity
        return quantity or None

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
        todo_moves = []
        todo_trans_events = []
        for weaning_event in events:
            assert (not weaning_event.female_move and
                not weaning_event.weaned_move), ('Weaning Event %s already '
                'has related stock moves when it is to validate.'
                % weaning_event.id)

            current_cycle = weaning_event.animal.current_cycle
            weaning_event.female_cycle = current_cycle
            if weaning_event.quantity > current_cycle.live:
                cls.raise_user_error('incorrect_quantity',
                    current_cycle.live)

            if (weaning_event.female_to_location and
                    weaning_event.female_to_location !=
                    weaning_event.animal.location):
                weaning_event.animal.check_allowed_location(
                    weaning_event.female_to_location, weaning_event.rec_name)

                female_move = weaning_event._get_female_move()
                female_move.save()
                weaning_event.female_move = female_move
                todo_moves.append(female_move)

            farrowing_group_lot = weaning_event.farrowing_group.lot
            with Transaction().set_context(
                    product=farrowing_group_lot.product.id,
                    locations=[weaning_event.animal.location.id],
                    stock_date_end=weaning_event.timestamp.date()):
                farrowing_group_qty = farrowing_group_lot.quantity
            lost_qty = farrowing_group_qty - weaning_event.quantity

            if lost_qty != 0:
                # put in 'animal.location' exactly 'quantity' units of
                # farrowing_group
                lost_move = weaning_event._get_lost_move(lost_qty)
                lost_move.save()
                weaning_event.lost_move = lost_move
                todo_moves.append(lost_move)

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
                weaning_event.farrowing_group.check_allowed_location(
                    weaning_event.weaned_to_location, weaning_event.rec_name)

                weaned_move = weaning_event._get_weaned_move()
                weaned_move.save()
                weaning_event.weaned_move = weaned_move
                todo_moves.append(weaned_move)

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

    def _get_weaning_cost_line(self):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('farm', 'cost_category_weaning_cost')
        group = (self.weaned_group if self.weaned_group
            else self.farrowing_group)
        if (group.lot and group.lot.product.weaning_price and
                group.lot.product.weaning_price != group.lot.cost_price):
            cost_line = LotCostLine()
            cost_line.lot = group.lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = (group.lot.product.weaning_price -
                group.lot.cost_price)
            return cost_line

    def _get_weaned_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
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
        cls._sql_constraints += [
            ('event_unique', 'UNIQUE(event)',
                'The Weaning Event must be unique.'),
            ('cycle_unique', 'UNIQUE(cycle)',
                'The Female Cycle must be unique.'),
            ]

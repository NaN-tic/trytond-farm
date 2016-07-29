# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelView, ModelSQL, Workflow
from trytond.pyson import And, Bool, Equal, Eval, Id, If, Not
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, ImportedEventMixin, \
    _STATES_WRITE_DRAFT, _DEPENDS_WRITE_DRAFT, \
    _STATES_VALIDATED, _DEPENDS_VALIDATED

__all__ = ['FarrowingProblem', 'FarrowingEvent', 'FarrowingEventFemaleCycle',
    'FarrowingEventAnimalGroup']


class FarrowingProblem(ModelSQL, ModelView):
    '''Farrowing Event Problem'''
    __name__ = 'farm.farrowing.problem'
    _order_name = 'name'

    name = fields.Char('Name', required=True, translate=True)


class FarrowingEvent(AbstractEvent, ImportedEventMixin):
    '''Farm Farrowing Event'''
    __name__ = 'farm.farrowing.event'
    _table = 'farm_farrowing_event'

    live = fields.Integer('Live', states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT)
    stillborn = fields.Integer('Stillborn', states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT)
    mummified = fields.Integer('Mummified', states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT)
    dead = fields.Function(fields.Integer('Dead'),
        'on_change_with_dead')
    problem = fields.Many2One('farm.farrowing.problem', 'Problem',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    female_cycle = fields.One2One(
        'farm.farrowing.event-farm.animal.female_cycle', 'event', 'cycle',
        string='Female Cycle', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    produced_group = fields.One2One('farm.farrowing.event-farm.animal.group',
        'event', 'animal_group', string='Produced Group', domain=[
            ('specie', '=', Eval('specie')),
            ('initial_quantity', '=', Eval('live')),
            ], readonly=True,
        states={
            'required': And(And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('live', 0))), Not(Eval('imported', False))),
            },
        depends=['specie', 'live', 'state', 'imported'])
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True, domain=[
            ('lot.animal_group', '=', Eval('produced_group')),
            ],
        states={
            'required': And(And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('live', 0))), Not(Eval('imported', False))),
            'invisible': Not(Eval('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            },
        depends=['produced_group', 'live', 'state', 'imported'])

    @classmethod
    def __setup__(cls):
        super(FarrowingEvent, cls).__setup__()
        cls.animal.domain += [
            ('type', '=', 'female'),
            If(~Eval('imported', True),
                ('current_cycle', '!=', None),
                ()),
            If(Equal(Eval('state'), 'draft') & ~Eval('imported', True),
                ('current_cycle.state', '=', 'pregnant'),
                ()),
            ]
        if 'imported' not in cls.animal.depends:
            cls.animal.depends.append('imported')
        cls._error_messages.update({
                'event_without_dead_nor_live': ('The farrowing event "%s" has '
                    '0 in Dead and Live. It has to have some unit in some of '
                    'these fields.'),
                })
        cls._sql_constraints += [
            ('live_not_negative', 'CHECK(live >= 0)',
                'The value of "Live" must to be positive.'),
            ('stillborn_not_negative', 'CHECK(stillborn >= 0)',
                'The value of "Stillborn" must to be positive.'),
            ('mummified_not_negative', 'CHECK(mummified >= 0)',
                'The value of "Mummified" must to be positive.'),
            ]
        cls._buttons['validate_event']['readonly'] = And(
            Equal(Eval('live', 0), 0),
            Equal(Eval('dead', 0), 0))

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
        return super(FarrowingEvent, self).get_rec_name(name)

    @fields.depends('stillborn', 'mummified')
    def on_change_with_dead(self, name=None):
        return (self.stillborn or 0) + (self.mummified or 0)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        Move = Pool().get('stock.move')
        todo_moves = []
        for farrowing_event in events:
            if farrowing_event.dead == 0 and farrowing_event.live == 0:
                cls.raise_user_error('event_without_dead_nor_live',
                    farrowing_event.rec_name)
            current_cycle = farrowing_event.animal.current_cycle
            farrowing_event.female_cycle = current_cycle

            if farrowing_event.live != 0:
                with Transaction().set_context(
                        no_create_stock_move=True,
                        create_cost_lines=False):
                    produced_group = farrowing_event._get_produced_group()
                    produced_group.save()
                farrowing_event.produced_group = produced_group

                move = farrowing_event._get_event_move()
                move.save()
                farrowing_event.move = move
                todo_moves.append(move)

            farrowing_event.save()
            current_cycle.update_state(farrowing_event)
        Move.assign(todo_moves)
        Move.do(todo_moves)

    def _get_produced_group(self):
        """
        Prepare values to create the produced group in female's farrowing
        """
        AnimalGroup = Pool().get('farm.animal.group')
        return AnimalGroup(
            specie=self.specie,
            breed=self.animal.breed,
            initial_location=self.animal.location,
            initial_quantity=self.live,
            origin='raised')

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('farm', 'cost_category_farrowing_cost')
        context = Transaction().context

        lot = self.produced_group.lot

        if lot and lot.product.template.farrowing_price:
            if lot.cost_lines:
                cost_line = lot.cost_lines[0]
            else:
                cost_line = LotCostLine()
                cost_line.lot = self.produced_group.lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = lot.product.template.farrowing_price
            cost_line.save()

        return Move(
            product=self.specie.group_product.id,
            uom=self.specie.group_product.default_uom.id,
            quantity=self.live,
            from_location=self.farm.production_location.id,
            to_location=self.animal.location.id,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.produced_group.lot.id,
            unit_price=self.produced_group.lot.product.cost_price,
            origin=self)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'female_cycle': None,
                'produced_group': None,
                'move': None,
                })
        return super(FarrowingEvent, cls).copy(records, default=default)


class FarrowingEventFemaleCycle(ModelSQL):
    "Farrowing Event - Female Cycle"
    __name__ = 'farm.farrowing.event-farm.animal.female_cycle'

    event = fields.Many2One('farm.farrowing.event', 'Farrowing Event',
        required=True, ondelete='RESTRICT')
    cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        required=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(FarrowingEventFemaleCycle, cls).__setup__()
        cls._sql_constraints += [
            ('event_unique', 'UNIQUE(event)',
                'The Farrowing Event must be unique.'),
            ('cycle_unique', 'UNIQUE(cycle)',
                'The Female Cycle must be unique.'),
            ]


class FarrowingEventAnimalGroup(ModelSQL):
    "Farrowing Event - AnimalGroup"
    __name__ = 'farm.farrowing.event-farm.animal.group'

    event = fields.Many2One('farm.farrowing.event', 'Farrowing Event',
        required=True, ondelete='RESTRICT')
    animal_group = fields.Many2One('farm.animal.group', 'Group', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(FarrowingEventAnimalGroup, cls).__setup__()
        cls._sql_constraints += [
            ('event_unique', 'UNIQUE(event)',
                'The Farrowing Event must be unique.'),
            ('animal_group_unique', 'UNIQUE(animal_group)',
                'The Animal Group must be unique.'),
            ]

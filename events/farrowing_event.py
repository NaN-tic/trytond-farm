# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.model import fields, ModelView, ModelSQL, Workflow, Check, Unique
from trytond.pyson import And, Bool, Equal, Eval, Id, If, Not, Or
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, ImportedEventMixin, \
    _STATES_WRITE_DRAFT, _DEPENDS_WRITE_DRAFT, \
    _STATES_VALIDATED, _DEPENDS_VALIDATED

__all__ = ['FarrowingProblem', 'FarrowingEvent', 'FarrowingEventFemaleCycle',
    'FarrowingEventAnimalGroup']


_INVISIBLE_NOT_GROUP = {
    'invisible': ~Equal(Eval('produced_animal_type'), 'group')}


class FarrowingProblem(ModelSQL, ModelView):
    '''Farrowing Event Problem'''
    __name__ = 'farm.farrowing.problem'
    _order_name = 'name'

    name = fields.Char('Name', required=True, translate=True)


class FarrowingEvent(AbstractEvent, ImportedEventMixin, ModelSQL, ModelView, Workflow):
    '''Farm Farrowing Event'''
    __name__ = 'farm.farrowing.event'
    _table = 'farm_farrowing_event'

    live = fields.Integer('Live', states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT)
    stillborn = fields.Integer(
        'Stillborn', states={**_STATES_WRITE_DRAFT,**_INVISIBLE_NOT_GROUP},
        depends=_DEPENDS_WRITE_DRAFT)
    mummified = fields.Integer(
        'Mummified', states={**_STATES_WRITE_DRAFT,**_INVISIBLE_NOT_GROUP},
        depends=_DEPENDS_WRITE_DRAFT)
    dead = fields.Function(fields.Integer('Dead', states={
            'invisible': ~Equal(Eval('produced_animal_type'), 'group')
        }), 'on_change_with_dead')
    problem = fields.Many2One('farm.farrowing.problem', 'Problem',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    female_cycle = fields.One2One(
        'farm.farrowing.event-farm.animal.female_cycle', 'event', 'cycle',
        string='Female Cycle', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    produced_animal_type = fields.Function(fields.Selection([
                ('individual', 'Individual'),
                ('group', 'Group'),
                ], 'Produced Animal Type'), 'get_produced_animal_type')
    produced_animals = fields.One2Many('farm.farrowing.event-farm.animal',
        'event', 'Produced Animals', readonly=True, domain=[
            ('specie', '=', Eval('specie')),
            ],
        states={
            'required': And(And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('live', 0))), Not(Eval('imported', False)),
                    Equal(Eval('produced_animal_type'), 'individual')),
            'invisible':  ~Equal(Eval('produced_animal_type'), 'individual')
            },
        depends=['specie', 'live', 'state', 'imported', 'produced_animal_type'])
    produced_group = fields.One2One('farm.farrowing.event-farm.animal.group',
        'event', 'animal_group', string='Produced Group', domain=[
            ('specie', '=', Eval('specie')),
            ('initial_quantity', '=', Eval('live')),
            ], readonly=True,
        states={
            'required': And(And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('live', 0))), Not(Eval('imported', False)),
                    Equal(Eval('produced_animal_type'), 'group')),
            'invisible': ~Equal(Eval('produced_animal_type'), 'group')
            },
        depends=['specie', 'live', 'state', 'imported', 'produced_animal_type'])
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True, domain=[
                ('lot.animal_group', '=', Eval('produced_group')),
            ],
        states={
            'required': And(And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('live', 0))), Not(Eval('imported', False)),
                    Equal(Eval('produced_animal_type'), 'group')),
            'invisible': Or(~Eval('context', {}).get('groups', []).contains(
                    Id('farm', 'group_farm_admin')),
                    ~Equal(Eval('produced_animal_type'), 'group')),
            },
        depends=['produced_group', 'live', 'state', 'imported',
            'produced_animal_type'])

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
        t = cls.__table__()
        cls._sql_constraints += [
            ('live_not_negative', Check(t, t.live >= 0),
                'farm.check_farrowing_live_positive'),
            ('stillborn_not_negative', Check(t, t.stillborn >= 0),
                'farm.check_farrowing_stillborn_positive'),
            ('mummified_not_negative', Check(t, t.mummified >= 0),
                'farm.check_farrowing_mummified_positive'),
            ]
        cls._buttons['validate_event']['readonly'] = And(
            Equal(Eval('live', 0), 0),
            Equal(Eval('dead', 0), 0))
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    },
                })

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

    @fields.depends('animal_type', 'animal', 'produced_animal_type')
    def on_change_animal(self):
        if not self.animal:
            return
        super(FarrowingEvent, self).on_change_animal()
        self.female_cycle = self.animal.current_cycle
        if self.produced_animal_type == 'individual':
            self.live = 1

    def get_produced_animal_type(self, name):
        if self.specie.produced_animal_type:
            return self.specie.produced_animal_type


    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        pool = Pool()
        Move = pool.get('stock.move')
        EventAnimal = pool.get('farm.farrowing.event-farm.animal')
        todo_moves = []
        for farrowing_event in events:
            if farrowing_event.dead == 0 and farrowing_event.live == 0:
                raise UserError(gettext('farm.event_without_dead_nor_live',
                    event=farrowing_event.rec_name))
            current_cycle = farrowing_event.animal.current_cycle
            farrowing_event.female_cycle = current_cycle

            if farrowing_event.live != 0:
                with Transaction().set_context(
                        no_create_stock_move=True,
                        create_cost_lines=False):
                    if farrowing_event.produced_animal_type == 'individual':
                        for i in range(farrowing_event.live):
                            produced_animal = farrowing_event._get_produced_animal()
                            produced_animal.save()
                            move = farrowing_event._get_event_move(produced_animal)
                            move.save()
                            todo_moves.append(move)
                            eventAnimal = EventAnimal()
                            eventAnimal.animal = produced_animal
                            eventAnimal.event = farrowing_event
                            eventAnimal.move = move
                            eventAnimal.save()
                    else:
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

    def _get_produced_animal(self):
        """
        Prepare values to create the produced animal in female's farrowing
        """
        Animal = Pool().get('farm.animal')
        return Animal(
            specie=self.specie,
            breed=self.animal.breed,
            initial_location=self.animal.location,
            type='individual',
            origin='raised')

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

    def _get_event_move(self, animal=None):
        pool = Pool()
        Move = pool.get('stock.move')
        ModelData = pool.get('ir.model.data')
        LotCostLine = pool.get('stock.lot.cost_line')
        category_id = ModelData.get_id('farm', 'cost_category_farrowing_cost')
        context = Transaction().context

        if self.produced_animal_type == 'individual':
            lot = animal.lot
            live = 1
            product = self.specie.individual_product.id
            uom = self.specie.individual_product.default_uom.id
        else:
            lot = self.produced_group.lot
            product = self.specie.group_product.id
            uom = self.specie.group_product.default_uom.id
            live = self.live

        if lot and lot.product.template.farrowing_price:
            if lot.cost_lines:
                cost_line = lot.cost_lines[0]
            else:
                cost_line = LotCostLine()
                cost_line.lot = lot
            cost_line.category = category_id
            cost_line.origin = str(self)
            cost_line.unit_price = lot.product.template.farrowing_price
            cost_line.save()

        return Move(
            product=product,
            uom=uom,
            quantity=live,
            from_location=self.farm.production_location.id,
            to_location=self.animal.location.id,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=lot.id,
            unit_price=lot.product.cost_price,
            origin=self)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'female_cycle': None,
                'produced_animal': None,
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
        t = cls.__table__()
        cls._sql_constraints += [
            ('event_unique', Unique(t, t.event),
                'farm.farrowing_event_unique'),
            ('cycle_unique', Unique(t, t.cycle),
                'farm.farrowing_cycle_unique'),
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
        t = cls.__table__()
        cls._sql_constraints += [
            ('event_unique', Unique(t, t.event),
                'farm.farrowing_event_unique'),
            ('animal_group_unique', Unique(t, t.animal_group),
                'farm.farrowing_animal_group_unique'),
            ]


class FarmFarrowingEventAnimal(ModelSQL, ModelView):
    'Farrowing Event - Animal'
    __name__ = 'farm.farrowing.event-farm.animal'

    event = fields.Many2One('farm.farrowing.event', 'Farrowing Event',
        required=True, ondelete='RESTRICT')
    animal = fields.Many2One('farm.animal', 'Animal', required=True,
        ondelete='RESTRICT')
    move = fields.Many2One('stock.move', 'Move', required=True,
        ondelete='RESTRICT')
    specie = fields.Function(
        fields.Many2One('farm.specie', 'Specie'), 'get_specie',
        searcher='search_specie')

    def get_specie(self):
        if self.animal and self.animal.specie:
            return self.animal.specie

    @classmethod
    def search_specie(cls, name, clause):
        return [('animal.specie',) + tuple(clause[1:])]
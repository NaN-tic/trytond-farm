#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import And, Bool, Equal, Eval, If
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED, _DEPENDS_VALIDATED, \
    _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN

__all__ = ['FosterEvent']


class FosterEvent(AbstractEvent):
    '''Farm Foster Event'''
    __name__ = 'farm.foster.event'
    _table = 'farm_foster_event'

    farrowing_group = fields.Function(fields.Many2One('farm.animal.group',
            'Farrowing Group'),
        'get_farrowing_group')
    quantity = fields.Integer('Fosters',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT,
        help='If this quantity is negative it is a Foster Out.')
    pair_female = fields.Many2One('farm.animal', 'Pair Female', domain=[
            ('specie', '=', Eval('specie')),
            ('type', '=', 'female'),
            ('farm', '=', Eval('farm')),
            ('id', '!=', Eval('animal')),
            ('current_cycle', '!=', None),
            If(Equal(Eval('state'), 'draft'),
                ('current_cycle.state', '=', 'lactating'),
                ()),
            ], states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['specie', 'farm', 'animal'])
    pair_event = fields.Many2One('farm.foster.event', 'Pair Foster Event',
        readonly=True, domain=[
            ('animal', '=', Eval('pair_female')),
            ('id', '!=', Eval('id')),
            ],
        states={
            'required': And(Equal(Eval('state'), 'validated'),
                    Bool(Eval('pair_female', 0))),
            }, depends=['pair_female', 'id', 'state'])
    female_cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN, depends=_DEPENDS_VALIDATED_ADMIN)

    @classmethod
    def __setup__(cls):
        super(FosterEvent, cls).__setup__()
        cls.animal.domain += [
            ('farm', '=', Eval('farm')),
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
        cls._error_messages.update({
                'farrowing_group_not_in_location': ('The farrowing group of '
                    'foster event "%(event)s" doesn\'t have %(quantity)s '
                    'units in location "%(location)s" at "%(timestamp)s".'),
                'pair_farrowing_group_not_in_location': ('The farrowing group '
                    'of the pair female of foster event "%(event)s" doesn\'t '
                    'have %(quantity)s units in location "%(location)s" at '
                    '"%(timestamp)s".'),
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
        return super(FosterEvent, self).get_rec_name(name)

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

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        '''
        If no pair_animal_id is given, we should create, move animals from and
            to specie_id.foster_location_id.
        If pair_animal_id is given, create a symmetric event for that animal
            (exchanging animal_id != pair_animal_id and
                fostered_in != fostered_out)
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        todo_moves = []
        for foster_event in events:
            assert (not foster_event.move and not foster_event.pair_event), (
                'Foster Event %s already has related pair event or stock move'
                % foster_event.id)
            farrowing_group = foster_event.farrowing_group
            pair_farrowing_group = (foster_event.pair_female and
                foster_event.pair_female.last_produced_group)

            if (foster_event.quantity < 0 and
                    not farrowing_group.check_in_location(
                        foster_event.animal.location,
                        foster_event.timestamp,
                        - foster_event.quantity)):
                cls.raise_user_error('farrowing_group_not_in_location', {
                        'event': foster_event.rec_name,
                        'location': foster_event.from_location.rec_name,
                        'quantity': - foster_event.quantity,
                        'timestamp': foster_event.timestamp,
                        })
            elif (foster_event.quantity and pair_farrowing_group and
                    not pair_farrowing_group.check_in_location(
                        foster_event.pair_female.location,
                        foster_event.timestamp,
                        foster_event.quantity)):
                cls.raise_user_error('pair_farrowing_group_not_in_location', {
                        'event': foster_event.rec_name,
                        'location': foster_event.pair_female.location.rec_name,
                        'quantity': - foster_event.quantity,
                        'timestamp': foster_event.timestamp,
                        })

            current_cycle = foster_event.animal.current_cycle
            foster_event.female_cycle = current_cycle

            if foster_event.pair_female:
                pair_event = foster_event._get_pair_event()
                pair_event.save()
                foster_event.pair_event = pair_event
                todo_moves.append(pair_event.move)

            new_move = foster_event._get_event_move()
            new_move.save()
            foster_event.move = new_move
            todo_moves.append(new_move)

            foster_event.save()
        Move.assign(todo_moves)
        Move.do(todo_moves)

    def _get_pair_event(self):
        pair_event, = FosterEvent.copy([self], {
                'animal': self.pair_female.id,
                'quantity': - self.quantity,
                'pair_female': self.animal.id,
                })

        pair_event.pair_event = self
        pair_event.female_cycle = pair_event.animal.current_cycle

        pair_new_move = pair_event._get_event_move()
        pair_new_move.save()
        pair_event.move = pair_new_move

        pair_event.state = 'validated'
        return pair_event

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context
        if self.quantity > 0:  # Foster In
            from_location = self.specie.foster_location
            to_location = self.animal.location
        else:
            from_location = self.animal.location
            to_location = self.specie.foster_location
        return Move(
            product=self.farrowing_group.lot.product,
            uom=self.farrowing_group.lot.product.default_uom,
            quantity=abs(self.quantity),
            from_location=from_location,
            to_location=to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=context.get('company'),
            lot=self.farrowing_group.lot,
            origin=self)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'pair_event': None,
                'female_cycle': None,
                'move': None,
                })
        return super(FosterEvent, cls).copy(records, default=default)

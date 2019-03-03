#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import logging
from datetime import datetime

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Bool, Equal, Eval, Get, Not
from trytond.pool import Pool
from trytond.transaction import Transaction

__all__ = ['EventOrder']

# The fields of the header are readonly if there are lines defined because they
# are used in the lines' domain
_STATES_HEADER = {
    'readonly': (Bool(Eval('medication_events', [])) |
        Bool(Eval('insemination_events', [])) |
        Bool(Eval('pregnancy_diagnosis_events', [])) |
        Bool(Eval('abort_events', [])) |
        Bool(Eval('farrowing_events', [])) |
        Bool(Eval('foster_events', [])) |
        Bool(Eval('weaning_events', []))),
    }
_DEPENDS_HEADER = []
_DOMAIN_LINES = [
    ('animal_type', '=', Eval('animal_type')),
    ('specie', '=', Eval('specie')),
    ('farm', '=', Eval('farm')),
    ('employee', '=', Eval('employee')),
    ]
_DEPENDS_LINES = ['animal_type', 'specie', 'event_type', 'farm', 'timestamp',
    'employee']


def _STATES_LINES(event_type):
    return {
        'invisible': Not(Equal(Eval('event_type'), event_type)),
        }


class EventOrder(ModelSQL, ModelView, Workflow):
    'Farm Events Work Order'
    __name__ = 'farm.event.order'
    _order = [('name', 'ASC')]

    name = fields.Char("Reference", select=True)
    animal_type = fields.Selection([
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
            ('group', 'Group'),
            ], "Animal Type", required=True, readonly=True, select=True,
        states={
            'invisible': Bool(Get(Eval('context', {}), 'animal_type')),
            })
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True, select=True, states={
            'invisible': Bool(Get(Eval('context', {}), 'specie')),
            })
    event_type = fields.Selection([
            ('medication', 'Medications'),
            ('insemination', 'Inseminations'),
            ('pregnancy_diagnosis', 'Pregnancy Diagnosis'),
            ('abort', 'Aborts'),
            ('farrowing', 'Farrowings'),
            ('foster', 'Fosters'),
            ('weaning', 'Weanings'),
            ], "Event Type", required=True, readonly=True, select=True,
        states={
            'invisible': Bool(Get(Eval('context', {}), 'event_type')),
            })
    farm = fields.Many2One('stock.location', 'Farm', required=True,
        domain=[
            ('type', '=', 'warehouse'),
            ('id', 'in', Eval('context', {}).get('farms', [])),
            ],
        context={
            'restrict_by_specie_animal_type': True,
            },
        states=_STATES_HEADER, depends=_DEPENDS_HEADER)
    timestamp = fields.DateTime('Date & Time', required=True,
        states=_STATES_HEADER, depends=_DEPENDS_HEADER)
    employee = fields.Many2One('party.party', 'Employee',
        states=_STATES_HEADER, depends=_DEPENDS_HEADER,
        help='Employee that did the job.')
    # Generic Events
    medication_events = fields.One2Many('farm.medication.event', 'order',
        'Medications', domain=_DOMAIN_LINES,
        states=_STATES_LINES('medication'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    # Female Events
    insemination_events = fields.One2Many('farm.insemination.event', 'order',
        'Inseminations', domain=_DOMAIN_LINES,
        states=_STATES_LINES('insemination'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    pregnancy_diagnosis_events = fields.One2Many(
        'farm.pregnancy_diagnosis.event', 'order',
        'Pregnancy Diagnosis', domain=_DOMAIN_LINES,
        states=_STATES_LINES('pregnancy_diagnosis'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    abort_events = fields.One2Many('farm.abort.event', 'order', 'Abort Events',
        domain=_DOMAIN_LINES, states=_STATES_LINES('abort'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    farrowing_events = fields.One2Many('farm.farrowing.event', 'order',
        'Farrowings', domain=_DOMAIN_LINES,
        states=_STATES_LINES('farrowing'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    foster_events = fields.One2Many('farm.foster.event', 'order',
        'Fosters', domain=_DOMAIN_LINES,
        states=_STATES_LINES('foster'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)
    weaning_events = fields.One2Many('farm.weaning.event', 'order',
        'Weanings', domain=_DOMAIN_LINES,
        states=_STATES_LINES('weaning'), context={
            'timestamp': Eval('timestamp'),
            }, depends=_DEPENDS_LINES)

    @classmethod
    def __setup__(cls):
        super(EventOrder, cls).__setup__()
        cls._sql_constraints += [
            ('name_required', 'CHECK (name IS NOT NULL)',
                'The Reference of the Event Order is required.'),
            ('name_uniq', 'UNIQUE (name)',
                'The Reference of the Event Order must be unique.'),
            ]
        cls._error_messages.update({
                'incompatible_animal_and_event_type': ('The Animal and Event '
                    'Type of Event Order "%s" are incompatibles.'),
                'no_farm_specie_farm_line_available': ('The specified farm '
                    '"%(farm)s" is not configured as farm with '
                    '"%(animal_type)s" for the specie "%(specie)s"'),
                })
        cls._buttons.update({
            'draft': {},
            'confirm': {},
            'cancel': {},
            })

    @staticmethod
    def default_animal_type():
        return Transaction().context.get('animal_type')

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_event_type():
        return Transaction().context.get('event_type')

    @staticmethod
    def default_timestamp():
        return Transaction().context.get('timestamp') or datetime.now()

    @staticmethod
    def default_employee():
        return Transaction().context.get('employee')

    @staticmethod
    def default_farm():
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        if user.farms:
            return user.farms[0].id

    @classmethod
    def validate(cls, orders):
        super(EventOrder, cls).validate(orders)
        for order in orders:
            order.check_animal_and_event_type()

    def check_animal_and_event_type(self):
        if self.event_type not in self.event_types_by_animal_type(
                self.animal_type, True):
            self.raise_user_error('incompatible_animal_and_event_type',
                self.rec_name)

    @staticmethod
    def event_types_by_animal_type(animal_type, include_generic):
        res = []
        if animal_type == 'generic' or include_generic:
            res.append('medication')
        if animal_type == 'female':
            res += [
                'insemination',
                'pregnancy_diagnosis',
                'abort',
                'farrowing',
                'foster',
                'weaning',
                ]
        return res

    @classmethod
    def create(cls, vlist):
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            logging.getLogger(cls.__name__).debug("Create vals: %s" % vals)
            if not vals.get('specie'):
                vals['specie'] = cls.default_specie()
            if not vals.get('animal_type'):
                vals['animal_type'] = cls.default_animal_type()
            if not vals.get('name'):
                vals['name'] = cls._calc_name(vals['specie'], vals['farm'],
                    vals['animal_type'])
        return super(EventOrder, cls).create(vlist)

    @classmethod
    def copy(cls, orders, default=None):
        if default is None:
            default = {}

        default.update({
                'timestamp': datetime.now(),
                'medication_events': None,
                'insemination_events': None,
                'pregnancy_diagnosis_events': None,
                'abort_events': None,
                'farrowing_events': None,
                'foster_events': None,
                'weaning_events': None,
                })

        res = []
        for order in orders:
            new_default = default.copy()
            new_default.update({
                    'name': cls._calc_name(order.specie.id, order.farm.id,
                        order.animal_type),
                    })
            new_order, = super(EventOrder, cls).copy([order],
                default=new_default)
            res.append(new_order)
        return res

    @classmethod
    def _calc_name(cls, specie_id, farm_id, animal_type):
        pool = Pool()
        FarmLine = pool.get('farm.specie.farm_line')
        Location = pool.get('stock.location')
        Sequence = pool.get('ir.sequence')
        Specie = pool.get('farm.specie')

        if not specie_id or not farm_id or not animal_type:
            return

        farm_lines = FarmLine.search([
                ('specie', '=', specie_id),
                ('farm', '=', farm_id),
                ('has_' + animal_type, '=', True),
                ])
        if not farm_lines:
            cls.raise_user_error('no_farm_specie_farm_line_available', {
                    'farm': Location(farm_id).rec_name,
                    'animal_type': animal_type,
                    'specie': Specie(specie_id).rec_name,
                    })
        farm_line, = farm_lines
        return Sequence.get_id(farm_line.event_order_sequence.id)

    @classmethod
    @ModelView.button
    def draft(cls, orders):
        pool = Pool()
        for order in orders:
            Event = pool.get('farm.%s.event' % order.event_type)
            events = Event.search([
                    ('order', '=', order.id),
                    ('state', '=', 'cancel'),
                    ])
            Event.draft(events)

    @classmethod
    @ModelView.button
    def confirm(cls, orders):
        pool = Pool()
        for order in orders:
            Event = pool.get('farm.%s.event' % order.event_type)
            events = Event.search([
                    ('order', '=', order.id),
                    ('state', '=', 'draft'),
                    ])
            Event.validate_event(events)

    @classmethod
    @ModelView.button
    def cancel(cls, orders):
        pool = Pool()
        for order in orders:
            Event = pool.get('farm.%s.event' % order.event_type)
            events = Event.search([
                    ('order', '=', order.id),
                    ('state', '=', 'validated'),  # also in 'draft'?
                    ])
            Event.cancel(events)

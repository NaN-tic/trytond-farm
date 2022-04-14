# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import datetime, date

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Equal, Eval, Id, Not
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.exceptions import UserError
from trytond.i18n import gettext

_EVENT_STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    # ('cancelled', 'Cancelled'),
    ]
_STATES_WRITE_DRAFT = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
    }
_DEPENDS_WRITE_DRAFT = ['state']
_STATES_VALIDATED = {
    'required': Equal(Eval('state'), 'validated'),
    }
_DEPENDS_VALIDATED = ['state']
_STATES_WRITE_DRAFT_VALIDATED = {
    'readonly': Not(Equal(Eval('state'), 'draft')),
    'required': Equal(Eval('state'), 'validated'),
    }
_DEPENDS_WRITE_DRAFT_VALIDATED = ['state']
_STATES_VALIDATED_ADMIN = {
    'required': Equal(Eval('state'), 'validated'),
    'invisible': ~Eval('context', {}).get('groups', []).contains(
        Id('farm', 'group_farm_admin')),
    }
_DEPENDS_VALIDATED_ADMIN = ['state']


class AbstractEvent(ModelSQL, ModelView, Workflow):
    'Event'
    __name__ = 'farm.event'
    _order = [
        ('timestamp', 'ASC'),
        ('id', 'DESC'),
        ]

    animal_type = fields.Selection([
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
            ('group', 'Group'),
            ], 'Animal Type', required=True, select=True, states={
            'readonly': True,
            })
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        select=True, states={
            'readonly': True,
            })
    farm = fields.Many2One('stock.location', 'Farm', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT,
        domain=[
            ('type', '=', 'warehouse'),
            ],
        context={
            'restrict_by_specie_animal_type': True,
            })
    order = fields.Many2One('farm.event.order', 'Order', readonly=True)
    animal = fields.Many2One('farm.animal', 'Animal', domain=[
            ('specie', '=', Eval('specie')),
            ('type', '=', Eval('animal_type')),
            # It fails when it is introducing event in past. For example in
            # feed inventories
            # If(Equal(Eval('state', ''), 'draft'),
            #     ('farm', '=', Eval('farm')),
            #     ()),
            ],
        select=True, states={
            'invisible': Equal(Eval('animal_type'), 'group'),
            'required': Not(Equal(Eval('animal_type'), 'group')),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['specie', 'animal_type', 'farm', 'state'])
    animal_group = fields.Many2One('farm.animal.group', 'Group', domain=[
            ('specie', '=', Eval('specie')),
            ('farms', 'in', [Eval('farm', -1)]),
            ],
        select=True, states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            'required': Equal(Eval('animal_type'), 'group'),
            'readonly': Not(Equal(Eval('state'), 'draft')),
            },
        depends=['specie', 'animal_type', 'farm', 'state'])
    lot = fields.Function(fields.Many2One('stock.lot', 'Lot'),
        'get_lot')
    # TODO: Used for permission management and filtering. If dot notation
    # doesn't work implement it
    # current_farms = fields.Function(fields.Many2Many('stock.warehouse',
    #            None, None, 'Current Farms', help='The farms (warehouses) '
    #            'where the animal or group is now.'), 'get_current_warehouse')
    timestamp = fields.DateTime('Date & Time', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    employee = fields.Many2One('party.party', 'Employee',
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT,
        help='Employee that did the job.')
    notes = fields.Text('Notes')
    state = fields.Selection(_EVENT_STATES, 'State', required=True,
        readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(AbstractEvent, cls).__setup__()
        cls._buttons.update({
                'draft': {
                    'invisible': Eval('state') == 'draft',
                    'icon': 'tryton-back',
                   },
                'validate_event': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-ok',
                    },
                })
        cls._transitions = set((
                # ('draft', 'cancelled'),
                ('draft', 'validated'),
                ('validated', 'draft')
                # ('validated', 'cancelled'),
                # ('cancelled', 'draft'),
                ))

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_farm():
        pool = Pool()
        User = pool.get('res.user')
        user = User(Transaction().user)
        if user.warehouse:
            return user.warehouse.id

    @staticmethod
    def default_animal_type():
        return Transaction().context.get('animal_type')

    @staticmethod
    def default_timestamp():
        return Transaction().context.get('timestamp') or datetime.now()

    @staticmethod
    def default_employee():
        return Transaction().context.get('employee')

    @staticmethod
    def default_state():
        return 'draft'

    def get_rec_name(self, name):
        if self.animal_type == 'group':
            return "%s %s" % (self.animal_group.rec_name, self.timestamp)
        else:
            return "%s %s" % (self.animal.rec_name, self.timestamp)

    def get_lot(self, name):
        if self.animal_type == 'group':
            return self.animal_group.lot.id
        return self.animal.lot.id

    @staticmethod
    def valid_animal_types():
        raise NotImplementedError(
            "Please Implement valid_animal_types() method")

    @fields.depends('animal_type', 'animal', '_parent_animal.farm')
    def on_change_animal(self):
        if (self.animal_type == 'group' or not self.animal or
                not self.animal.farm):
            return
        self.farm = self.animal.farm

    @fields.depends('timestamp')
    def on_change_timestamp(self):
        if not self.timestamp:
            return

        today = date.today()
        if isinstance(self.timestamp, datetime):
            set_date = self.timestamp.date()
        else:
            set_date = self.timestamp
        if set_date > today:
            raise UserError(gettext('farm.abstract_invalid_date'))

    @fields.depends('animal_type', 'animal_group')
    def on_change_animal_group(self):
        if (self.animal_type != 'group' or not self.animal_group or
                not self.animal_group.farms):
            return
        self.farm = self.animal_group.farms[0]

    @classmethod
    def copy(cls, events, default=None):
        if default is None:
            default = {}
        default['state'] = 'draft'
        return super(AbstractEvent, cls).copy(events, default)

    @classmethod
    def delete(cls, events):
        for event in events:
            if event.state != 'draft':
                raise UserError(gettext('farm.invalid_state_to_delete',
                    event=event.rec_name))
        return super(AbstractEvent, cls).delete(events)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, events):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Tests if animal or group is in warehouse in the timestamp of event
        """
        raise NotImplementedError("Please Implement validate_event() method")

    # @classmethod
    # @ModelView.button
    # @Workflow.transition('cancelled')
    # def cancel(cls, events):
    #     raise NotImplementedError("Please Implement cancel() method")


_STATES_VALIDATED_ADMIN_BUT_IMPORTED = _STATES_VALIDATED_ADMIN.copy()
_STATES_VALIDATED_ADMIN_BUT_IMPORTED['required'] &= Not(Eval('imported',
        False))
_DEPENDS_VALIDATED_ADMIN_BUT_IMPORTED = ['state', 'imported']


class ImportedEventMixin:
    imported = fields.Boolean('Imported', readonly=True)

    @staticmethod
    def default_imported():
        return False

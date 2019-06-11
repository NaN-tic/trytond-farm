# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from datetime import date, datetime, timedelta
from decimal import Decimal
from trytond.rpc import RPC
from trytond.model import ModelView, ModelSQL, fields, UnionMixin, Unique
from trytond.pyson import Equal, Eval, Greater, Id, Not, Bool
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta
from trytond.wizard import Wizard, StateView, StateAction, Button, StateTransition
from trytond.exceptions import UserError
from trytond.i18n import gettext

__all__ = ['Tag', 'Animal', 'AnimalTag', 'AnimalWeight', 'Male', 'Female',
    'FemaleCycle', 'CreateFemaleStart', 'CreateFemaleLine', 'CreateFemale',
    'ChangeCycleObservationStart', 'ChangeCycleObservation', 'EventUnion']

_STATES_MALE_FIELD = {
    'invisible': Not(Equal(Eval('type'), 'male')),
    }
_DEPENDS_MALE_FIELD = ['type']
_STATES_FEMALE_FIELD = {
    'invisible': Not(Equal(Eval('type'), 'female')),
    }
_DEPENDS_FEMALE_FIELD = ['type']
_STATES_INDIVIDUAL_FIELD = {
    'invisible': Not(Equal(Eval('type'), 'individual')),
    }
_DEPENDS_INDIVIDUAL_FIELD = ['type']

ANIMAL_ORIGIN = [
    ('purchased', 'Purchased'),
    ('raised', 'Raised'),
    ]
FEMALE_CICLE_STATES = [
    ('mated', 'Mated'),
    ('pregnant', 'Pregnant'),
    ('lactating', 'Lactating'),
    ('unmated', 'Unmated'),
    ]


class Tag(ModelSQL, ModelView):
    'Farm Tags'
    __name__ = 'farm.tag'

    name = fields.Char('Name', required=True)
    animals = fields.Many2Many('farm.animal-farm.tag', 'tag', 'animal',
         'Animals')
    animal_group = fields.Many2Many('farm.animal.group-farm.tag', 'tag',
        'group', 'Groups')

    @classmethod
    def __setup__(cls):
        super(Tag, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('name_uniq', Unique(t, t.name),
                'farm.tag_must_be_unique'),
            ]


class AnimalMixin:
    feed_unit_digits = fields.Function(fields.Integer('Feed Unit Digits'),
        'get_feed_unit_digits')

    def get_feed_unit_digits(self, name):
        Uom = Pool().get('product.uom')
        weight_base_uom, = Uom.search([
                ('symbol', '=', 'kg'),
                ])
        return weight_base_uom.id

    @classmethod
    def _create_and_done_first_stock_move(cls, records):
        """
        It creates the first stock.move for animal's lot, and then confirms,
        assigns and set done it to get stock in initial location (Farm).
        """
        pool = Pool()
        Move = pool.get('stock.move')

        with Transaction().set_context(_check_access=False):
            new_moves = []
            for record in records:
                move = record._get_first_move()
                new_moves.append(move._save_values)
            new_moves = Move.create(new_moves)
            Move.assign(new_moves)
            Move.do(new_moves)
        return new_moves

    def _get_first_move(self):
        """
        Prepare values to create the first stock.move for animal's lot to
        get stock in initial location (Farm).
        """
        pool = Pool()
        Company = pool.get('company.company')
        Move = Pool().get('stock.move')

        context = Transaction().context
        company = Company(context['company'])

        if self.origin == 'purchased':
            from_location = company.party.supplier_location
            if not from_location:
                raise UserError(gettext('farm.missing_supplier_location',
                    party=company.party.rec_name))
        else:  # raised
            from_location = self.initial_location.warehouse.production_location
            if not from_location:
                raise UserError(gettext('farm.missing_production_location',
                    location=self.initial_location.warehouse.rec_name))

        move_date = self.arrival_date or date.today()
        return Move(
            product=self.lot.product,
            uom=self.lot.product.default_uom,
            quantity=getattr(self, 'initial_quantity', 1),
            from_location=from_location,
            to_location=self.initial_location,
            planned_date=move_date,
            effective_date=move_date,
            company=company,
            lot=self.lot,
            unit_price=self.lot.product.cost_price,
            origin=self)


class Animal(ModelSQL, ModelView, AnimalMixin):
    "Farm Animal"
    __name__ = 'farm.animal'

    type = fields.Selection([
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
            ], 'Type', required=True, select=True, states={
            'readonly': True,
            })
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        select=True, states={
            'readonly': True,
            })
    breed = fields.Many2One('farm.specie.breed', 'Breed', required=True,
        domain=[('specie', '=', Eval('specie'))], depends=['specie'])
    lot = fields.One2One('stock.lot-farm.animal', 'animal', 'lot',
        string='Lot', required=True, readonly=True, domain=[
            ('animal_type', '=', Eval('type')),
        ], depends=['type'])
    number = fields.Function(fields.Char('Number'),
        'get_number', 'set_number', searcher='search_number')
    # location is updated in do() of stock.move
    location = fields.Many2One('stock.location', 'Current Location',
        readonly=True, domain=[
            ('type', '!=', 'warehouse'),
            ('silo', '=', False),
            ], help='Indicates where the animal currently resides.')
    farm = fields.Function(fields.Many2One('stock.location', 'Current Farm'),
        'on_change_with_farm', searcher='search_farm')
    origin = fields.Selection(ANIMAL_ORIGIN, 'Origin', required=True,
        readonly=True,
        help='Raised means that this animal was born in the farm. Otherwise, '
        'it was purchased.')
    arrival_date = fields.Date('Arrival Date', states={
            'readonly': Greater(Eval('id', 0), 0),
            }, depends=['id'],
        help="The date this animal arrived (if it was purchased) or when it "
        "was born.")
    purchase_shipment = fields.Many2One('stock.shipment.in',
        'Purchase Shipment', readonly=True,
        states={'invisible': Not(Equal(Eval('origin'), 'purchased'))},
        depends=['origin'])
    initial_location = fields.Many2One('stock.location', 'Initial Location',
        required=True, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states={'readonly': Greater(Eval('id', 0), 0)}, depends=['id'],
        context={'restrict_by_specie_animal_type': True},
        help="The Location where the animal was reached or where it was "
        "allocated when it was purchased.\nIt is used as historical "
        "information and to get Serial Number.")
    birthdate = fields.Date('Birthdate')
    removal_date = fields.Date('Removal Date', readonly=True,
        help='Get information from the corresponding removal event.')
    removal_reason = fields.Many2One('farm.removal.reason', 'Removal Reason',
        readonly=True)
    weights = fields.One2Many('farm.animal.weight', 'animal',
        'Weight Records', readonly=False, order=[('timestamp', 'DESC')])
    current_weight = fields.Function(fields.Many2One('farm.animal.weight',
            'Current Weight'),
        'on_change_with_current_weight')
    tags = fields.Many2Many('farm.animal-farm.tag', 'animal', 'tag', 'Tags')
    notes = fields.Text('Notes')
    active = fields.Boolean('Active')
    consumed_feed = fields.Function(fields.Numeric('Consumed Feed (Kg)',
            digits=(16, Eval('feed_unit_digits', 2)),
            depends=['feed_unit_digits']),
        'get_consumed_feed')
    # Individual Fields
    sex = fields.Selection([
            ('male', "Male"),
            ('female', "Female"),
            ('undetermined', "Undetermined"),
            ], 'Sex', required=True, states=_STATES_INDIVIDUAL_FIELD,
        depends=_DEPENDS_INDIVIDUAL_FIELD)
    purpose = fields.Selection([
            (None, ''),
            ('sale', 'Sale'),
            ('replacement', 'Replacement'),
            ('unknown', 'Unknown'),
            ], 'Purpose', states=_STATES_INDIVIDUAL_FIELD,
        depends=_DEPENDS_INDIVIDUAL_FIELD)
    active = fields.Boolean('Active')

    # We can't use the 'required' attribute in field because it's
    # checked on view before execute 'create()' function where this
    # field is filled in.

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_breed():
        pool = Pool()
        Specie = pool.get('farm.specie')
        context = Transaction().context
        if 'specie' in context:
            specie = Specie(context['specie'])
            if len(specie.breeds) == 1:
                return specie.breeds[0].id

    @staticmethod
    def default_type():
        return Transaction().context.get('animal_type')

    @staticmethod
    def default_origin():
        return 'purchased'

    @staticmethod
    def default_arrival_date():
        return date.today()

    @staticmethod
    def default_sex():
        sex = Transaction().context.get('animal_type', 'undetermined')
        if sex in ('group', 'individual'):
            sex = 'undetermined'
        return sex

    @staticmethod
    def default_active():
        return True

    def get_rec_name(self, name):
        if self.lot:
            name = self.lot.number
            if not self.active:
                name += ' (*)'
            return name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('lot.number',) + tuple(clause[1:])]

    @classmethod
    def search_number(cls, name, clause):
        return [('lot.number',) + tuple(clause[1:])]

    def get_number(self, name):
        if self.lot:
            return self.lot.number

    @classmethod
    def set_number(cls, animals, name, value):
        Lot = Pool().get('stock.lot')
        lots = [animal.lot for animal in animals if animal.lot]
        if lots:
            Lot.write(lots, {
                    'number': value,
                    })

    @fields.depends('location')
    def on_change_with_farm(self, name=None):
        return (self.location and self.location.warehouse and
            self.location.warehouse.id or None)

    @classmethod
    def search_farm(cls, name, clause):
        return [('location.warehouse',) + tuple(clause[1:])]

    @fields.depends('weights')
    def on_change_with_current_weight(self, name=None):
        if self.weights:
            return self.weights[0].id

    def get_consumed_feed(self, name):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')
        Uom = pool.get('product.uom')

        now = datetime.now()
        feed_events = FeedEvent.search([
                ('animal_type', '=', self.type),
                ('animal', '=', self.id),
                ('state', 'in', ['provisional', 'validated']),
                ['OR', [
                    ('start_date', '=', None),
                    ('timestamp', '<=', now),
                    ], [
                    ('start_date', '<=', now.date()),
                    ]],
                ])

        kg, = Uom.search([
                ('symbol', '=', 'kg'),
                ])
        consumed_feed = Decimal('0.0')
        for event in feed_events:
            # TODO: it uses compute_price() because quantity is a Decimal
            # quantity in feed_product default uom. The method is not for
            # this purpose but it works
            event_feed_quantity = Uom.compute_price(kg, event.feed_quantity,
                event.uom)
            if event.timestamp > now:
                event_feed_quantity /= (event.end_date - event.start_date).days
                event_feed_quantity *= (now.date() - event.start_date).days
            consumed_feed += event_feed_quantity
        return consumed_feed

    def check_in_location(self, location, timestamp):
        with Transaction().set_context(
                locations=[location.id],
                stock_date_end=timestamp.date()):
            return self.lot.quantity == 1

    def check_allowed_location(self, location, event_rec_name):
        if not location.warehouse:
            return
        for farm_line in self.specie.farm_lines:
            if farm_line.farm.id == location.warehouse.id:
                if getattr(farm_line, 'has_%s' % self.type):
                    return
        raise UserError(gettext('farm.invalid_animal_destination',
                event=event_rec_name,
                animal=self.rec_name,
                location=location.rec_name,
                ))

    @classmethod
    def copy(cls, animals, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
            'lot': None,
            'number': None,
            'location': None,
            'purchase_shipment': None,
            'removal_reason': None,
            'removal_date': None,
            'weights': None,
            })
        return super(Animal, cls).copy(animals, default=default)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')

        context = Transaction().context
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('specie'):
                vals['specie'] = cls.default_specie()
            if not vals.get('type'):
                vals['type'] = cls.default_type()
            if vals['type'] in ('male', 'female'):
                vals['sex'] = vals['type']
            if not vals.get('number'):
                location = Location(vals['initial_location'])
                vals['number'] = cls._calc_number(vals['specie'],
                        location.warehouse.id, vals['type'])
            if vals.get('lot'):
                lot = Lot(vals['lot'])
                Lot.write([lot], cls._get_lot_values(vals, False))
            else:
                new_lot, = Lot.create([cls._get_lot_values(vals, True)])
                vals['lot'] = new_lot.id
        new_animals = super(Animal, cls).create(vlist)
        if not context.get('no_create_stock_move'):
            cls._create_and_done_first_stock_move(new_animals)
        return new_animals

    @classmethod
    def _calc_number(cls, specie_id, farm_id, type):
        pool = Pool()
        FarmLine = pool.get('farm.specie.farm_line')
        Location = pool.get('stock.location')
        Sequence = pool.get('ir.sequence')
        Specie = pool.get('farm.specie')

        sequence_fieldname = '%s_sequence' % type
        farm_lines = FarmLine.search([
                ('specie', '=', specie_id),
                ('farm', '=', farm_id),
                ('has_' + type, '=', True),
                ])
        if not farm_lines:
            raise UserError(gettext(
                    'farm.animal_no_farm_specie_farm_line_available',
                    farm=Location(farm_id).rec_name,
                    animal_type=type,
                    specie=Specie(specie_id).rec_name,
                    ))
        farm_line, = farm_lines
        sequence = getattr(farm_line, sequence_fieldname, False)
        if not sequence:
            raise UserError(gettext('farm.no_sequence_in_farm_line',
                    sequence_field=getattr(FarmLine, sequence_fieldname).string,
                    farm_line=farm_line.rec_name,
                    ))
        return Sequence.get_id(sequence.id)

    @classmethod
    def _get_lot_values(cls, animal_vals, create):
        """
        Prepare values to create the stock.lot for the new animal.
        animal_vals: dictionary with values to create farm.animal
        It returns a dictionary with values to create stock.lot
        """
        pool = Pool()
        Lot = pool.get('stock.lot')
        Specie = pool.get('farm.specie')

        if not animal_vals:
            return {}
        specie = Specie(animal_vals['specie'])
        product_fieldname = '%s_product' % animal_vals['type']
        product = getattr(specie, product_fieldname, False)
        if not product:
            raise UserError(gettext('farm.no_product_in_specie',
                    product_field=getattr(Specie, product_fieldname).string,
                    specie=specie.rec_name,
                    ))

        lot_tmp = Lot(product=product)
        res = {
            'number': animal_vals['number'],
            'product': product.id,
            'animal_type': animal_vals['type'],
            }
        if Transaction().context.get('create_cost_lines', True):
            cost_lines = lot_tmp._on_change_product_cost_lines().get('add')
            if cost_lines:
                res['cost_lines'] = [('create', [cl[1] for cl in cost_lines])]
        return res

    @classmethod
    def delete(cls, animals):
        pool = Pool()
        Lot = pool.get('stock.lot')

        lots = [a.lot for a in animals if a.lot is not None]
        if lots:
            Lot.write(lots, {'animal': None})
        result = super(Animal, cls).delete(animals)
        if lots:
            Lot.delete(lots)
        return result


class AnimalTag(ModelSQL):
    'Animal - Tag'
    __name__ = 'farm.animal-farm.tag'
    animal = fields.Many2One('farm.animal', 'Animal', ondelete='CASCADE',
        required=True, select=True)
    tag = fields.Many2One('farm.tag', 'Tag', ondelete='CASCADE', required=True,
        select=True)


class AnimalWeight(ModelSQL, ModelView):
    'Farm Animal Weight Record'
    __name__ = 'farm.animal.weight'
    _order = [('timestamp', 'DESC')]

    animal = fields.Many2One('farm.animal', 'Animal',
        required=True,
        ondelete='CASCADE')
    timestamp = fields.DateTime('Date & Time', required=True)
    uom = fields.Many2One('product.uom', "UoM",
        required=True,
        domain=[('category', '=', Id('product', 'uom_cat_weight'))])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    weight = fields.Numeric('Weight',
        digits=(16, Eval('unit_digits', 2)),
        required=True,
        depends=['unit_digits'])

    @staticmethod
    def default_timestamp():
        return datetime.now()

    @staticmethod
    def default_uom():
        return Pool().get('ir.model.data').get_id('product', 'uom_kilogram')

    @staticmethod
    def default_unit_digits():
        return 2

    def get_rec_name(self, name):
        return '%s %s (%s)' % (self.weight, self.uom.symbol, self.timestamp)

    @classmethod
    def search_rec_name(cls, name, clause):
        operand = clause[2]
        operand = operand.replace('%', '')
        try:
            operand = Decimal(operand)
        except:
            return [('weight', '=', 0)]
        operator = clause[1]
        operator = operator.replace('ilike', '=').replace('like', '=')
        return [('weight', operator, operand)]

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class Male(metaclass=PoolMeta):
    __name__ = 'farm.animal'

    extractions = fields.One2Many('farm.semen_extraction.event',
        'animal', 'Semen Extractions', states=_STATES_MALE_FIELD,
        depends=_DEPENDS_MALE_FIELD)
    last_extraction = fields.Date('Last Extraction', readonly=True,
        states=_STATES_MALE_FIELD, depends=_DEPENDS_MALE_FIELD)

    def update_last_extraction(self, validated_event=None):
        if not self.extractions:
            self.last_extraction = None
            self.save()
            return None
        last_extraction = None
        reversed_extractions = list(self.extractions)
        reversed_extractions.reverse()
        for extraction_event in reversed_extractions:
            if (extraction_event.state == 'validated' or
                    validated_event and extraction_event == validated_event):
                last_extraction = extraction_event.timestamp.date()
                break
        self.last_extraction = last_extraction
        self.save()
        return last_extraction


class Female(metaclass=PoolMeta):
    __name__ = 'farm.animal'

    cycles = fields.One2Many('farm.animal.female_cycle', 'animal', 'Cycles',
        readonly=True, order=[
            ('sequence', 'ASC'),
            ('ordination_date', 'ASC'),
            ],
        states=_STATES_FEMALE_FIELD, depends=_DEPENDS_FEMALE_FIELD)
    current_cycle = fields.Many2One('farm.animal.female_cycle',
        'Current Cycle', readonly=True, states=_STATES_FEMALE_FIELD,
        depends=_DEPENDS_FEMALE_FIELD)
    current_cycle_state = fields.Selection([(None, '')] + FEMALE_CICLE_STATES,
        'Current Cycle State', readonly=True, states=_STATES_FEMALE_FIELD,
        depends=_DEPENDS_FEMALE_FIELD)
    state = fields.Selection([
            (None, ''),
            ('prospective', 'Prospective'),
            ('unmated', 'Unmated'),
            ('mated', 'Mated'),
            ('removed', 'Removed'),
            ],
        'Status', readonly=True, states=_STATES_FEMALE_FIELD,
        depends=_DEPENDS_FEMALE_FIELD,
        help='According to NPPC Production and Financial Standards there are '
        'four status for breeding sows. The status change is event driven: '
        'arrival date, entry date mating event and removal event')
    first_mating = fields.Function(fields.Date('First Mating',
            states=_STATES_FEMALE_FIELD, depends=_DEPENDS_FEMALE_FIELD,
            help='Date of first mating. This will change the status of the '
            'sow to "mated"'),
        'get_first_mating')
    days_from_insemination = fields.Function(fields.Integer('Inseminated Days',
            help='Number of days from last insemination. -1 if there isn\'t '
            'any insemination.'),
        'get_days_from_insemination', searcher='search_days_from_insemination')
    last_produced_group = fields.Function(fields.Many2One('farm.animal.group',
            'Last Produced Group', domain=[
                ('specie', '=', Eval('specie')),
                ], depends=['specie']),
        'get_last_produced_group')
    days_from_farrowing = fields.Function(fields.Integer('Unpregnant Days',
            help='Number of days from last farrowing. -1 if there '
            'isn\'t any farrowing.'),
        'get_days_from_farrowing', searcher='search_days_from_farrowing')
    farrowing_group = fields.Function(fields.Many2One('farm.animal.group',
            'Farrowing Group'),
        'get_farrowing_group')

    events = fields.One2Many('farm.animal.cycle.events', 'animal', 'Events',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(Female, cls).__setup__()
        cls._buttons.update({
                'change_observation': {
                    'invisible': Not(Bool(Eval('cycles'))),
                }
            })

    @staticmethod
    def default_state():
        '''
        Specific for Female animals.
        '''
        if Transaction().context.get('animal_type') == 'female':
            return 'prospective'
        return None

    @classmethod
    @ModelView.button_action('farm.wizard_farm_cycle_observation_female')
    def change_observation(cls, records):
        pass

    def is_lactating(self):
        return (self.current_cycle and self.current_cycle.state == 'lactating'
            or False)

    # TODO: call when cycle is created, deleted or its ordination_date or
    # sequence are modifyied
    def update_current_cycle(self):
        current_cycle = self.cycles and self.cycles[-1] or None
        self.current_cycle = current_cycle
        self.current_cycle_state = (current_cycle.state
            if current_cycle else None)
        self.save()
        return current_cycle

    def get_state(self):
        if self.type != 'female':
            return
        if self.removal_date and self.removal_date <= date.today():
            state = 'removed'
        elif (not self.cycles or len(self.cycles) == 1 and
                not self.cycles[0].weaning_event and
                self.cycles[0].state == 'unmated'):
            state = 'prospective'
        elif self.current_cycle and self.current_cycle.state == 'unmated':
            state = 'unmated'
        else:
            state = 'mated'
        return state

    # TODO: call in removal event, when cycle is added (but probably it's
    # called from cycle)
    def update_state(self):
        self.state = self.get_state()
        self.current_cycle_state = (self.current_cycle.state
            if self.current_cycle else None)
        self.save()
        return self.state

    def get_first_mating(self, name):
        InseminationEvent = Pool().get('farm.insemination.event')
        if self.type != 'female':
            return None
        first_inseminations = InseminationEvent.search([
                ('animal', '=', self.id),
                ], limit=1, order=[('timestamp', 'ASC')])
        if not first_inseminations:
            return None
        first_insemination, = first_inseminations
        return first_insemination.timestamp.date()

    def get_days_from_insemination(self, name):
        InseminationEvent = Pool().get('farm.insemination.event')
        last_valid_insemination = InseminationEvent.search([
                ('animal', '=', self.id),
                ('state', '=', 'validated'),
                ], order=[('timestamp', 'DESC')], limit=1)
        if not last_valid_insemination:
            return -1
        days_from_insemination = (date.today() -
            last_valid_insemination[0].timestamp.date()).days
        return days_from_insemination

    @classmethod
    def search_days_from_insemination(cls, name, clause):
        InseminationEvent = Pool().get('farm.insemination.event')

        event_filter, operator = cls._get_filter_search_days(name, clause)

        animal_ids = set()
        for event in InseminationEvent.search(event_filter):
            animal_ids.add(event.animal.id)
        return [
            ('type', '=', 'female'),
            ('id', operator, list(animal_ids)),
            ]

    def get_last_produced_group(self, name):
        FarrowingEvent = Pool().get('farm.farrowing.event')
        last_farrowing_events = FarrowingEvent.search([
                ('animal', '=', self),
                ('state', '=', 'validated'),
                ('produced_group', '!=', None),
                ],
            order=[
                ('timestamp', 'DESC'),
                ], limit=1)
        if last_farrowing_events:
            return last_farrowing_events[0].produced_group.id
        return None

    def get_days_from_farrowing(self, name):
        FarrowingEvent = Pool().get('farm.farrowing.event')
        last_valid_farrowing = FarrowingEvent.search([
                ('animal', '=', self.id),
                ('state', '=', 'validated'),
                ], order=[('timestamp', 'DESC')], limit=1)
        if not last_valid_farrowing:
            return -1
        days_from_farrowing = (date.today() -
            last_valid_farrowing[0].timestamp.date()).days
        return days_from_farrowing

    @classmethod
    def search_days_from_farrowing(cls, name, clause):
        FarrowingEvent = Pool().get('farm.farrowing.event')

        event_filter, operator = cls._get_filter_search_days(name, clause)

        animal_ids = set()
        for event in FarrowingEvent.search(event_filter):
            animal_ids.add(event.animal.id)
        return [
            ('type', '=', 'female'),
            ('id', operator, list(animal_ids)),
            ]

    @classmethod
    def _get_filter_search_days(cls, name, clause):
        event_filter = []
        include_oposite = False
        if isinstance(clause[2], bool) and clause[2] is False:
            if clause[1] == '=':
                include_oposite = True
            # else: "!= False" => inseminated sometimes
        elif isinstance(clause[2], int):
            # third element is a number of days
            operator = False
            n_days = False
            if clause[1] in ('<', '<='):
                operator = '>'
                if clause[1] == '<':
                    n_days = clause[2]
                else:
                    n_days = clause[2] + 1
            elif clause[1] in ('>', '>='):
                operator = '<'
                include_oposite = True
                if clause[1] == '>':
                    n_days = clause[2] + 1
                else:
                    n_days = clause[2]
            elif clause[1] in ('=', '!='):
                operator = clause[1]
                n_days = clause[2]

            if operator and n_days:
                date_lim = date.today() - timedelta(days=n_days)
                if operator == '=':
                    event_filter = ['AND', [
                            ('timestamp', '>=',
                                date_lim.strftime('%Y-%m-%d 00:00:00')),
                        ], [
                            ('timestamp', '<=',
                                date_lim.strftime('%Y-%m-%d 23:59:59')),
                        ], ]
                elif operator == '!=':
                    include_oposite = True
                    event_filter = ['OR', [
                            ('timestamp', '<',
                                date_lim.strftime('%Y-%m-%d 00:00:00')),
                        ], [
                            ('timestamp', '>',
                                date_lim.strftime('%Y-%m-%d 23:59:59')),
                        ], ]
                else:
                    event_filter = [
                        ('timestamp', operator,
                            date_lim.strftime('%Y-%m-%d 23:59:59')),
                        ]
        op = 'in'
        if include_oposite:
            if event_filter:
                event_filter.insert(0, 'NOT')
            op = 'not in'
        return event_filter, op

    def get_farrowing_group(self, name):
        '''
        Return the farm.animal.group produced for current cycle
        '''
        if not self.current_cycle or self.current_cycle.state != 'lactating':
            return None
        return self.current_cycle.farrowing_event.produced_group.id

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Animal = pool.get('farm.animal')
        Location = pool.get('stock.location')
        for vals in vlist:
            if vals.get('type', '') == 'female' and not vals.get('state'):
                vals['state'] = 'prospective'
            number = vals.get('number')
            initial_location = vals.get('initial_location')
            location = Location(initial_location)
            duplicate = Animal.search([
                    ('number', '=', number),
                    ('farm', '=', location.warehouse.id),
                    ('active', '=', True),
                    ], limit=1)

            if duplicate:
                raise UserError(gettext('farm.duplicate_animal', number=number))
        return super(Female, cls).create(vlist)

    @classmethod
    def write(cls, *args):
        actions = iter(args)

        for females, values in zip(actions, actions):
            number = values.get('number')
            if not number:
                continue

            for female in females:
                farm = female.farm

                duplicate = Animal.search([('number', '=', number),
                    ('farm', '=', farm),
                    ('active', '=', True),
                    ('id', '!=', female.id)], limit=1)
                if duplicate:
                    raise UserError('farm.duplicate_animal', number=number)

        super(Female, cls).write(*args)

    @classmethod
    def copy(cls, females, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default['cycles'] = None
        default['current_cycle'] = None
        default['state'] = cls.default_state()
        return super(Female, cls).copy(females, default)


class FemaleCycle(ModelSQL, ModelView):
    'Farm Female Cycle'
    __name__ = 'farm.animal.female_cycle'
    _order = [
        ('animal', 'ASC'),
        ('sequence', 'ASC'),
        ('ordination_date', 'ASC'),
        ]

    animal = fields.Many2One('farm.animal', 'Female', required=True,
        ondelete='CASCADE', domain=[('type', '=', 'female')])
    sequence = fields.Integer('Num. cycle', required=True)
    ordination_date = fields.DateTime('Date for ordination', required=True,
        readonly=True)
    state = fields.Selection(FEMALE_CICLE_STATES, 'State', readonly=True,
        required=True)
    # Female events fields
    insemination_events = fields.One2Many('farm.insemination.event',
        'female_cycle', 'Inseminations')
    days_between_weaning_and_insemination = fields.Function(
        fields.Integer('Unmated Days', help='Number of days between previous '
            'weaning and first insemination.'),
        'get_days_between_weaning_and_insemination')
    diagnosis_events = fields.One2Many('farm.pregnancy_diagnosis.event',
        'female_cycle', 'Diagnosis')
    pregnant = fields.Function(fields.Boolean('Pregnant',
            help='A female will be considered pregnant if there are more than'
            ' one diagnosis and the last one has a positive result.'),
        'on_change_with_pregnant')
    abort_event = fields.One2One('farm.abort.event-farm.animal.female_cycle',
        'cycle', 'event', string='Abort', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], depends=['animal'])
    farrowing_event = fields.One2One(
        'farm.farrowing.event-farm.animal.female_cycle', 'cycle', 'event',
        string='Farrowing', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], depends=['animal'])
    live = fields.Function(fields.Integer('Live'),
        'get_farrowing_event_field')
    dead = fields.Function(fields.Integer('Dead'),
        'get_farrowing_event_field')
    foster_events = fields.One2Many('farm.foster.event', 'female_cycle',
        'Fosters')
    fostered = fields.Function(fields.Integer('Fostered',
            help='Diference between Fostered Input and Output. A negative '
            'number means that he has given more than taken.'),
        'on_change_with_fostered')
    weaning_event = fields.One2One(
        'farm.weaning.event-farm.animal.female_cycle', 'cycle', 'event',
        string='Weaning', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], depends=['animal'])
    weaned = fields.Function(fields.Integer('Weaned Quantity'),
        'get_weaned')
    removed = fields.Function(fields.Integer('Removed Quantity',
            help='Number of removed animals from Produced Group. Diference '
            'between born live and weaned, computing Fostered diference.'),
        'get_removed')
    days_between_farrowing_weaning = fields.Function(
        fields.Integer('Lactating Days',
            help='Number of days between Farrowing and Weaning.'),
        'get_lactating_days')
    observations = fields.Text('Observations')

    @staticmethod
    def default_sequence(animal_id=None):
        '''
        If 'animal_id' is not found in context it return 0.
        Otherwise, if the last cycle is completed (has 'farrowing event'), it
            returns its sequence plus one, if it's not completed it returns its
            sequence.
        '''
        FemaleCycle = Pool().get('farm.animal.female_cycle')
        animal_id = animal_id or Transaction().context.get('animal')
        if not animal_id:
            return 0
        cycles = FemaleCycle.search([
                ('animal', '=', animal_id),
                ],
            order=[
                ('sequence', 'DESC'),
                ('ordination_date', 'DESC'),
                ], limit=1)
        if not cycles:
            return 1
        if cycles[0].farrowing_event:
            return cycles[0].sequence + 1
        return cycles[0].sequence

    @staticmethod
    def default_ordination_date():
        return datetime.now()

    @staticmethod
    def default_state():
        return 'unmated'

    def get_rec_name(self, name):
        return str(self.sequence)

    @fields.depends('animal', 'ordination_date')
    def on_change_ordination_date(self):
        if not self.ordination_date or not self.animal:
            return

        past_date = self.animal.current_cycle.ordination_date.date()
        current_date = self.ordination_date.date()
        if past_date > current_date:
            raise UserError(gettext('farm.cycle_invalid_date'))

    def get_rec_name(self, name):
        state_labels = dict(self.fields_get(['state'])['state']['selection'])
        return "%s (%s)" % (self.sequence, state_labels[self.state])

    # TODO: call in weaning, farrowing, abort, pregnancy_diagnosis and
    # insemination event (in 'valid()' and 'cancel()')
    def update_state(self, validated_event):
        '''
        Sorted rules:
        - A cycle will be considered 'unmated'
          if weaning_event_id != False and weaning_event.state == 'validated'
          or if abort_event != False has abort_event.state == 'validated'
          or has not any validated event in insemination_event_ids.
        - A female will be considered 'lactating'
          if farrowing_event_id!=False and farrowing_event.state=='validated'
        - A female will be considered 'pregnant' if there are more than one
          diagnosis in 'validated' state and the last one has a positive result
        - A female will be considered 'mated' if there are any items in
          insemination_event_ids with 'validated' state.
        '''
        def check_event(event_to_check):
            return (type(event_to_check) == type(validated_event) and
                event_to_check == validated_event or
                event_to_check.state == 'validated')

        state = 'unmated'
        if (self.abort_event and check_event(self.abort_event) or
                self.weaning_event and check_event(self.weaning_event)):
            state = 'unmated'
        elif self.farrowing_event and check_event(self.farrowing_event):
            if self.farrowing_event.live > 0:
                state = 'lactating'
            else:
                state = 'unmated'
        elif self.pregnant:
            state = 'pregnant'
        else:
            for insemination_event in self.insemination_events:
                if check_event(insemination_event):
                    state = 'mated'
                    break
        self.state = state
        self.save()
        self.animal.update_state()
        return state

    def get_days_between_weaning_and_insemination(self, name):
        if not self.insemination_events:
            return None
        previous_cycles = self.search([
                ('animal', '=', self.animal.id),
                ('sequence', '<=', self.sequence),
                ('id', '!=', self.id)
                ],
            order=[
                ('sequence', 'DESC'),
                ('ordination_date', 'DESC'),
                ], limit=1)
        if not previous_cycles or (not previous_cycles[0].weaning_event and
                not previous_cycles[0].abort_event):
            return None
        previous_date = (previous_cycles[0].weaning_event.timestamp.date()
            if previous_cycles[0].weaning_event
            else previous_cycles[0].abort_event.timestamp.date())
        insemination_date = self.insemination_events[0].timestamp.date()
        return (insemination_date - previous_date).days

    @fields.depends('abort_event', 'diagnosis_events', 'farrowing_event')
    def on_change_with_pregnant(self, name=None):
        if self.abort_event:
            return False
        if not self.diagnosis_events:
            return False
        if self.farrowing_event:
            return False
        # relation to cycle is set on event validate so it's not required to
        # check the state
        return self.diagnosis_events[-1].result == 'positive'

    def get_farrowing_event_field(self, name):
        return (self.farrowing_event and getattr(self.farrowing_event, name)
            or 0)

    @fields.depends('foster_events')
    def on_change_with_fostered(self, name=None):
        return sum(e.quantity for e in self.foster_events)

    def get_weaned(self, name):
        return self.weaning_event and self.weaning_event.quantity or 0

    def get_removed(self, name):
        if not self.weaning_event:
            return None
        return self.live + self.fostered - self.weaned

    def get_lactating_days(self, name):
        if not self.farrowing_event or not self.weaning_event:
            return None
        return (self.weaning_event.timestamp.date() -
            self.farrowing_event.timestamp.date()).days

    @classmethod
    def create(cls, vlist):
        vlist = [v.copy() for v in vlist]
        for vals in vlist:
            if not vals.get('sequence') and vals.get('animal'):
                vals['sequence'] = cls.default_sequence(vals['animal'])
        return super(FemaleCycle, cls).create(vlist)


class EventUnion(UnionMixin, ModelSQL, ModelView):
    'Union between female cycles and events'
    __name__ = 'farm.animal.cycle.events'

    timestamp = fields.DateTime('Date & Time', required=True)
    cycle = fields.Function(fields.Many2One('farm.animal.female_cycle',
        'Cycle'), 'get_cycle')
    event_type = fields.Function(fields.Char('Event Type'), 'get_event_type')
    event_link = fields.Function(fields.Reference('Event',
        selection='get_fieldname'), 'get_event')
    animal = fields.Many2One('farm.animal', 'Animal')

    @classmethod
    def __setup__(cls):
        super(EventUnion, cls).__setup__()
        cls.__rpc__.update({
               'get_fieldname': RPC(),
                })
        cls._order.insert(0, ('timestamp', 'ASC'))

    @classmethod
    def _get_fieldname(cls):
        return ['farm.abort.event', 'farm.event.order',
            'farm.farrowing.event', 'farm.feed.event',
            'farm.foster.event', 'farm.insemination.event',
            'farm.medication.event', 'farm.move.event',
            'farm.pregnancy_diagnosis.event', 'farm.removal.event',
            'farm.semen_extraction.event', 'farm.transformation.event',
            'farm.weaning.event']

    @classmethod
    def get_fieldname(cls):
        pool = Pool()
        Model = pool.get('ir.model')
        models = cls._get_fieldname()
        models = Model.search([
                ('model', 'in', models),
                ])
        return [('', '')] + [(m.model, m.name) for m in models]

    def _get_event(self):
        cls = self.__class__
        model = cls.union_unshard(self.id)
        return model

    def get_event_type(self, name=None):
        pool = Pool()
        Model = pool.get('ir.model')
        model, = Model.search([
                ('model', '=', self._get_event().__class__.__name__),
                ], limit=1)
        return model.name

    def get_event(self, name=None):
        return str(self._get_event())

    def get_cycle(self, name=None):
        model = self._get_event()
        if hasattr(model, 'female_cycle') and model.female_cycle:
            return model.female_cycle.id
        return None

    @staticmethod
    def union_models():
        res = super(EventUnion, EventUnion).union_models()
        models = ['farm.abort.event', 'farm.event.order',
            'farm.farrowing.event', 'farm.feed.event',
            'farm.foster.event', 'farm.insemination.event',
            'farm.medication.event', 'farm.move.event',
            'farm.pregnancy_diagnosis.event', 'farm.removal.event',
            'farm.semen_extraction.event', 'farm.transformation.event',
            'farm.weaning.event']
        return res + models


class ChangeCycleObservationStart(ModelView):
    'Sets the value of the observation field of a cycle'
    __name__ = 'female.cycle.observation.start'

    cycle = fields.Many2One('farm.animal.female_cycle', 'Cycle',
        domain=[
            ('animal', '=', Eval('animal'))
            ],
        states={
            'required': True,
        },
        depends=['animal'],
        )
    observation = fields.Text('Observation', required=True)
    animal = fields.Many2One('farm.animal', 'Current animal',
        readonly=True, states={
            'invisible': True,
        })

    @staticmethod
    def default_cycle():
        Animal = Pool().get('farm.animal')
        active_id = Transaction().context.get('active_id')
        if active_id:
            active_animal = Animal(active_id)
            last_cycle = active_animal.cycles[-1]
            return last_cycle.id

    @staticmethod
    def default_animal():
        return Transaction().context.get('active_id')


class ChangeCycleObservation(Wizard):
    'Sets the value of the observation field of a cycle'
    __name__ = 'female.cycle.observation'

    start = StateView('female.cycle.observation.start',
        'farm.farm_cycle_observation_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'result', 'tryton-ok', default=True),
            ])
    result = StateTransition()

    def transition_result(self):
        cycle = self.start.cycle
        cycle.observations = self.start.observation
        cycle.save()
        return 'end'


class CreateFemaleStart(ModelView):
    'Create Female Start'
    __name__ = 'farm.create_female.start'

    number = fields.Char('Number')
    origin = fields.Selection(ANIMAL_ORIGIN, 'Origin', required=True)
    arrival_date = fields.Date('Arrival Date', required=True)
    birthdate = fields.Date('Birthdate',
        states={
            'readonly': Eval('origin') == 'raised',
            },
        depends=['origin'])
    initial_location = fields.Many2One('stock.location', 'Current Location',
        required=True,
        domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        context={
            'restrict_by_specie_animal_type': True,
            })
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True)
    breed = fields.Many2One('farm.specie.breed', 'Breed', required=True,
        domain=[
            ('specie', '=', Eval('specie')),
            ],
        depends=['specie'])
    cycles = fields.One2Many('farm.create_female.line', 'start', 'Cycles',
        order=[('insemination_date', 'ASC')])
    last_cycle_active = fields.Boolean('Last cycle active',
        help='If marked the moves for the last cycle will be created.')

    @staticmethod
    def default_specie():
        context = Transaction().context
        if context.get('active_model') == 'ir.ui.menu':
            pool = Pool()
            Menu = pool.get('ir.ui.menu')
            return Menu(context.get('active_id')).specie.id
        return context.get('specie')

    @staticmethod
    def default_origin():
        return 'raised'

    @fields.depends('origin', 'arrival_date')
    def on_change_with_birthdate(self):
        if self.origin == 'raised':
            return self.arrival_date
        return None


class CreateFemaleLine(ModelView):
    'Create Female Line'
    __name__ = 'farm.create_female.line'

    start = fields.Many2One('farm.create_female.start', 'Start', required=True)
    insemination_date = fields.Date('Insemination Date', required=True)
    second_insemination_date = fields.Date('Second Insemination Date')
    third_insemination_date = fields.Date('Third Insemination Date')
    abort = fields.Boolean('Aborted?')
    abort_date = fields.Date('Abort Date', states={
            'invisible': ~Eval('abort', False),
            }, depends=['abort'])
    farrowing_date = fields.Date('Farrowing Date', states={
            'required': Bool(Eval('weaning_date')),
            'invisible': Bool(Eval('abort')),
            }, depends=['weaning_date', 'abort'])
    live = fields.Integer('Live', states={
            'required': Bool(Eval('farrowing_date')),
            'invisible': Bool(Eval('abort')),
            }, depends=['farrowing_date', 'abort'])
    stillborn = fields.Integer('Stillborn', states={
            'invisible': Bool(Eval('abort')),
            }, depends=['abort'])
    mummified = fields.Integer('Mummified', states={
            'invisible': Bool(Eval('abort')),
            }, depends=['abort'])
    fostered = fields.Integer('Fostered', states={
            'invisible': Bool(Eval('abort')),
            }, depends=['abort'])
    to_weaning_quantity = fields.Function(
        fields.Integer('To Weaning Quantity'),
        'on_change_with_to_weaning_quantity')
    weaning_date = fields.Date('Weaning Date', states={
            'invisible': (Eval('abort', False) |
                (Eval('to_weaning_quantity', 0) == 0)),
            }, depends=['abort', 'to_weaning_quantity'])
    weaned_quantity = fields.Integer('Weaned Quantity', states={
            'required': Bool(Eval('weaning_date')),
            'invisible': (Eval('abort', False) |
                (Eval('to_weaning_quantity', 0) == 0)),
            }, depends=['weaning_date', 'abort', 'to_weaning_quantity'])

    @fields.depends('live', 'fostered')
    def on_change_with_to_weaning_quantity(self, name=None):
        return (self.live or 0) + (self.fostered or 0)


class CreateFemale(Wizard):
    'Create Female'
    __name__ = 'farm.create_female'
    start = StateView('farm.create_female.start',
        'farm.farm_create_female_start_view', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Create', 'result', 'tryton-ok', default=True),
            ])
    result = StateAction('farm.act_farm_animal_female')

    def do_result(self, action):
        pool = Pool()
        Abort = pool.get('farm.abort.event')
        Animal = pool.get('farm.animal')
        Cycle = pool.get('farm.animal.female_cycle')
        Farrowing = pool.get('farm.farrowing.event')
        Foster = pool.get('farm.foster.event')
        Insemination = pool.get('farm.insemination.event')
        Weaning = pool.get('farm.weaning.event')

        events_time = datetime.now().time()

        if (self.start.birthdate and self.start.birthdate >
                self.start.arrival_date):
            raise UserError(gettext('farm.birthdate_after_arrival',
                    birth=self.start.birthdate,
                    arrival=self.start.arrival_date))

        female = Animal()
        female.type = 'female'
        female.specie = self.start.specie
        female.breed = self.start.breed
        female.number = self.start.number
        female.arrival_date = self.start.arrival_date
        female.birthdate = self.start.birthdate
        female.origin = self.start.origin
        female.initial_location = self.start.initial_location
        female.save()
        female.cycles = []
        farm = female.initial_location.warehouse
        for sequence, line in enumerate(self.start.cycles):
            for field in ('live', 'stillborn', 'mummified', 'weaned_quantity'):
                value = getattr(line, field)
                if value and value < 0:
                    raise UserError(gettext('farm.greather_than_zero',
                        line=line.insemination_date))
            cycle = Cycle()
            cycle.sequence = sequence + 1
            cycle.animal = female
            cycle.ordination_date = datetime.combine(line.insemination_date,
                events_time)

            insemination_events = []
            last_insemination_date = None
            for insemination_date in (line.insemination_date,
                    line.second_insemination_date,
                    line.third_insemination_date):
                if not insemination_date:
                    continue
                if (not last_insemination_date or
                        last_insemination_date < insemination_date):
                    last_insemination_date = insemination_date
                if insemination_date < self.start.arrival_date:
                    raise UserError(gettext('farm.insemination_before_arrival',
                            insemination=insemination_date,
                            line=line.insemination_date,
                            arrival=self.start.arrival_date))
                if (line.farrowing_date and insemination_date >
                        line.farrowing_date):
                    raise UserError(gettext(
                            'farm.farrowing_before_insemination',
                            farrowing=line.farrowing_date,
                            line=line.insemination_date,
                            insemination=insemination_date))
                if line.abort_date and insemination_date > line.abort_date:
                    raise UserError(gettext('farm.abort_before_insemination',
                            abort=line.abort_date,
                            line=line.insemination_date,
                            insemination=insemination_date))
                insemination = Insemination()
                insemination.imported = True
                insemination.animal = female
                insemination.animal_type = 'female'
                insemination.farm = farm
                insemination.specie = self.start.specie
                insemination.timestamp = datetime.combine(insemination_date,
                    events_time)
                insemination.state = 'validated'
                insemination_events.append(insemination)
            cycle.insemination_events = insemination_events

            if line.abort:
                abort = Abort()
                abort.female_cycle = cycle
                abort.imported = True
                abort.animal = female
                abort.animal_type = 'female'
                abort.farm = farm
                abort.specie = self.start.specie
                abort.timestamp = datetime.combine(line.abort_date
                        if line.abort_date else last_insemination_date,
                    events_time)
                abort.state = 'validated'
                abort.save()
                cycle.abort_event = abort
            elif line.farrowing_date:
                cycle.save()
                farrowing = Farrowing()
                farrowing.female_cycle = cycle
                farrowing.imported = True
                farrowing.animal = female
                farrowing.animal_type = 'female'
                farrowing.farm = farm
                farrowing.specie = self.start.specie
                farrowing.timestamp = datetime.combine(line.farrowing_date,
                    events_time)
                farrowing.live = line.live
                farrowing.stillborn = line.stillborn
                farrowing.mummified = line.mummified
                farrowing.state = 'validated'
                cycle.farrowing_event = farrowing

                if line.fostered:
                    if line.fostered < 0 and abs(line.fostered) > line.live:
                        raise UserError(gettext('farm.more_fostered_than_live',
                            line=line.insemination_date))
                    foster = Foster()
                    foster.imported = True
                    foster.female_cycle = cycle
                    foster.animal = female
                    foster.animal_type = 'female'
                    foster.farm = farm
                    foster.specie = self.start.specie
                    foster.timestamp = datetime.combine(line.farrowing_date,
                        events_time)
                    foster.quantity = line.fostered
                    foster.state = 'validated'
                    cycle.foster_events = [foster]

                if line.weaning_date:
                    if line.weaning_date < line.farrowing_date:
                        raise UserError(gettext('farm.weaning_before_farrowing',
                                weaning=line.weaning_date,
                                line=line.insemination_date,
                                farrowing=line.farrowing_date))
                    if line.weaned_quantity > line.to_weaning_quantity:
                        raise UserError(gettext('farm.more_weaned_than_live',
                            line=line.insemination_date))

                    weaning = Weaning()
                    weaning.imported = True
                    weaning.female_cycle = cycle
                    weaning.animal = female
                    weaning.animal_type = 'female'
                    weaning.farm = farm
                    weaning.specie = self.start.specie
                    weaning.timestamp = datetime.combine(line.weaning_date,
                        events_time)
                    weaning.quantity = line.weaned_quantity
                    weaning.female_to_location = female.initial_location
                    weaning.weaned_to_location = female.initial_location
                    weaning.state = 'validated'
                    cycle.weaning_event = weaning
                elif (not self.start.last_cycle_active or
                        line != self.start.cycles[-1]):
                    if (line.live + (line.fostered or 0) -
                            (line.stillborn or 0) -
                            (line.mummified or 0) > 0):
                        raise UserError(gettext('farm.missing_weaning',
                            line=line.insemination_date))
            cycle.save()
            cycle.update_state(None)

        female = Animal(female.id)
        female.update_current_cycle()
        if self.start.last_cycle_active:
            cycle = female.current_cycle
            if cycle:
                if cycle.farrowing_event:
                    Farrowing.write([cycle.farrowing_event], {
                        'state': 'draft',
                        })
                    Farrowing.validate_event([cycle.farrowing_event])
                    Farrowing.write([cycle.farrowing_event], {
                        'imported': False,
                        })
                if cycle.foster_events:
                    Foster.write(list(cycle.foster_events), {
                        'state': 'draft',
                        })
                    Foster.validate_event(cycle.foster_events)
                    Foster.write(list(cycle.foster_events), {
                        'imported': False,
                        })
                if cycle.weaning_event:
                    Weaning.write([cycle.weaning_event], {
                        'state': 'draft',
                        })
                    Weaning.validate_event([cycle.weaning_event])
                    Weaning.write([cycle.weaning_event], {
                        'imported': False,
                        })

        action['views'].reverse()
        return action, {'res_id': [female.id]}

#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Equal, Eval, Greater, Id, Not
from trytond.transaction import Transaction
from trytond.pool import Pool, PoolMeta

__all__ = ['Tag', 'Animal', 'AnimalTag', 'AnimalWeight', 'Male', 'Female',
    'FemaleCycle']
__metaclass__ = PoolMeta

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
        cls._sql_constraints += [
            ('name_uniq', 'UNIQUE (name)',
                'The Name of the Tag must be unique.'),
            ]


class AnimalMixin:
    @classmethod
    def _create_and_done_first_stock_move(cls, records):
        """
        It creates the first stock.move for animal's lot, and then confirms,
        assigns and set done it to get stock in initial location (Farm).
        """
        Move = Pool().get('stock.move')

        new_moves = []
        for record in records:
            move = record._get_first_move()
            move.save()
            new_moves.append(move)

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
                self.raise_user_error('missing_supplier_location',
                    company.party.rec_name)
        else:  # raised
            from_location = self.initial_location.warehouse.production_location
            if not from_location:
                self.raise_user_error('missing_production_location',
                    self.initial_location.warehouse.rec_name)

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
            # TODO: es suficient agafar el cost_price del producte o s'hauria
            # de permetre a l'usuari especificar un preu de cost inicial?
            unit_price=self.lot.product.cost_price,
            origin=self)


class Animal(ModelSQL, ModelView, AnimalMixin):
    "Farm Animal"
    __name__ = 'farm.animal'

    type = fields.Selection([
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
        ], 'Type', required=True, readonly=True, select=True)
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True, select=True)
    breed = fields.Many2One('farm.specie.breed', 'Breed', required=True,
        domain=[('specie', '=', Eval('specie'))], depends=['specie'])
    lot = fields.One2One('stock.lot-farm.animal', 'animal', 'lot',
        string='Lot', required=True, readonly=True, domain=[
            ('animal_type', '=', Eval('type')),
        ], depends=['type'])
    number = fields.Function(fields.Char('Number'),
        'get_number', 'set_number')
    # location is updated in do() of stock.move
    location = fields.Many2One('stock.location', 'Location', readonly=True,
        domain=[('type', '!=', 'warehouse')],
        help='Indicates where the animal currently resides.')
    farm = fields.Function(fields.Many2One('stock.location', 'Current Farm',
            on_change_with=['location'], depends=['location']),
        'on_change_with_farm', searcher='search_farm')
    origin = fields.Selection([
            ('purchased', 'Purchased'),
            ('raised', 'Raised'),
            ], 'Origin', required=True, readonly=True,
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
        required=True, domain=[('type', '=', 'storage')],
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
            'Current Weight', on_change_with=['weights']),
        'on_change_with_current_weight')
    tags = fields.Many2Many('farm.animal-farm.tag', 'animal', 'tag', 'Tags')
    notes = fields.Text('Notes')
    active = fields.Boolean('Active')
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

    # We can't use the 'required' attribute in field because it's
    # checked on view before execute 'create()' function where this
    # field is filled in.
    @classmethod
    def __setup__(cls):
        super(Animal, cls).__setup__()
        cls._error_messages.update({
                'missing_supplier_location': ('Supplier Location of '
                    'company\'s party "%s" is empty but it is required to '
                    'create the arrival stock move for a new animal.'),
                'missing_production_location': ('The warehouse location "%s" '
                    'doesn\'t have set production location, but it is '
                    'required to create the arrival stock move for a new '
                    'animal.'),
                'no_farm_specie_farm_line_available': ('The specified farm '
                    '"%(farm)s" is not configured as farm with '
                    '"%(animal_type)s" for the specie "%(specie)s"'),
                'no_sequence_in_farm_line': ('The required sequence '
                    '"%(sequence_field)s" is not set in the farm line '
                    '"%(farm_line)s".'),
                'invalid_animal_destination': ('The event "%(event)s" is '
                    'trying to move the animal "%(animal)s" to location '
                    '"%(location)s", but the location\'s warehouse is not '
                    'configured as a farm for this kind of animals.'),
                'no_product_in_specie': ('The required product '
                    '"%(product_field)s" is not set in the farm "%(farm)s".'),
                })

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

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
        name = self.lot.number
        if not self.active:
            name += ' (*)'
        return name

    @classmethod
    def search_rec_name(cls, name, clause):
        return [('lot.number',) + clause[1:]]

    def get_number(self, name):
        return self.lot.number

    @classmethod
    def set_number(cls, animals, name, value):
        Lot = Pool().get('stock.lot')
        lots = [animal.lot for animal in animals if animal.lot]
        if lots:
            Lot.write(lots, {
                    'number': value,
                    })

    def on_change_with_farm(self, name=None):
        return (self.location and self.location.warehouse and
            self.location.warehouse.id or None)

    @classmethod
    def search_farm(cls, name, clause):
        return [('location.warehouse',) + tuple(clause[1:])]

    def on_change_with_current_weight(self, name=None):
        if self.weights:
            return self.weights[0].id

    def check_in_location(self, location, timestamp):
        with Transaction().set_context(
                locations=[location.id],
                stock_date_end=timestamp.date()):
            return self.lot.quantity == 1

    def check_allowed_location(self, location, event_rec_name):
        for farm_line in self.specie.farm_lines:
            if farm_line.farm.id == location.warehouse.id:
                if getattr(farm_line, 'has_%s' % self.type):
                    return
        self.raise_user_error('invalid_animal_destination', {
                'event': event_rec_name,
                'animal': self.rec_name,
                'location': location.rec_name,
                })

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
            logging.getLogger(cls.__name__).debug("Create vals: %s" % vals)
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
            cls.raise_user_error('no_farm_specie_farm_line_available', {
                    'farm': Location(farm_id).rec_name,
                    'animal_type': type,
                    'specie': Specie(specie_id).rec_name,
                    })
        farm_line, = farm_lines
        sequence = getattr(farm_line, sequence_fieldname, False)
        if not sequence:
            cls.raise_user_error('no_sequence_in_farm_line', {
                    'sequence_field': getattr(FarmLine,
                            sequence_fieldname).string,
                    'farm_line': farm_line.rec_name,
                    })
        return Sequence.get_id(sequence.id)

    @classmethod
    def _get_lot_values(cls, animal_vals, create):
        """
        Prepare values to create the stock.lot for the new animal.
        animal_vals: dictionary with values to create farm.animal
        It returns a dictionary with values to create stock.lot
        """
        Specie = Pool().get('farm.specie')
        if not animal_vals:
            return {}
        specie = Specie(animal_vals['specie'])
        product_fieldname = '%s_product' % animal_vals['type']
        product = getattr(specie, product_fieldname, False)
        if not product:
            cls.raise_user_error('no_product_in_specie', {
                    'product_field': getattr(Specie, product_fieldname).string,
                    'specie': specie.rec_name,
                    })
        return {
            'number': animal_vals['number'],
            'product': product.id,
            'animal_type': animal_vals['type'],
            }

    @classmethod
    def delete(cls, animals):
        pool = Pool()
        Lot = pool.get('stock.lot')

        lots = [a.lot for a in animals]
        result = super(Animal, cls).delete(animals)
        if lots:
            Lot.delete(lots)
        return result


class AnimalTag(ModelSQL):
    'Animal - Tag'
    __name__ = 'farm.animal-farm.tag'
    animal = fields.Many2One('farm.animal', 'Animal', required=True)
    tag = fields.Many2One('farm.tag', 'Tag', required=True)


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
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']),
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

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2


class Male:
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


class Female:
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
            help='Number of days from last Insemination Event. -1 if there '
            'isn\'t any Insemination Event.'),
        'get_days_from_insemination', searcher='search_days_from_insemination')
    last_produced_group = fields.Function(fields.Many2One('farm.animal.group',
            'Last Produced Group', domain=[
                ('specie', '=', Eval('specie')),
                ], depends=['specie']),
        'get_last_produced_group')
    days_from_farrowing = fields.Function(fields.Integer('Unpregnant Days',
            help='Number of days from last Farrowing Event. -1 if there '
            'isn\'t any Farrowing Event.'),
        'get_days_from_farrowing', searcher='search_days_from_farrowing')

    @staticmethod
    def default_state():
        '''
        Specific for Female animals.
        '''
        if Transaction().context.get('animal_type') == 'female':
            return 'prospective'
        return None

    def is_lactating(self):
        return (self.current_cycle and self.current_cycle.state == 'lactating'
            or False)

    # TODO: call when cycle is created, deleted or its ordination_date or
    # sequence are modifyied
    def update_current_cycle(self):
        current_cycle = self.cycles and self.cycles[-1].id or None
        self.current_cycle = current_cycle
        self.save()
        return current_cycle

    # TODO: call in removal event, when cycle is added (but probably it's
    # called from cycle)
    def update_state(self):
        if self.type != 'female':
            return
        if (self.removal_date and self.removal_date <= date.today()):
            state = 'removed'
        elif (not self.cycles or len(self.cycles) == 1 and
                not self.cycles[0].weaning_event and
                self.cycles[0].state == 'unmated'):
            state = 'prospective'
        elif self.current_cycle.state == 'unmated':
            state = 'unmated'
        else:
            state = 'mated'
        self.state = state
        self.save()
        return state

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
                ('produced_group', '!=', False),
                ],
            order=[
                ('timestamp', 'DESC'),
                ], limit=1)
        if last_farrowing_events:
            return last_farrowing_events[0].produced_group
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
    _rec_name = 'sequence'
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
    state = fields.Selection([
            ('mated', 'Mated'),
            ('pregnant', 'Pregnant'),
            ('lactating', 'Lactating'),
            ('unmated', 'Unmated'),
            ], 'State', readonly=True, required=True)
    # Female events fields
    insemination_events = fields.One2Many('farm.insemination.event',
            'female_cycle', 'Insemination Events')
    days_between_weaning_and_insemination = fields.Function(
        fields.Integer('Unmated Days', help='Number of days between previous '
            'Weaning Event and first Insemination Event.'),
        'get_days_between_weaning_and_insemination')
    diagnosis_events = fields.One2Many('farm.pregnancy_diagnosis.event',
            'female_cycle', 'Diagnosis Events')
    pregnant = fields.Function(fields.Boolean('Pregnant',
            on_change_with=['diagnosis_events', 'abort_event'],
            depends=['diagnosis_events', 'abort_event'],
            help='A female will be considered pregnant if there are more than'
            ' one diagnosis and the last one has a positive result.'),
        'on_change_with_pregnant')
    abort_event = fields.One2One('farm.abort.event-farm.animal.female_cycle',
        'cycle', 'event', string='Abort Event', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], depends=['animal'])
    farrowing_event = fields.One2One(
        'farm.farrowing.event-farm.animal.female_cycle', 'cycle', 'event',
        string='Farrowing Event', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], depends=['animal'])
    live = fields.Function(fields.Integer('Live'),
        'get_farrowing_event_field')
    dead = fields.Function(fields.Integer('Dead'),
        'get_farrowing_event_field')
    foster_events = fields.One2Many('farm.foster.event', 'female_cycle',
        'Foster Events')
    fostered = fields.Function(fields.Integer('Fostered',
            on_change_with=['foster_events'], depends=['foster_events'],
            help='Diference between Fostered Input and Output. A negative '
            'number means that he has given more than taken.'),
        'on_change_with_fostered')
    weaning_event = fields.One2One(
        'farm.weaning.event-farm.animal.female_cycle', 'cycle', 'event',
        string='Weaning Event', readonly=True, domain=[
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
        logging.getLogger(self.__name__).debug("FemaleCycle.get_rec_name()")
        state_labels = FemaleCycle.state.selection
        logging.getLogger(self.__name__).debug("state_labels: ", state_labels)
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
                ('ordination_date', '<', self.ordination_date)
                ],
            order=[
                ('sequence', 'DESC'),
                ('ordination_date', 'DESC'),
                ], limit=1)
        if not previous_cycles or not previous_cycles[0].weaning_event:
            return None
        weaning_date = previous_cycles[0].weaning_event.timestamp.date()
        insemination_date = self.insemination_events[0].timestamp.date()
        return (insemination_date - weaning_date).days

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

    def on_change_with_fostered(self, name=None):
        return sum(e.quantity for e in self.foster_events)

    def get_weaned(self, name):
        return self.weaning_event and self.weaning_event.quantity or 0

    def get_removed(self, name):
        return self.live + self.fostered + self.weaned

    def get_days_between_farrowing_weaning(self, name):
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

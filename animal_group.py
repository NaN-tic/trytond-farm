#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from datetime import date, datetime
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, fields
from trytond.pyson import Equal, Eval, Greater, Id, Not
from trytond.transaction import Transaction
from trytond.pool import Pool

from .animal import AnimalMixin

__all__ = ['AnimalGroup', 'AnimalGroupTag', 'AnimalGroupWeight']


class AnimalGroup(ModelSQL, ModelView, AnimalMixin):
    'Group of Farm Animals'
    __name__ = 'farm.animal.group'

    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True)
    breed = fields.Many2One('farm.specie.breed', 'Breed', required=True,
        domain=[('specie', '=', Eval('specie'))], depends=['specie'])
    lot = fields.One2One('stock.lot-farm.animal.group', 'animal_group',
        'lot', 'Lot', required=True, readonly=True,
        domain=[('animal_type', '=', 'group')])
    number = fields.Function(fields.Char('Number'),
        'get_number', 'set_number')
    farms = fields.Function(fields.Many2Many('stock.location', None, None,
            'Current Farms', readonly=True, domain=[
                ('type', '=', 'warehouse'),
                ],
            help='Farms where this group can be found. It is used for access '
            'management.'),
        'get_farms', searcher='search_farms')
    origin = fields.Selection([
            ('purchased', 'Purchased'),
            ('raised', 'Raised'),
        ], 'Origin', required=True, readonly=True,
        help='Raised means that this group was born in the farm. Otherwise, '
        'it was purchased.')
    arrival_date = fields.Date('Arrival Date', states={
            'readonly': Greater(Eval('id', 0), 0),
            }, depends=['id'],
        help="The date this group arrived (if it was purchased) or when it "
        "was born.")
    purchase_shipment = fields.Many2One('stock.shipment.in',
        'Purchase Shipment', readonly=True,
        states={'invisible': Not(Equal(Eval('origin'), 'purchased'))},
        depends=['origin'])
    initial_location = fields.Many2One('stock.location', "Initial Location",
        required=True, domain=[('type', '=', 'storage')],
        states={'readonly': Greater(Eval('id', 0), 0)}, depends=['id'],
        context={'restrict_by_specie_animal_type': True},
        help="The Location where the group was reached or where it was "
        "allocated when it was purchased.\nIt is used as historical "
        "information and to get Serial Number.")
    initial_quantity = fields.Integer('Initial Quantity', required=True,
        states={'readonly': Greater(Eval('id', 0), 0)}, depends=['id'],
        help="The number of animals in group when it was reached or "
        "purchased.\nIt is used as historical information and to create the "
        "initial move.")
    removal_date = fields.Date('Removal Date', readonly=True)
    weights = fields.One2Many('farm.animal.group.weight', 'group',
        'Weight Records', readonly=True)
    current_weight = fields.Function(fields.Many2One(
            'farm.animal.group.weight', 'Current Weight',
            on_change_with=['weights']),
        'on_change_with_current_weight')
    tags = fields.Many2Many('farm.animal.group-farm.tag', 'group', 'tag',
        'Tags')
    notes = fields.Text('Notes')
    active = fields.Boolean('Active')

#    # TODO: Extra
#    'type': fields.selection([('static','Static'),('dynamic','Dynamic')],
#        help='Static = all-in, all-out. Dynamic = continuous flow')
#    # Stages a dynamic group may be in.
#    'stage': fields.many2one('farm.animal.group.stage')

    @classmethod
    def __setup__(cls):
        super(AnimalGroup, cls).__setup__()
        cls._sql_constraints += [
            ('initial_quantity_positive', 'check (initial_quantity > 0)',
                'In Groups, the initial quantity must be positive (greater or '
                'equals 1)'),
            ]
        cls._error_messages.update({
                'missing_supplier_location': ('Supplier Location of '
                    'company\'s party "%s" is empty but it is required to '
                    'create the arrival stock move for a new group.'),
                'missing_production_location': ('The warehouse location "%s" '
                    'doesn\'t have set production location, but it is '
                    'required to create the arrival stock move for a new '
                    'group.'),
                'no_farm_specie_farm_line_available': ('The specified farm '
                    '"%(farm)s" is not configured as farm with groups for '
                    'the specie "%(specie)s".'),
                'invalid_group_destination': ('The event "%(event)s" is '
                    'trying to move the group "%(group)s" to location '
                    '"%(location)s", but the location\'s warehouse is not '
                    'configured as a farm for this kind of animals.'),
                })

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_origin():
        return 'purchased'

    @staticmethod
    def default_arrival_date():
        return date.today()

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
    def set_number(cls, instances, name, value):
        Lot = Pool().get('stock.lot')
        lots = [group.lot for group in instances if group.lot]
        if lots:
            Lot.write(lots, {
                    'number': value,
                    })

    @classmethod
    def get_farms(cls, animal_groups, name):
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')

        warehouses = Location.search([
            ('type', '=', 'warehouse'),
            ])
        qbl = Lot.quantity_by_location([ag.lot for ag in animal_groups],
            location_ids=[w.id for w in warehouses], with_childs=True)
        res = {}
        for animal_group in animal_groups:
            ag_lot_id = animal_group.lot.id
            res[animal_group.id] = [l for l in qbl[ag_lot_id]
                    if qbl[ag_lot_id][l] > 0.0]
        return res

    @classmethod
    def search_farms(cls, name, domain=None):
        pool = Pool()
        Location = pool.get('stock.location')
        Product = pool.get('product.product')
        Specie = pool.get('farm.specie')

        if not domain:
            return []

        specie_id = cls.default_specie()
        product_ids = None
        if specie_id:
            specie = Specie(specie_id)
            if not specie.group_product:
                return []
            product_ids = [specie.group_product.id]

            specie_warehouse_ids = [l.farm.id for l in specie.farm_lines
                if l.has_group]
            warehouses = Location.search([
                ('id', 'in', specie_warehouse_ids),
                ('type', '=', 'warehouse'),
                ('warehouse',) + domain[1:],
                ])
        else:
            warehouses = Location.search([
                ('type', '=', 'warehouse'),
                ('warehouse',) + domain[1:],
                ])
        if not warehouses:
            return []

        pbl = Product.products_by_location([w.id for w in warehouses],
            product_ids=product_ids, with_childs=True,
            grouping=('product', 'lot'))

        lot_ids = set()
        for (location_id, product_id, lot_id), quantity in pbl.iteritems():
            if quantity > 0.0:
                lot_ids.add(lot_id)

        return [('lot', 'in', list(lot_ids))]

    def on_change_with_current_weight(self, name=None):
        if self.weights:
            return self.weights[0].id

    def check_in_location(self, location, timestamp, quantity=1):
        with Transaction().set_context(
                locations=[location.id],
                stock_date_end=timestamp.date()):
            return self.lot.quantity >= quantity

    def check_allowed_location(self, location, event_rec_name):
        for farm_line in self.specie.farm_lines:
            if farm_line.farm.id == location.warehouse.id:
                if farm_line.has_group:
                    return
        self.raise_user_error('invalid_group_destination', {
                'event': event_rec_name,
                'group': self.rec_name,
                'location': location.rec_name,
                })

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
            'lot': False,
            'farms': False,
            'origin': False,
            'arrival_date': False,
            'purchase_shipment': False,
            'removal_date': False,
            'weights': False,
            })
        return super(AnimalGroup, cls).copy(records, default)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Location = pool.get('stock.location')
        Lot = pool.get('stock.lot')

        context = Transaction().context
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('specie'):
                vals['specie'] = context.get('specie')
            if not vals.get('number'):
                location = Location(vals['initial_location'])
                vals['number'] = cls._calc_number(vals['specie'],
                        location.warehouse.id)
            if vals.get('lot'):
                lot = Lot(vals['lot'])
                Lot.write([lot], cls._get_lot_values(vals, False))
            else:
                new_lot, = Lot.create([cls._get_lot_values(vals, True)])
                vals['lot'] = new_lot.id
        new_groups = super(AnimalGroup, cls).create(vlist)
        if not context.get('no_create_stock_move'):
            cls._create_and_done_first_stock_move(new_groups)
        return new_groups

    @classmethod
    def _calc_number(cls, specie_id, farm_id):
        pool = Pool()
        FarmLine = pool.get('farm.specie.farm_line')
        Location = pool.get('stock.location')
        Sequence = pool.get('ir.sequence')
        Specie = pool.get('farm.specie')

        farm_lines = FarmLine.search([
                ('specie', '=', specie_id),
                ('farm', '=', farm_id),
                ('has_group', '=', True),
                ])
        if not farm_lines:
            cls.raise_user_error('no_farm_specie_farm_line_available', {
                    'farm': Location(farm_id).rec_name,
                    'specie': Specie(specie_id).rec_name,
                    })
        sequence = farm_lines[0].group_sequence
        return sequence and Sequence.get_id(sequence.id) or ''

    @classmethod
    def _get_lot_values(cls, group_vals, create):
        """
        Prepare values to create the stock.lot for the new group.
        group_vals: dictionary with values to create farm.animal.group
        It returns a dictionary with values to create stock.lot
        """
        Specie = Pool().get('farm.specie')
        if not group_vals:
            return {}
        specie = Specie(group_vals['specie'])
        return {
            'number': group_vals['number'],
            'product': (specie.group_product and specie.group_product.id or
                None),
            'animal_type': 'group',
            }

    @classmethod
    def delete(cls, groups):
        pool = Pool()
        Lot = pool.get('stock.lot')

        lots = [g.lot for g in groups]
        result = super(AnimalGroup, cls).delete(groups)
        if lots:
            Lot.delete(lots)
        return result


class AnimalGroupTag(ModelSQL):
    'Animal Group - Tag'
    __name__ = 'farm.animal.group-farm.tag'
    group = fields.Many2One('farm.animal.group', 'Group', required=True)
    tag = fields.Many2One('farm.tag', 'Tag', required=True)


class AnimalGroupWeight(ModelSQL, ModelView):
    'Farm Animal Group Weight Record'
    __name__ = 'farm.animal.group.weight'
    _order = ('timestamp', 'DESC')

    group = fields.Many2One('farm.animal.group', 'Group', required=True,
        ondelete='CASCADE')
    timestamp = fields.DateTime('Date & Time', required=True)
    quantity = fields.Integer('Number of individuals', required=True)
    uom = fields.Many2One('product.uom', "UoM", required=True,
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

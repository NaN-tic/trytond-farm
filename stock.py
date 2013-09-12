#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import datetime
from collections import defaultdict
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, fields, Workflow
from trytond.pyson import Equal, Eval, Not, Or
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

__all__ = ['Location', 'LocationSiloLocation', 'Lot', 'LotAnimal',
    'LotAnimalGroup', 'Move']
__metaclass__ = PoolMeta


class Lot:
    __name__ = 'stock.lot'

    animal_type = fields.Selection([
            (None, ''),
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
            ('group', 'Group'),
            ], 'Animal Type', readonly=True)
    animal = fields.One2One('stock.lot-farm.animal', 'lot', 'animal',
        string='Animal', readonly=True,
        states={'invisible': Equal(Eval('animal_type'), 'group')},
        depends=['animal_type'])
    animal_group = fields.One2One('stock.lot-farm.animal.group', 'lot',
        'animal_group', string='Group', readonly=True,
        states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            }, depends=['animal_type'])

    #TODO aquestes restriccions les deixem aqui o les passem a 'animal'
    # (i group?). Afegir-ho a la tasca
    # Add constraint that ensures that if the stock lot is of
    # animal_type in (male, female, individual), the lot can only be
    # in a single non-virtual location at any given point in time.
    # Consider restricting only one unit should be available at any
    # given time (may not be easy because then the order in which stock
    # moves are done may be relevant).

    # Consider making configurable per specie if that constraint should
    # apply to 'group' too but with more than one unit.

    @staticmethod
    def default_animal_type():
        return ''

    def get_rec_name(self, name):
        rec_name = super(Lot, self).get_rec_name(name)
        if not self.animal_type:
            return rec_name
        if self.animal_type == 'group' and self.animal_group:
            if not self.animal_group.active:
                rec_name += " (*)"
        elif self.animal:
            if not self.animal.active:
                rec_name += " (*)"
        return rec_name

    @classmethod
    def quantity_by_location(cls, lots, location_ids, with_childs=False):
        Product = Pool().get('product.product')

        pbl = Product.products_by_location(location_ids,
            product_ids=list(set(l.product.id for l in lots)),
            with_childs=with_childs,
            grouping=('product', 'lot'))

        quantities = {}
        for (location_id, product_id, lot_id), quantity in pbl.iteritems():
            if lot_id is None:
                continue
            lot_quantities = quantities.setdefault(lot_id, {})
            lot_quantities[location_id] = quantity
        return quantities


class LotAnimal(ModelSQL):
    "Lot - Animal"
    __name__ = 'stock.lot-farm.animal'

    lot = fields.Many2One('stock.lot', 'Lot', required=True,
        ondelete='RESTRICT', select=True)
    animal = fields.Many2One('farm.animal', 'Animal', required=True,
        ondelete='RESTRICT', select=True)

    @classmethod
    def __setup__(cls):
        super(LotAnimal, cls).__setup__()
        cls._sql_constraints += [
            ('lot_unique', 'UNIQUE(lot)', 'The Lot must be unique.'),
            ('animal_unique', 'UNIQUE(animal)', 'The Animal must be unique.'),
            ]


class LotAnimalGroup(ModelSQL):
    "Lot - Animal Group"
    __name__ = 'stock.lot-farm.animal.group'

    lot = fields.Many2One('stock.lot', 'Lot', required=True,
        ondelete='RESTRICT', select=True)
    animal_group = fields.Many2One('farm.animal.group', 'Animal Group',
        required=True, ondelete='RESTRICT', select=True)

    @classmethod
    def __setup__(cls):
        super(LotAnimalGroup, cls).__setup__()
        cls._sql_constraints += [
            ('lot_unique', 'UNIQUE(lot)', 'The lot must be unique.'),
            ('animal_group_unique', 'UNIQUE(animal_group)',
                'The group must be unique.'),
            ]


class Location:
    __name__ = 'stock.location'

    silo = fields.Boolean('Silo', select=True,
        help='Indicates that the location is a silo.')
    current_lot = fields.Function(fields.Many2One('stock.lot',
            'Current Lot', states={
                'invisible': Not(Eval('silo', False)),
                }, depends=['silo']),
        'get_current_lot')
    locations_to_fed = fields.Many2Many('stock.location.silo-stock.location',
        'silo', 'location', 'Locations to fed', domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states={
            'invisible': Not(Eval('silo', False)),
            }, depends=['silo'],
        help='Indicates the locations the silo feeds. Note that this will '
        'only be a default value.')
    feed_inventory_lines = fields.One2Many('farm.feed.inventory.line',
        'dest_location', 'Input Inventory Lines', readonly=True, states={
            'invisible': Or(Not(Equal(Eval('type'), 'storage')),
                    Eval('silo', False)),
            }, depends=['type', 'silo'])

    @staticmethod
    def default_silo():
        return False

    @classmethod
    def get_current_lot(cls, locations, name):
        '''
        It suposes that a silo is never filled by same lot two times.
        If letters represent lots and list represents the silo, this case never
        happens: [A, B, A, C]
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')

        current_lots = {}.fromkeys([l.id for l in locations], None)

        silo_locations = [l for l in locations if l.silo]
        if not silo_locations:
            return current_lots

        pbl = Product.products_by_location([l.id for l in silo_locations],
            with_childs=False, grouping=('product', 'lot'))

        location_lots = defaultdict(set)
        for (location_id, product_id, lot_id), quantity in pbl.iteritems():
            if (lot_id is not None and
                    Decimal(str(quantity)).quantize(Decimal('0.01'))
                    > Decimal('0.01')):
                location_lots[location_id].add(lot_id)

        for location in silo_locations:
            if not location_lots[location.id]:
                continue
            first_moves = Move.search([
                    ('lot', 'in', list(location_lots[location.id])),
                    ('state', '=', 'done'),
                    ('to_location', '=', location.id),
                    ], offset=0, limit=1,
                order=[('effective_date', 'ASC'), ('id', 'ASC')])
            current_lots[location.id] = first_moves and first_moves[0].lot.id
        return current_lots

    @classmethod
    def search(cls, args, offset=0, limit=None, order=None, count=False,
            query=False):
        FarmLine = Pool().get('farm.specie.farm_line')

        args = args[:]
        context = Transaction().context
        if context.get('restrict_by_specie_animal_type'):
            specie_id = context.get('specie')
            animal_type = context.get('animal_type')
            farm_lines = FarmLine.search([
                    ('specie', '=', specie_id),
                    ('has_' + animal_type, '=', True),
                    ])
            if not farm_lines:
                return []
            storage_locations = [fl.farm.storage_location.id
                for fl in farm_lines]
            #args.append(('parent', 'child_of', storage_locations))
            args += [[
                'OR', [
                        ('parent', 'child_of', storage_locations),
                    ], [
                        ('id', 'in', [fl.farm.id for fl in farm_lines]),
                    ],
                ]]
        res = super(Location, cls).search(args, offset=offset, limit=limit,
            order=order, count=count, query=query)
        return res

    def get_lot_fifo(self, stock_date=None, to_uom=None):
        '''
        Only for 'silo' locations, it returns the list of tuples of lots in
        location at specified date and their available stock in specified UOM,
        sorted by input date (FIFO):
            [(<lot instance>, <available quantity in 'to_uom'>)]

        It suposes that a silo is never filled by same lot two times.
        If letters represent lots and list represents the silo, this case never
        happens: [A, B, A, C]

        It doesn't computes child locations, raise an exception if some product
        in location dosen't have a compatible UoM and returns a Decimal.

        If 'stock_date' is not specified, today is used.
        If 'to_uom' is not specified, it is returned in the default_uom of the
            product of each lot.
        '''
        pool = Pool()
        Move = pool.get('stock.move')
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        if not self.silo:
            return []

        if stock_date is None:
            stock_date = datetime.date.today()

        with Transaction().set_context(stock_date_end=stock_date):
            pbl = Product.products_by_location([self.id], with_childs=False,
                grouping=('product', 'lot'))

        lot_quantities = {}
        for (location_id, product_id, lot_id), quantity in pbl.iteritems():
            if lot_id is not None and quantity >= 0.0:
                lot_quantities[lot_id] = quantity

        lot_fifo = []
        moves = Move.search([
                ('lot', 'in', lot_quantities.keys()),
                ('state', '=', 'done'),
                ('to_location', '=', self.id),
                ('effective_date', '<=', stock_date),
                ], offset=0,
            order=[
                ('effective_date', 'ASC'),
                ('id', 'ASC'),
                ])
        for move in moves:
            if to_uom is None or move.product.default_uom.id == to_uom.id:
                quantity = lot_quantities[move.lot.id]
            else:
                assert (move.product.default_uom.category.id ==
                    to_uom.category.id), ('Invalid to_uom "%s" in '
                    'Location.get_lot_fifo(). Incompatible with default UoM '
                    'of product "%s" in silo "%s"'
                    % (to_uom.rec_name, move.product.rec_name, self.rec_name))
                quantity = Uom.compute_qty(move.product.default_uom,
                    lot_quantities[move.lot.id], to_uom, round=True)
            lot_fifo.append((move.lot, Decimal(str(quantity))))
        return lot_fifo

    def get_total_quantity(self, stock_date=None, to_uom=None):
        '''
        Returns the total amount of any product in location at specified date
        in the specified UOM.
        It doesn't computes child locations, raise an exception if some product
        in location dosen't have a compatible UoM and returns a Decimal.
        '''
        pool = Pool()
        Product = pool.get('product.product')
        Uom = pool.get('product.uom')

        if stock_date is None:
            stock_date = datetime.date.today()

        with Transaction().set_context(stock_date_end=stock_date):
            pbl = Product.products_by_location([self.id], with_childs=False)

        total_quantity = Decimal('0.0')
        for (location_id, product_id), quantity in pbl.iteritems():
            product = Product(product_id)
            if to_uom is not None and product.default_uom.id != to_uom.id:
                assert (product.default_uom.category.id ==
                    to_uom.category.id), ('Invalid to_uom "%s" in '
                    'Location.get_total_quantity(). Incompatible with default '
                    'UoM of product "%s" in location "%s"'
                    % (to_uom.rec_name, product.rec_name, self.rec_name))
                quantity = Uom.compute_qty(product.default_uom, quantity,
                    to_uom, round=True)
            total_quantity += Decimal(str(quantity))
        return total_quantity


class LocationSiloLocation(ModelSQL):
    'Silo - Location'
    __name__ = 'stock.location.silo-stock.location'
    silo = fields.Many2One('stock.location', 'Silo', ondelete='CASCADE',
        required=True, select=True)
    location = fields.Many2One('stock.location', 'Location',
        ondelete='CASCADE', required=True, select=True)


class Move:
    __name__ = 'stock.move'

    @classmethod
    def _get_origin(cls):
        models = super(Move, cls)._get_origin()
        models += [
            'farm.animal',
            'farm.animal.group',
            'farm.move.event',
            'farm.transformation.event',
            'farm.removal.event',
            'farm.feed.event',
            'farm.medication.event',
            'farm.semen_extraction.event',
            'farm.semen_extraction.delivery',
            'farm.insemination.event',
            'farm.farrowing.event',
            'farm.foster.event',
            'farm.weaning.event',
            ]
        return models

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def do(cls, moves):
        res = super(Move, cls).do(moves)
        for move in moves:
            if (not move.lot or not move.lot.animal_type or
                    move.lot.animal_type == 'group'):
                continue
            move.lot.animal.location = move.to_location.id
            move.lot.animal.save()
        return res

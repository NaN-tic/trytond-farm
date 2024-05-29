#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import datetime
from collections import defaultdict
from decimal import Decimal

from trytond.model import ModelView, ModelSQL, fields, Workflow
from trytond.pyson import Equal, Eval, Not
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from sql import Table


class Lot(metaclass=PoolMeta):
    __name__ = 'stock.lot'

    animal_type = fields.Selection([
            (None, ''),
            ('male', 'Male'),
            ('female', 'Female'),
            ('individual', 'Individual'),
            ('group', 'Group'),
            ], 'Animal Type', readonly=True)
    animal = fields.Many2One('farm.animal', 'Animal', readonly=True,
        states={'invisible': Equal(Eval('animal_type'), 'group')})
    animal_group = fields.One2One('stock.lot-farm.animal.group', 'lot',
        'animal_group', string='Group', readonly=True,
        states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            })

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

    @classmethod
    def __register__(cls, module_name):
        table = cls.__table_handler__(module_name)
        sql_table = cls.__table__()
        update_animal = False
        if not table.column_exist('animal'):
            update_animal = True
        super().__register__(module_name)
        table = cls.__table_handler__(module_name)
        if update_animal:
            sql_table_animal_lot = 'stock_lot-farm_animal'
            if table.table_exist(sql_table_animal_lot):
                sql_table_animal_lot = Table(sql_table_animal_lot)
                cursor = Transaction().connection.cursor()
                cursor.execute(*sql_table_animal_lot.select(
                    sql_table_animal_lot.animal, sql_table_animal_lot.lot))
                for animal_id, lot_id in cursor.fetchall():
                    cursor.execute(*sql_table.update(columns=[sql_table.animal],
                        values=[animal_id], where=sql_table.id == lot_id))

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
    def quantity_by_location(cls, lots, location_ids, quantity_domain=None,
            with_childs=False):
        """
        The context with keys:
            stock_skip_warehouse: if set, quantities on a warehouse are no more
                quantities of all child locations but quantities of the storage
                zone.
        location_ids is the list of IDs of locations to take account to compute
            the stock. It can't be empty.
        """
        pool = Pool()
        Location = pool.get('stock.location')
        Move = pool.get('stock.move')

        if not location_ids:
            return {}

        # Skip warehouse location in favor of their storage location
        # to compute quantities. Keep track of which ids to remove
        # and to add after the query.
        storage_to_remove = set()
        wh_by_storage = {}
        if Transaction().context.get('stock_skip_warehouse'):
            location_ids = set(location_ids)
            for location in Location.browse(list(location_ids)):
                if location.type == 'warehouse':
                    location_ids.remove(location.id)
                    if location.storage_location.id not in location_ids:
                        storage_to_remove.add(location.storage_location.id)
                    location_ids.add(location.storage_location.id)
                    wh_by_storage[location.storage_location.id] = location.id
            location_ids = list(location_ids)

        with Transaction().set_context(cls._quantity_context('quantity')):
            if lots is None:
                grouping_filter = (None, None)
            else:
                grouping_filter = (None, [l.id for l in lots])
            query = Move.compute_quantities_query(location_ids,
                with_childs=with_childs, grouping=('product', 'lot'),
                grouping_filter=grouping_filter)

            if quantity_domain:
                having_domain = cls.quantity._field.convert_domain(
                    quantity_domain, {
                        None: (query, {}),
                        }, cls)
                having_domain.left = query.columns[-1].expression
                if query.having:
                    query.having &= having_domain
                else:
                    query.having = having_domain

            quantities = Move.compute_quantities(query, location_ids,
                with_childs=with_childs, grouping=('product', 'lot'),
                grouping_filter=grouping_filter)

        res = {}
        for (location_id, unused, lot_id), quantity in quantities.items():
            if lot_id is None:
                continue
            lot_quantities = res.setdefault(lot_id, {})
            if location_id not in storage_to_remove:
                lot_quantities[location_id] = quantity
            if location_id in wh_by_storage:
                warehouse_id = wh_by_storage[location_id]
                if warehouse_id in lot_quantities:
                    lot_quantities[warehouse_id] += quantity
                else:
                    lot_quantities[warehouse_id] = quantity
        return res


class LotAnimalGroup(ModelSQL):
    "Lot - Animal Group"
    __name__ = 'stock.lot-farm.animal.group'

    lot = fields.Many2One('stock.lot', 'Lot', required=True,
        ondelete='RESTRICT')
    animal_group = fields.Many2One('farm.animal.group', 'Animal Group',
        required=True, ondelete='RESTRICT')


class Location(metaclass=PoolMeta):
    __name__ = 'stock.location'

    silo = fields.Boolean('Silo',
        help='Indicates that the location is a silo.')
    current_lot = fields.Function(fields.Many2One('stock.lot',
            'Current Lot', states={
                'invisible': Not(Eval('silo', False)),
                }),
        'get_current_lot')
    locations_to_fed = fields.Many2Many('stock.location.silo-stock.location',
        'silo', 'location', 'Locations to fed', domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states={
            'invisible': Not(Eval('silo', False)),
            },
        help='Indicates the locations the silo feeds. Note that this will '
        'only be a default value.')

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
        for (location_id, product_id, lot_id), quantity in pbl.items():
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
            current_lots[location.id] = first_moves[0].lot.id if first_moves else None
        return current_lots

    @classmethod
    def search(cls, args, offset=0, limit=None, order=None, count=False,
            query=False):
        FarmLine = Pool().get('farm.specie.farm_line')

        args = args[:]
        context = Transaction().context
        if context.get('restrict_by_specie_animal_type'):
            domain = []
            specie = context.get('specie')
            if specie:
                domain += ('specie', '=', specie),
            animal_type = context.get('animal_type')
            if animal_type:
                domain += ('has_' + animal_type, '=', True),
            farm_lines = FarmLine.search(domain)
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
                        ], [
                        ('type', 'not in', ['warehouse', 'storage']),
                        ]
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
        for (location_id, product_id, lot_id), quantity in pbl.items():
            if lot_id is not None and quantity >= 0.0:
                lot_quantities[lot_id] = quantity

        lot_fifo = []
        moves = Move.search([
                ('lot', 'in', list(lot_quantities.keys())),
                ('state', '=', 'done'),
                ('to_location', '=', self.id),
                ('effective_date', '<=', stock_date),
                ], offset=0,
            order=[
                ('effective_date', 'ASC'),
                ('id', 'ASC'),
                ])
        for move in moves:
            if not lot_quantities.get(move.lot.id):
                continue
            quantity = lot_quantities[move.lot.id]
            del lot_quantities[move.lot.id]

            if to_uom != None:
                assert (move.product.default_uom.category.id ==
                    to_uom.category.id), ('Invalid to_uom "%s" in '
                    'Location.get_lot_fifo(). Incompatible with default UoM '
                    'of product "%s" in silo "%s"'
                    % (to_uom.rec_name, move.product.rec_name, self.rec_name))
                quantity = Uom.compute_qty(move.product.default_uom, quantity,
                    to_uom, round=True)
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

        total_quantity = Decimal(0)
        for (location_id, product_id), quantity in pbl.items():
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
        required=True)
    location = fields.Many2One('stock.location', 'Location',
        ondelete='CASCADE', required=True)


class Move(metaclass=PoolMeta):
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
            'farm.insemination.event',
            'farm.farrowing.event',
            'farm.foster.event',
            'farm.weaning.event',
            'farm.reclassification.event'
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

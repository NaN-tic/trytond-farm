#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sql import Literal
from sql.aggregate import Avg, Count, Max, Sum
from sql.conditionals import Coalesce
from sql.functions import Extract, Now

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Bool, Eval, Id, Not
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN
from ..postgresql import GenerateSeries

__all__ = ['AnimalLocationStock', 'FeedInventory', 'FeedInventoryLocation',
    'FeedProvisionalInventory', 'FeedProvisionalInventoryLocation',
    'FeedInventoryLine', 'FeedLocationDate']

_INVENTORY_STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('cancel', 'Cancelled'),
    ]


class AnimalLocationStock():
    '''
    A class with two dictionaries. The main is a dictionary with a tuple of
        integers as keys (first integer is the ID of Lot and second integer is
        the ID of Location) and its values are lists of tuples that represents
        periods.
        The tuples of values has tree items: the first is the number of
            animals, the second is the start date and the third is the end
            date of period.
            The third element of tuple could be a 'False' that represent this
            period is opened.
    Second dictionary has dates as keys and its values are list 2-tuples, first
        value is a key of main dictionary and second is the quantity of animals
        in location in the date.
    '''
    def __init__(self, inventory_id, silo_id, start_date, end_date,
            warehouse_by_location):
        assert start_date and isinstance(start_date, date), ("'start_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % str(start_date))
        assert end_date and isinstance(end_date, date), ("'end_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % str(end_date))
        assert end_date > start_date, "Invalid period: %s - %s" % (start_date,
                end_date)

        # "public" to use in event
        self.inventory_id = inventory_id
        self.silo_id = silo_id
        self.start_date = start_date
        self.end_date = end_date
        self.location_animal_days = {}
        self.total_animal_days = 0
        # "private"
        self._warehouse_by_location = warehouse_by_location
        self._lot_data = {}
        self._lot_loc_dict = {}
        self._open_periods = []
        self._day_dict = {}
        self._open_animal_event = {}
        self._animal_events = []

        date_it = start_date
        while date_it <= end_date:
            self._day_dict[date_it] = []
            date_it += timedelta(days=1)

    def fill_animals_data(self, specie, close_time):
        pool = Pool()
        Lot = pool.get('stock.lot')
        Product = pool.get('product.product')

        assert close_time and isinstance(close_time, time), ("'close_time' "
            "parameter is empty or is not a datetime.time instance: %s"
            % str(close_time))

        def pbl_sortkey(pbl_item):
            return (pbl_item[0][2], pbl_item[1])

        product_ids = []
        for animal_type in ('male', 'female', 'individual', 'group'):
            if getattr(specie, '%s_enabled' % animal_type):
                product_ids.append(
                    getattr(specie, '%s_product' % animal_type).id)

        location_ids = self._warehouse_by_location.keys()
        with Transaction().set_context(stock_date_end=self.start_date):
            pbl = Product.products_by_location(location_ids,
                product_ids=product_ids, with_childs=False,
                grouping=('product', 'lot'))
        # First, it initialize 'loc_stock' with stock of animals in
        # location_ids at start_date
        for (location_id, product_id, lot_id), quantity in pbl.iteritems():
            if lot_id is None or quantity <= 0.0:
                continue
            self._add_animals(Lot(lot_id), location_id, quantity,
                self.start_date, close_time)

        # after, it iterates throw all movements in/out location_ids of animals
        for date_it in sorted(self._day_dict.keys())[1:]:
            with Transaction().set_context(stock_date_start=date_it,
                    stock_date_end=date_it):
                daily_pbl = Product.products_by_location(location_ids,
                    product_ids=product_ids, with_childs=False,
                    grouping=('product', 'lot'))
            # registers with 'qty'==0 refer to animals/groups that have come
            # out and enter the same day.
            for (loc_id, prod_id, lot_id), qty in sorted(daily_pbl.iteritems(),
                    key=pbl_sortkey):
                if lot_id is None or qty == 0.0:
                    continue
                # In openerp: close_time=lot_calendar.first_time
                self._add_animals(Lot(lot_id), loc_id, qty, date_it,
                    close_time)

        open_periods = self._open_periods[:]
        for (lot_id, location_id) in open_periods:
            self._close_period(lot_id, location_id, self.end_date, close_time)
        # it deletes _lot_loc_dict because its an auxiliar structure to prepare
        # _day_dict and total_animal_days for next steps
        del self._lot_loc_dict

    def _add_animals(self, lot, location_id, quantity, ddate, close_time):
        assert float(int(quantity)) == float(quantity), (
            "'quantity' parameter is not an integer: %s" % quantity)
        quantity = int(quantity)
        assert ddate and isinstance(ddate, date), ("'ddate' parameter is "
            "empty or is not a datetime.date instance: %s" % str(ddate))
        assert close_time and isinstance(close_time, time), (
            "'close_time' parameter is empty or is not a datetime.time "
            "instance: %s" % str(close_time))
        assert ddate >= self.start_date and ddate <= self.end_date, (
            "Date %d is not in period %d - %d" % (ddate, self.start_date,
                self.end_date))

        if lot.id not in self._lot_data:
            self._lot_data[lot.id] = {
                'specie_id': (lot.animal_type == 'group' and
                    lot.animal_group.specie.id or
                    lot.animal_type and lot.animal.specie.id),
                'animal_type': lot.animal_type,
                'animal_id': lot.animal and lot.animal.id or None,
                'group_id': lot.animal_group and lot.animal_group.id or None,
                }

        open_period = self._get_open_period(lot.id, location_id)
        # negative quantity => animal/group come out
        if quantity < 0:
            assert open_period, ("The animal %s in location %s has not any "
                "open period but there is a negative movement of %s units  on "
                "date %s" % (lot.id, location_id, quantity, ddate))
            curr_qty = open_period[0]
            quantity = abs(quantity)

            assert curr_qty >= quantity, ("Unexpected come out movement for "
                "Lot %s and Location %s. More units (%s) than opened period "
                "has: %s" % (lot.id, location_id, quantity, open_period))

            # it close the open period
            self._close_period(lot.id, location_id, ddate - timedelta(days=1),
                close_time)
            # if report qty > closed period qty => some animals remain in
            # location => it adds a new opened period for these animals
            if curr_qty > quantity:
                curr_qty -= quantity
                self._open_period(lot.id, location_id, curr_qty, ddate)

        # positive quantity => animal/group come in
        elif quantity > 0:
            if open_period:
                # if lot+location has _open_period, it close it and sums
                # quantity of this period to new quantity
                self._close_period(lot.id, location_id,
                    ddate - timedelta(days=1), close_time)
                quantity += open_period[0]
            # add new open period with new quantity
            self._open_period(lot.id, location_id, quantity, ddate)

    def _get_open_period(self, lot_id, location_id):
        '''
        If this lot and location has any period and the last doesn't has
        end date, returns it.
        @return: 3-tuple with qty, start date and a 'False'
        '''
        key = (lot_id, location_id)
        if not self._lot_loc_dict.get(key, False):
            return False
        lastperiod = self._lot_loc_dict[key][-1]
        # a period is open if end date (3th element of period tuple) is False
        return not lastperiod[2] and lastperiod or False

    def _open_period(self, lot_id, location_id, qty, start_date):
        assert start_date and isinstance(start_date, date), ("'start_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % start_date)
        key = (lot_id, location_id)
        if key not in self._lot_loc_dict:
            self._lot_loc_dict[key] = []

        if location_id not in self.location_animal_days:
            self.location_animal_days[location_id] = 0

        self._lot_loc_dict[key].append((qty, start_date, False))
        self._open_periods.append(key)

    def _close_period(self, lot_id, location_id, end_date, close_time):
        assert end_date and isinstance(end_date, date), ("'end_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % str(end_date))
        assert close_time and isinstance(close_time, time), ("'close_time' "
            "parameter is empty or is not a datetime.time instance: %s"
            % str(close_time))
        key = (lot_id, location_id)
        lastperiod = self._lot_loc_dict[key][-1]
        qty = lastperiod[0]
        lastperiod = (qty, lastperiod[1], end_date)
        self._lot_loc_dict[key][-1] = lastperiod

        date_it = lastperiod[1]
        while date_it < end_date:
            self._day_dict[date_it].append(
                (lot_id, location_id, lastperiod[0], False, close_time))
            self.location_animal_days[location_id] += qty
            self.total_animal_days += qty
            date_it += timedelta(days=1)

        self._day_dict[date_it].append(
            (lot_id, location_id, lastperiod[0], True, close_time))
        self.location_animal_days[location_id] += qty
        self.total_animal_days += qty

        self._open_periods.remove(key)
        return lastperiod

    def get_events_vals(self, consumed_per_animal_day, lot_qty_fifo, uom):
        assert isinstance(consumed_per_animal_day, Decimal), ("The type of "
            "'consumed_per_animal_day' param is not the expected Decimal")

        current_feed_lot, current_feed_qty = lot_qty_fifo.pop(0)

        zero_qty = Decimal('1E-%d' % uom.digits)

        days_list = self._day_dict.keys()
        days_list.sort()
        for date_it in days_list:
            for lot_id, location_id, n_animals, close, close_time \
                    in self._day_dict[date_it]:
                key = (lot_id, location_id)
                open_event = self._open_animal_event.get(key, False)

                if (open_event and open_event['feed_lot'] !=
                        current_feed_lot.id):
                    self._close_event(key, open_event, uom)
                    open_event = False

                if not open_event:
                    open_event = self._new_event(lot_id, date_it, location_id,
                        current_feed_lot, uom)

                qty_to_feed = n_animals * consumed_per_animal_day
                while qty_to_feed > zero_qty:
                    timestamp = datetime.combine(date_it, close_time)
                    if qty_to_feed <= current_feed_qty:
                        # if there are enough quantity of current feed, adds it
                        # to open event and updates qty_to_feed
                        open_event['quantity'] += qty_to_feed
                        open_event['timestamp'] = timestamp
                        open_event['end_date'] = date_it

                        current_feed_qty -= qty_to_feed
                        # sets False to 'qty_to_feed' to break 'while' loop
                        # and continue with remaining 'current_feed' with next
                        # animal or day
                        qty_to_feed = False
                    else:
                        if current_feed_qty > zero_qty:
                            # adds remaining quantity of current feed to
                            #    open_event
                            open_event['quantity'] += current_feed_qty
                            open_event['timestamp'] = timestamp
                            open_event['end_date'] = date_it

                            qty_to_feed -= current_feed_qty
                            current_feed_qty = Decimal('0.0')

                        # close open event current event
                        self._close_event(key, open_event, uom)

                        # get next feed product and open a new event for new
                        # feed product.
                        # in next loops the 'qty_to_feed' will be added to new
                        # event
                        if lot_qty_fifo:
                            (current_feed_lot,
                                current_feed_qty) = lot_qty_fifo.pop(0)
                            open_event = self._new_event(lot_id, date_it,
                                location_id, current_feed_lot, uom)
                        else:
                            open_event = None
                if close and open_event:
                    # location or quantity of animals changed. calculated
                    # when animals was added
                    self._close_event(key, open_event, uom)

        for key in self._open_animal_event:
            self._close_event(key, self._open_animal_event[key], uom)
        return self._animal_events

    def _new_event(self, lot_id, event_date, location_id, feed_lot, uom):
        assert event_date and isinstance(event_date, date), ("'event_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % str(event_date))
        event = {
            'specie': self._lot_data[lot_id]['specie_id'],
            'farm': self._warehouse_by_location[location_id],
            'animal_type': self._lot_data[lot_id]['animal_type'],
            'animal': self._lot_data[lot_id].get('animal_id'),
            'animal_group': self._lot_data[lot_id].get('group_id'),
            'timestamp': datetime.combine(event_date, time(8, 0, 0)),
            'location': location_id,
            'feed_location': self.silo_id,
            'feed_product': feed_lot.product.id,
            'feed_lot': feed_lot.id,
            'quantity': Decimal('0.0'),
            'uom': uom.id,
            'start_date': event_date,
            'end_date': event_date,
            'feed_inventory': self.inventory_id,
            }
        self._open_animal_event[(lot_id, location_id)] = event
        return event

    def _close_event(self, key, open_event, uom):
        if open_event['quantity'] > Decimal('1E-%d' % uom.digits):
            # if it is not an empty feed event, rounds the quantity
            open_event['quantity'] = open_event['quantity'].quantize(
                Decimal(str(10.0 ** -uom.digits)))
            self._animal_events.append(open_event)
        # remove it from anima'ls open events => animal hasn't open event
        del self._open_animal_event[key]


class FeedInventory(ModelSQL, ModelView, Workflow):
    'Feed Inventory'
    __name__ = 'farm.feed.inventory'
    _order = [('timestamp', 'ASC')]

    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True, select=True)
    location = fields.Many2One('stock.location', 'Silo', required=True,
        domain=[
            ('silo', '=', True),
            ], on_change=['location', 'dest_locations'],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    dest_locations = fields.Many2Many('farm.feed.inventory-stock.location',
        'inventory', 'location', 'Locations to fed', required=True,
        domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    timestamp = fields.DateTime('Date & Time', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    prev_inventory = fields.Many2One('farm.feed.inventory',
        'Previous Inventory', readonly=True)
    uom = fields.Many2One('product.uom', "UOM", domain=[
            ('category', '=', Id('product', 'uom_cat_weight')),
            ], states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']),
        'on_change_with_unit_digits')
    quantity = fields.Numeric('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['unit_digits'])
    lines = fields.One2Many('farm.feed.inventory.line', 'inventory',
        'Inventory Lines', readonly=True)
    feed_events = fields.One2Many('farm.feed.event', 'feed_inventory',
        'Feed Events', readonly=True)
    state = fields.Selection(_INVENTORY_STATES, 'State', required=True,
        readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(FeedInventory, cls).__setup__()
        cls._error_messages.update({
                'invalid_state_to_delete': ('The inventory "%s" can\'t be '
                    'deleted because is not in "Draft" or "Cancelled" state.'),
                'invalid_inventory_quantity': ('The quantity specified in '
                    'feed inventory "%(inventory)s" is not correct.\n'
                    'The current stock of this silo is %(curr_qty)s. The '
                    'quantity in the inventory must to be less than the '
                    'current stock.'),
                #'inventories_with_successors_not_cancellable': (
                #    'Next feed inventories can\'t be cancelled because later '
                #    'inventories exist for their own silos:\n - %s'),
                })
        cls._buttons.update({
                #'cancel': {
                #    'invisible': Eval('state') == 'cancel',
                #    },
                #'draft': {
                #    'invisible': Eval('state') != 'cancel',
                #    },
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    },
                })
        cls._transitions = set((
                ('draft', 'cancel'),
                ('draft', 'validated'),
                #('validated', 'cancel'),
                #('cancel', 'draft'),
                ))

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_timestamp():
        return Transaction().context.get('timestamp') or datetime.now()

    @staticmethod
    def default_uom():
        return Pool().get('ir.model.data').get_id('product', 'uom_kilogram')

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_state():
        return 'draft'

    def get_rec_name(self, name):
        return "%s (%s)" % (self.location.rec_name, self.timestamp)

    def on_change_location(self, name=None):
        if not self.location:
            return {
                'dest_locations': None,
                }
        return {
            'dest_locations': [l.id for l in self.location.locations_to_fed],
            }

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @classmethod
    def copy(cls, inventories, default=None):
        if default is None:
            default = {}
        default.update({
                'prev_inventory': False,
                'lines': False,
                'feed_events': False,
                'state': 'draft',
                })
        return super(FeedInventory, cls).copy(inventories, default)

    @classmethod
    def delete(cls, inventories):
        for inventory in inventories:
            if inventory.state not in ('draft', 'cancel'):
                cls.raise_user_error('invalid_state_to_delete',
                    inventory.rec_name)
        return super(FeedInventory, cls).delete(inventories)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, inventories):
        pool = Pool()
        FeedProvisionalInventory = pool.get('farm.feed.provisional_inventory')

        provisional_inventories = FeedProvisionalInventory.search([
                ('feed_inventory', 'in', [i.id for i in inventories]),
                ])
        if provisional_inventories:
            FeedProvisionalInventory.write(provisional_inventories, {
                    'feed_inventory': False,
                    })
        cls.write(inventories, {
                'prev_inventory': False,
                'feed_events': [('delete_all')],
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def confirm(cls, inventories):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')
        ProvisionalInventory = pool.get('farm.feed.provisional_inventory')
        InventoryLine = pool.get('farm.feed.inventory.line')

        for inventory in inventories:
            assert not inventory.feed_events, ('Feed Inventory "%s" already '
                'has related feed events.' % inventory.rec_name)

            prev_inventory = inventory._get_previous_inventory()
            if not prev_inventory:
                logging.getLogger(cls.__name__).warning('No previous Feed '
                    'Inventory for inventory "%s".' % inventory.rec_name)
                continue

            # Associate provisional inventories to inventory and canel them
            provisional_inventories = ProvisionalInventory.search([
                    ('location', '=', inventory.location.id),
                    ('feed_inventory', 'in', [None, inventory.id]),
                    ('state', '=', 'validated'),
                    ('timestamp', '<=', inventory.timestamp),
                    ])
            ProvisionalInventory.write(provisional_inventories, {
                    'feed_inventory': inventory.id,
                    })
            ProvisionalInventory.cancel(provisional_inventories)

            inv_qty = inventory.quantity
            qty_in_silo = inventory.location.get_total_quantity(
                inventory.timestamp.date(), inventory.uom)
            if inv_qty >= qty_in_silo:
                cls.raise_user_error('invalid_inventory_quantity', {
                        'inventory': inventory.rec_name,
                        'curr_qty': qty_in_silo,
                        })

            # Prepare data to compute and create Inventory Lines and
            #     Feed Events (using AnimalLocationStock class)
            start_date = prev_inventory.timestamp.date() + timedelta(days=1)
            warehouse_by_location = {}
            for location in inventory.dest_locations:
                warehouse_by_location[location.id] = location.warehouse.id

            animal_loc_stock = AnimalLocationStock(inventory.id,
                inventory.location.id, start_date, inventory.timestamp.date(),
                warehouse_by_location)
            animal_loc_stock.fill_animals_data(inventory.specie,
                inventory.timestamp.time())

            consumed_qty = qty_in_silo - inv_qty
            consumed_per_animal_day = (consumed_qty /
                    Decimal(str(animal_loc_stock.total_animal_days)))

            lot_qty_fifo = inventory.location.get_lot_fifo(
                inventory.timestamp.date(), inventory.uom)

            # Compute Feed Events values and create them (related to inventory)
            FeedEvent.create(animal_loc_stock.get_events_vals(
                    consumed_per_animal_day, lot_qty_fifo, inventory.uom))

            # Create Inventory Lines
            InventoryLine.create(inventory._get_inventory_line_vals(
                    animal_loc_stock, consumed_per_animal_day))

            inventory.prev_inventory = prev_inventory.id
            inventory.save()

        # Validate the created Feed Events
        inventories_events = FeedEvent.search([
                ('feed_inventory', 'in', [i.id for i in inventories]),
                ])
        FeedEvent.validate_event(inventories_events)

    def _get_previous_inventory(self):
        prev_inventories = self.search([
                ('location', '=', self.location.id),
                ('timestamp', '<', self.timestamp),
                ('state', '=', 'validated'),
                ],
            order=[
                ('timestamp', 'DESC'),
                ], limit=1)
        return prev_inventories and prev_inventories[0] or None

    def _get_inventory_line_vals(self, animal_loc_stock, qty_animal_day):
        qty_animal_day = qty_animal_day.quantize(
            Decimal(str(10.0 ** -self.uom.digits)))
        lines_vals = []
        for loc_dest in self.dest_locations:
            animals_day = (
                    animal_loc_stock.location_animal_days.get(loc_dest.id, 0))
            lines_vals.append({
                    'inventory': self.id,
                    'location': self.location.id,
                    'start_date': animal_loc_stock.start_date,
                    'end_date': animal_loc_stock.end_date,
                    'dest_location': loc_dest.id,
                    'animals_day': animals_day,
                    'consumed_qty_animal_day': qty_animal_day,
                    'consumed_qty': animals_day * qty_animal_day,
                    'uom': self.uom.id,
                    'state': 'validated',
                    })
        return lines_vals

    #@classmethod
    #@ModelView.button
    #@Workflow.transition('cancel')
    #def cancel(cls, inventories):
    #    pool = Pool()
    #    FeedEvent = pool.get('farm.feed.event')
    #    FeedProvisionalInventory = pool.get('farm.feed.provisional_inventory')

    #    inventories_ids = [i.id for i in inventories]
    #    next_inventories = cls.search([
    #                ('prev_inventory', 'in', inventories_ids),
    #                ('id', 'not in', inventories_ids),
    #                ('state', '=', 'validated'),
    #            ])
    #    if next_inventories:
    #        cls.raise_user_error(
    #            'inventories_with_successors_not_cancellable',
    #            "\n - ".join([i.prev_inventory.rec_name
    #                    for i in next_inventories]))

    #    for inventory in inventories:
    #        valid_feed_events = [e for e in inventory.feed_events
    #            if e.state == 'validated']
    #        valid_feed_events.reverse()
    #        FeedEvent.cancel(valid_feed_events)
    #    cls.write(inventories, {
    #        'lines': [('delete_all')],
    #        })

    #    # Re-validate Provisional Inventories
    #    provisional_inventories = FeedProvisionalInventory.search([
    #            ('feed_inventory', 'in', [i.id for i in inventories]),
    #            ])
    #    FeedProvisionalInventory.draft(provisional_inventories)
    #    FeedProvisionalInventory.validate(provisional_inventories)


class FeedInventoryLocation(ModelSQL):
    'Feed Inventory - Location'
    __name__ = 'farm.feed.inventory-stock.location'

    inventory = fields.Many2One('farm.feed.inventory', 'Feed Inventory',
        required=True, ondelete='CASCADE', select=True)
    location = fields.Many2One('stock.location', 'Location', required=True,
        select=True)


class FeedProvisionalInventory(ModelSQL, ModelView, Workflow):
    'Feed Provisional Inventory'
    __name__ = 'farm.feed.provisional_inventory'
    _order = [('timestamp', 'ASC')]

    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True, select=True)
    location = fields.Many2One('stock.location', 'Silo', required=True,
        domain=[
            ('silo', '=', True),
            ],
        on_change=['location', 'dest_locations'],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    dest_locations = fields.Many2Many(
        'farm.feed.provisional_inventory-stock.location', 'inventory',
        'location', 'Locations to fed', required=True,
        domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    timestamp = fields.DateTime('Date & Time', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    prev_inventory_date = fields.Date('Previous Inventory Date', readonly=True)
    uom = fields.Many2One('product.uom', "UOM", domain=[
            ('category', '=', Id('product', 'uom_cat_weight')),
            ], states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    unit_digits = fields.Function(fields.Integer('Unit Digits',
            on_change_with=['uom']),
        'on_change_with_unit_digits')
    quantity = fields.Numeric('Quantity', digits=(16, Eval('unit_digits', 2)),
        states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['unit_digits'])
    lines = fields.One2Many('farm.feed.inventory.line',
        'provisional_inventory', 'Inventory Lines', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Standard Inventory',
        readonly=True, states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN)
    feed_inventory = fields.Many2One('farm.feed.inventory', 'Inventory',
        readonly=True, depends=['location'])
    state = fields.Selection(_INVENTORY_STATES, 'State', required=True,
        readonly=True, select=True)

    @classmethod
    def __setup__(cls):
        super(FeedProvisionalInventory, cls).__setup__()
        cls._error_messages.update({
                'invalid_state_to_delete': ('The inventory "%s" can\'t be '
                    'deleted because is not in "Draft" or "Cancelled" state.'),
                'exists_later_real_inventories': ('There are real inventories '
                    'after the provisional inventory "%s" you are trying to '
                    'confirm.'),
                'invalid_inventory_quantity': ('The quantity specified in '
                    'feed provisional inventory "%(inventory)s" is not '
                    'correct.\n'
                    'The current stock of in this silo is %(curr_qty)s. The '
                    'quantity in the inventory must to be less than the '
                    'current stock.'),
                'missing_previous_inventory': ('There isn\'t any Feed '
                    'Inventory before the feed provisional inventory "%s" you '
                    'are trying to confirm.')
                #'inventories_with_successors_not_cancellable': (
                #    'Next feed inventories can\'t be cancelled because later '
                #    'inventories exist for their own silos:\n - %s'),
                })
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    },
                'cancel': {
                    'invisible': Eval('state') != 'validated',
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancel',
                    },
                })
        cls._transitions = set((
                ('draft', 'validated'),
                ('validated', 'cancel'),
                ('cancel', 'draft'),
                ))

    @staticmethod
    def default_specie():
        return Transaction().context.get('specie')

    @staticmethod
    def default_timestamp():
        return Transaction().context.get('timestamp') or datetime.now()

    @staticmethod
    def default_uom():
        return Pool().get('ir.model.data').get_id('product', 'uom_kilogram')

    @staticmethod
    def default_unit_digits():
        return 2

    @staticmethod
    def default_state():
        return 'draft'

    def get_rec_name(self, name):
        return "%s (%s)" % (self.location.rec_name, self.timestamp)

    def on_change_location(self, name=None):
        if not self.location:
            return {
                'dest_locations': None,
                }
        return {
            'dest_locations': [l.id for l in self.location.locations_to_fed],
            }

    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @classmethod
    def copy(cls, inventories, default=None):
        if default is None:
            default = {}
        default.update({
                'prev_inventory_date': False,
                'lines': False,
                'inventory': False,
                'feed_inventory': False,
                'state': 'draft',
                })
        return super(FeedProvisionalInventory, cls).copy(inventories, default)

    @classmethod
    def delete(cls, inventories):
        for inventory in inventories:
            if inventory.state not in ('draft', 'cancel'):
                cls.raise_user_error('invalid_state_to_delete',
                    inventory.rec_name)
        return super(FeedProvisionalInventory, cls).delete(inventories)

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, inventories):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def confirm(cls, inventories):
        pool = Pool()
        FeedInventory = pool.get('farm.feed.inventory')
        InventoryLine = pool.get('farm.feed.inventory.line')
        StockInventory = pool.get('stock.inventory')

        todo_stock_inventories = []
        for inventory in inventories:
            assert not inventory.inventory, ('Feed Provisional Inventory "%s" '
                'already has related a stock inventory.' % inventory.rec_name)

            current_real_inventories = FeedInventory.search([
                    ('location', '=', inventory.location.id),
                    ('timestamp', '>=', inventory.timestamp),
                    ('state', '=', 'validated'),
                    ])
            if current_real_inventories:
                cls.raise_user_error('exists_later_real_inventories',
                    inventory.rec_name)

            prev_inventory_date = inventory._get_previous_inventory_date()
            if not prev_inventory_date:
                cls.raise_user_error('missing_previous_inventory',
                    inventory.rec_name)
            inventory.prev_inventory_date = prev_inventory_date

            inv_qty = inventory.quantity
            qty_in_silo = inventory.location.get_total_quantity(
                    inventory.timestamp.date(), inventory.uom)
            if inv_qty >= qty_in_silo:
                cls.raise_user_error('invalid_inventory_quantity', {
                        'inventory': inventory.rec_name,
                        'curr_qty': qty_in_silo,
                        })

            # Prepare data to compute and create Inventory Lines and
            #     Feed Events (using AnimalLocationStock class)
            start_date = prev_inventory_date + timedelta(days=1)
            warehouse_by_location = {}
            for location in inventory.dest_locations:
                warehouse_by_location[location.id] = location.warehouse.id

            animal_loc_stock = AnimalLocationStock(inventory.id,
                inventory.location.id, start_date, inventory.timestamp.date(),
                warehouse_by_location)
            animal_loc_stock.fill_animals_data(inventory.specie,
                inventory.timestamp.time())

            consumed_qty = qty_in_silo - inv_qty
            consumed_per_animal_day = (consumed_qty /
                    Decimal(str(animal_loc_stock.total_animal_days)))

            # Create Inventory Lines
            InventoryLine.create(inventory._get_inventory_line_vals(
                    animal_loc_stock, consumed_per_animal_day))

            # Create stock.inventory
            stock_inventory = inventory._get_stock_inventory()
            stock_inventory.save()
            todo_stock_inventories.append(stock_inventory)
            inventory.inventory = stock_inventory

            inventory.save()
        StockInventory.confirm(todo_stock_inventories)

    def _get_previous_inventory_date(self):
        Inventory = Pool().get('farm.feed.inventory')

        prev_inventories = Inventory.search([
                ('location', '=', self.location.id),
                ('timestamp', '<', self.timestamp),
                ('state', '=', 'validated'),
                ],
            order=[
                ('timestamp', 'DESC'),
                ], limit=1)
        if not prev_inventories:
            return None

        prev_prov_inventories = self.search([
                ('location', '=', self.location.id),
                ('timestamp', '<', self.timestamp),
                ('timestamp', '>', prev_inventories[0].timestamp),
                ('state', '=', 'validated'),
                ],
            order=[
                ('timestamp', 'DESC'),
                ], limit=1)
        if prev_prov_inventories:
            return prev_prov_inventories[0].timestamp.date()
        return prev_inventories[0].timestamp.date()

    def _get_inventory_line_vals(self, animal_loc_stock, qty_animal_day):
        qty_animal_day = qty_animal_day.quantize(
            Decimal(str(10.0 ** -self.uom.digits)))
        lines_vals = []
        for loc_dest in self.dest_locations:
            animals_day = (
                    animal_loc_stock.location_animal_days.get(loc_dest.id, 0))
            lines_vals.append({
                    'provisional_inventory': self.id,
                    'location': self.location.id,
                    'start_date': animal_loc_stock.start_date,
                    'end_date': animal_loc_stock.end_date,
                    'dest_location': loc_dest.id,
                    'animals_day': animals_day,
                    'consumed_qty_animal_day': qty_animal_day,
                    'consumed_qty': animals_day * qty_animal_day,
                    'uom': self.uom.id,
                    })
        return lines_vals

    def _get_stock_inventory(self):
        pool = Pool()
        StockInventory = pool.get('stock.inventory')
        StockInventoryLine = pool.get('stock.inventory.line')
        UOM = pool.get('product.uom')

        pending_qty = self.quantity
        reversed_lot_fifo = self.location.get_lot_fifo(self.timestamp.date(),
            self.uom)
        reversed_lot_fifo.reverse()
        lines = []
        for lot, lot_qty in reversed_lot_fifo:
            line_qty = min(pending_qty, lot_qty)
            pending_qty -= line_qty
            if lot.product.default_uom.id != self.uom.id:
                lot_qty = UOM.compute_qty(self.uom, lot_qty,
                    lot.product.default_uom)
                line_qty = UOM.compute_qty(self.uom, line_qty,
                    lot.product.default_uom)
            lines.append(StockInventoryLine(
                    product=lot.product,
                    lot=lot,
                    expected_quantity=lot_qty,
                    quantity=line_qty))

        return StockInventory(
            location=self.location,
            date=self.timestamp.date(),
            lost_found=self.specie.feed_lost_found_location,
            lines=lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancel')
    def cancel(cls, inventories):
        pool = Pool()
        Date = pool.get('ir.date')
        InventoryLine = pool.get('farm.feed.inventory.line')
        StockInventory = pool.get('stock.inventory')
        StockMove = pool.get('stock.move')

        todo_stock_inventories = []
        todo_stock_moves = []
        inventory_lines = []
        for inventory in inventories:
            assert inventory.state == 'validated' and inventory.inventory, (
                'Feed Provisional Inventory "%s" is not in Validated state or '
                'it doesn\'t have stock inventory.' % inventory.rec_name)
            todo_stock_inventories.append(inventory.inventory)
            todo_stock_moves += [l.move for l in inventory.inventory.lines
                if l.move]
            inventory_lines += inventory.lines

        deny_modify_done_cancel_bak = StockMove._deny_modify_done_cancel.copy()
        StockMove._deny_modify_done_cancel.remove('state')
        StockMove._deny_modify_done_cancel.remove('effective_date')
        today = Date.today()
        for move in todo_stock_moves:
            move.state = 'cancel'
            move.effective_date = today
            if (move.from_location.type in ('supplier', 'production')
                    and move.to_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('out')
            elif (move.to_location.type == 'supplier'
                    and move.from_location.type == 'storage'
                    and move.product.cost_price_method == 'average'):
                move._update_product_cost_price('in')
            move.effective_date = None
            move.save()
        StockMove._deny_modify_done_cancel = deny_modify_done_cancel_bak

        StockInventory.write(todo_stock_inventories, {
                'state': 'cancel',
                })

        InventoryLine.delete(inventory_lines)

    @classmethod
    def write(cls, inventories, vals):
        pool = Pool()
        StockInventory = pool.get('stock.inventory')
        StockMove = pool.get('stock.move')

        super(FeedProvisionalInventory, cls).write(inventories, vals)

        if vals.get('state', '') == 'cancel':
            stock_inventories = [i.inventory for i in inventories]
            stock_moves = [l.move for i in stock_inventories
                for l in i.lines if l.move]
            StockMove.delete(stock_moves)
            StockInventory.delete(stock_inventories)


class FeedProvisionalInventoryLocation(ModelSQL):
    'Feed Provisional Inventory - Location'
    __name__ = 'farm.feed.provisional_inventory-stock.location'

    inventory = fields.Many2One('farm.feed.provisional_inventory',
        'Feed Provisional Inventory', ondelete='CASCADE', required=True,
        select=True)
    location = fields.Many2One('stock.location', 'Location', required=True,
        select=True)


class FeedInventoryLine(ModelSQL, ModelView):
    'Feed Inventory Line'
    __name__ = 'farm.feed.inventory.line'
    _order = [('end_date', 'ASC')]

    inventory = fields.Many2One('farm.feed.inventory', 'Inventory',
        ondelete='CASCADE', readonly=True, states={
            'invisible': Not(Bool(Eval('inventory', 0))),
            })
    provisional_inventory = fields.Many2One('farm.feed.provisional_inventory',
        'Provisional Inventory', ondelete='CASCADE', readonly=True, states={
            'invisible': Not(Bool(Eval('provisional_inventory', 0))),
            })
    state = fields.Function(fields.Selection(_INVENTORY_STATES,
            'Inventory State'),
        'get_state')
    location = fields.Many2One('stock.location', 'Silo', domain=[
            ('silo', '=', True),
            ], required=True, readonly=True)
    dest_location = fields.Many2One('stock.location', 'Location to fed',
        required=True, readonly=True)
    start_date = fields.Date('Start Date', required=True, readonly=True)
    end_date = fields.Date('End Date', required=True, readonly=True)
    animals_day = fields.Integer('Animals-Day', required=True, readonly=True,
        help='Number of total Animals-Day that has been in "Location Fed" '
        'during the period.')
    uom = fields.Many2One('product.uom', "UOM", domain=[
            ('category', '=', Id('product', 'uom_cat_weight')),
            ], required=True, readonly=True)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'get_unit_digits')
    consumed_qty_animal_day = fields.Numeric('Consumed Qty. per Animal-Day',
        digits=(16, Eval('unit_digits', 2)), required=True, readonly=True,
        depends=['unit_digits'])
    consumed_qty = fields.Numeric('Consumed Qty.',
        digits=(16, Eval('unit_digits', 2)), required=True, readonly=True,
        depends=['unit_digits'])

    @classmethod
    def __setup__(cls):
        super(FeedInventoryLine, cls).__setup__()
        cls._sql_constraints += [
            ('inventory_or_provisional_required',
                ('CHECK (inventory IS NOT NULL OR '
                    'provisional_inventory IS NOT NULL)'),
                'The Inventory or Provisional Inventory is required for all '
                'Feed Inventory Lines'),
            ]

    def get_state(self, name):
        if self.inventory:
            return self.inventory.state
        return self.provisional_inventory.state

    def get_unit_digits(self, name):
        return self.uom and self.uom.digits or 2


class FeedLocationDate(ModelSQL, ModelView):
    'Feed Consumption per Location and Date'
    __name__ = 'farm.feed.location_date'
    #_order = [
    #    ('location', 'ASC'),
    #    ('date', 'DESC'),
    #    ]

    location = fields.Many2One('stock.location', 'Location fed', select=True)
    date = fields.Date('Date', select=True)
    inventory_qty = fields.Integer('Final Inventories', select=True,
        help='Number of Final Inventories which include this date.')
    provisional_inventory_qty = fields.Integer('Provisional Inventories',
        select=True,
        help='Number of Provisional Inventories which include this date.')
    #uom = fields.Many2One('product.uom', "UOM", readonly=True)
    #unit_digits = fields.Function(fields.Integer('Unit Digits'),
    #    'get_unit_digits')
    consumed_qty_animal_day = fields.Float('Consumed Qty. per Animal-Day',
        digits=(16, 2), select=True)
        #depends=['unit_digits'])
    animals_qty = fields.Function(fields.Integer('Num. Animals',
            help='Number of Animals (Males, Females, Individuals or members '
            'of Groups) in this location in this date.'),
        'get_computed_quantities')
    consumed_qty = fields.Function(fields.Float('Consumed Qty.',
            digits=(16, 2),
            help='Total consumed quantity calculated by average.'),
        'get_computed_quantities')
    median_consumed_qty = fields.Float('Median Consumed Qty.',
        digits=(16, 2), select=True,
        help='The median of daily consumed quantity computed from Inventory Lines.')

    #@classmethod
    #def __setup__(cls):
    #    super(ProductCostHistory, cls).__setup__()
    #    cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def table_query(cls):
        pool = Pool()
        InventoryLine = pool.get('farm.feed.inventory.line')

        n_days = cls._days_to_compute()

        inv_line = InventoryLine.__table__()
        inv_line_tmp = InventoryLine.__table__()
        inv_line2 = inv_line_tmp.select(
            inv_line_tmp.inventory,
            inv_line_tmp.provisional_inventory,
            inv_line_tmp.dest_location,
            inv_line_tmp.start_date,
            inv_line_tmp.end_date,
            inv_line_tmp.consumed_qty_animal_day,
            (inv_line_tmp.consumed_qty /
                (inv_line_tmp.end_date - inv_line_tmp.start_date + 1)).as_(
                'daily_consumed_qty'))

        # TODO: replace by SELECT DISTINCT when it was supported by python-sql
        locations = inv_line.select(inv_line.dest_location,
            Max(inv_line.create_uid).as_('create_uid'),
            Max(inv_line.create_date).as_('create_date'),
            Max(inv_line.write_uid).as_('write_uid'),
            Max(inv_line.write_date).as_('write_date'),
            group_by=inv_line.dest_location)

        generate_series = GenerateSeries(Now().cast('DATE') - Literal(n_days),
            Now(), "INTERVAL '1 day'")

        return locations.join(generate_series, condition=Literal(True)).join(
            inv_line2,
            condition=((inv_line2.dest_location == locations.dest_location)
                & (inv_line2.start_date <= generate_series.date)
                & (inv_line2.end_date >= generate_series.date))
            ).select(
                (locations.dest_location * 10000 +
                    Extract('DOY', generate_series.date)).as_('id'),
                Max(locations.create_uid).as_('create_uid'),
                Max(locations.create_date).as_('create_date'),
                Max(locations.write_uid).as_('write_uid'),
                Max(locations.write_date).as_('write_date'),
                locations.dest_location.as_('location'),
                generate_series.date,
                Count(inv_line2.inventory).as_('inventory_qty'),
                Count(inv_line2.provisional_inventory).as_(
                    'provisional_inventory_qty'),
                Coalesce(Sum(inv_line2.consumed_qty_animal_day), 0.0).cast(
                    cls.consumed_qty_animal_day.sql_type().base
                    ).as_('consumed_qty_animal_day'),
                Coalesce(Sum(inv_line2.daily_consumed_qty), 0.0).cast(
                    cls.median_consumed_qty.sql_type().base
                    ).as_('median_consumed_qty'),
                group_by=(locations.dest_location, generate_series.date))

    @staticmethod
    def _days_to_compute():
        'Number of days that will be computed and show in the report'
        return 29

    #def get_unit_digits(self, name):
    #    return self.uom and self.uom.digits or 2

    @classmethod
    def get_computed_quantities(cls, instances, names):
        pool = Pool()
        InventoryLine = pool.get('farm.feed.inventory.line')
        Product = pool.get('product.product')
        Specie = pool.get('farm.specie')

        def get_specie_animals_products(specie):
            animals_products = []
            for animal_type in ('male', 'female', 'individual', 'group'):
                if getattr(specie, '%s_enabled' % animal_type):
                    animals_products.append(getattr(specie,
                            '%s_product' % animal_type))
            return animals_products

        instances_by_date = {}
        for instance in instances:
            instances_by_date.setdefault(instance.date, []).append(instance)

        context = Transaction().context
        if context.get('specie'):
            specie = Specie(context['specie'])
            animals_products = get_specie_animals_products(specie)
        else:
            all_dates = sorted(instances_by_date.keys())
            inventory_lines = InventoryLine.search([
                    ('dest_location', 'in',
                        [i.location.id for i in instances]),
                    ('start_date', '<=', all_dates[-1]),
                    ('end_date', '>=', all_dates[0]),
                    ])

            animals_products = []
            for inv_line in inventory_lines:
                specie = (inv_line.inventory and inv_line.inventory.specie or
                    inv_line.provisional_inventory.specie)
                animals_products += get_specie_animals_products(specie)
            animals_products = list(set(animals_products))

        res = {
            'animals_qty': {},
            'consumed_qty': {},
            }
        for date, date_instances in instances_by_date.items():
            location_ids = [i.location.id for i in date_instances]
            with Transaction().set_context(stock_date_end=date):
                pbl = Product.products_by_location(location_ids=location_ids,
                    product_ids=[p.id for p in animals_products],
                    with_childs=False)
            qty_by_location = {}.fromkeys(location_ids, 0)
            for key, qty in pbl.items():
                location_id = key[0]
                qty_by_location[location_id] += int(qty)

            for instance in date_instances:
                animals_qty = qty_by_location[instance.location.id]
                res['animals_qty'][instance.id] = animals_qty
                res['consumed_qty'][instance.id] = (
                    float(animals_qty) * instance.consumed_qty_animal_day)

        if 'animals_qty' not in names:
            del res['animals_qty']
        if 'consumed_qty' not in names:
            del res['consumed_qty']
        return res

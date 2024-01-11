# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
import logging
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from sql import Cast, Literal, Values, With
from sql.aggregate import Avg, Count, Max, Sum
from sql.conditionals import Coalesce
from sql.functions import Extract, Now

from trytond.model import fields, ModelSQL, ModelView, Workflow
from trytond.pyson import Equal, Eval, Id, Not
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.i18n import gettext

from .abstract_event import _STATES_WRITE_DRAFT, _STATES_VALIDATED_ADMIN

_INVENTORY_STATES = [
    ('draft', 'Draft'),
    ('validated', 'Validated'),
    ('cancelled', 'Cancelled'),
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
    def __init__(self, inventory, silo_id, start_date, end_date,
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
        self.inventory = inventory
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

        location_ids = list(self._warehouse_by_location.keys())
        with Transaction().set_context(stock_date_end=self.start_date,
                with_childs=False):
            pbl = Product.products_by_location(location_ids,
                with_childs=False, grouping=('product', 'lot'),
                grouping_filter=[product_ids])
        # First, it initialize 'loc_stock' with stock of animals in
        # location_ids at start_date
        for (location_id, _, lot_id), quantity in pbl.items():
            if lot_id is None or quantity <= 0.0:
                continue
            self._add_animals(Lot(lot_id), location_id, quantity,
                self.start_date, close_time)

        # after, it iterates throw all movements in/out location_ids of animals
        for date_it in sorted(self._day_dict.keys())[1:]:
            with Transaction().set_context(stock_date_start=date_it,
                    stock_date_end=date_it):
                daily_pbl = Product.products_by_location(location_ids,
                    with_childs=False, grouping=('product', 'lot'),
                    grouping_filter=[product_ids])
            # registers with 'qty'==0 refer to animals/groups that have come
            # out and enter the same day.
            for (loc_id, _, lot_id), qty in sorted(iter(daily_pbl.items()),
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
        # TODO: del self._lot_loc_dict

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

    def get_provisional_events_vals(self, consumed_per_animal_day, uom):
        assert isinstance(consumed_per_animal_day, Decimal), ("The type of "
            "'consumed_per_animal_day' param is not the expected Decimal")
        # TODO: use it
        events_vals = []
        for (lot_id, location_id), periods in list(self._lot_loc_dict.items()):
            for (n_animals, start_date, end_date) in periods:
                event = self._new_event(lot_id, n_animals, start_date,
                    location_id, None, uom, consumed_per_animal_day)
                # TODO: close time
                event['timestamp'] = datetime.combine(end_date,
                    time(8, 0, 0))
                event['feed_quantity'] = (consumed_per_animal_day * n_animals *
                    (end_date - start_date).days).quantize(
                        Decimal(str(10.0 ** -uom.digits)))
                event['state'] = 'provisional'
                events_vals.append(event)
        return [x for x in events_vals if x['feed_quantity']]

    def get_events_vals(self, consumed_per_animal_day, lot_qty_fifo, uom):
        assert isinstance(consumed_per_animal_day, Decimal), ("The type of "
            "'consumed_per_animal_day' param is not the expected Decimal")

        current_feed_lot, current_feed_qty = lot_qty_fifo.pop(0)

        zero_qty = Decimal('1E-%d' % uom.digits)

        days_list = list(self._day_dict.keys())
        days_list.sort()
        for date_it in days_list:
            for lot_id, location_id, n_animals, close, close_time \
                    in self._day_dict[date_it]:
                key = (lot_id, location_id)
                open_event = self._open_animal_event.get(key, False)

                if open_event and (
                        open_event['quantity'] != n_animals or
                        open_event['feed_lot'] != current_feed_lot.id):
                    self._close_event(key, open_event, uom)
                    open_event = False

                if not open_event:
                    open_event = self._new_event(lot_id, n_animals, date_it,
                        location_id, current_feed_lot, uom,
                        consumed_per_animal_day)

                qty_to_feed = n_animals * consumed_per_animal_day
                while qty_to_feed > zero_qty:
                    timestamp = datetime.combine(date_it, close_time)
                    if qty_to_feed <= current_feed_qty:
                        # if there are enough quantity of current feed, adds it
                        # to open event and updates qty_to_feed
                        open_event['feed_quantity'] += qty_to_feed
                        open_event['timestamp'] = timestamp

                        current_feed_qty -= qty_to_feed
                        # sets False to 'qty_to_feed' to break 'while' loop
                        # and continue with remaining 'current_feed' with next
                        # animal or day
                        qty_to_feed = False
                    else:
                        if current_feed_qty > zero_qty:
                            # adds remaining quantity of current feed to
                            #    open_event
                            open_event['feed_quantity'] += current_feed_qty
                            open_event['timestamp'] = timestamp

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
                            open_event = self._new_event(lot_id, n_animals,
                                date_it, location_id, current_feed_lot, uom,
                                consumed_per_animal_day)
                        else:
                            open_event = None
                if close and open_event:
                    # location or quantity of animals changed. calculated
                    # when animals was added
                    self._close_event(key, open_event, uom)

        for key in self._open_animal_event:
            self._close_event(key, self._open_animal_event[key], uom)
        return [x for x in self._animal_events if x['feed_quantity']]

    def _new_event(self, lot_id, n_animals, start_date, location_id, feed_lot,
            uom, consumed_per_animal_day):
        assert start_date and isinstance(start_date, date), ("'start_date' "
            "parameter is empty or is not a datetime.date instance: %s"
            % str(start_date))
        event = {
            'specie': self._lot_data[lot_id]['specie_id'],
            'farm': self._warehouse_by_location[location_id],
            'animal_type': self._lot_data[lot_id]['animal_type'],
            'animal': self._lot_data[lot_id].get('animal_id'),
            'animal_group': self._lot_data[lot_id].get('group_id'),
            'timestamp': datetime.combine(start_date, time(8, 0, 0)),
            'location': location_id,
            'quantity': n_animals,
            'feed_location': self.silo_id,
            'feed_product': feed_lot.product.id if feed_lot else None,
            'feed_lot': feed_lot.id if feed_lot else None,
            'feed_quantity': Decimal('0.0'),
            'uom': uom.id,
            'start_date': start_date,
            'feed_quantity_animal_day': consumed_per_animal_day.quantize(
                Decimal('0.0001')),
            'feed_inventory': str(self.inventory),
            }
        self._open_animal_event[(lot_id, location_id)] = event
        return event

    def _close_event(self, key, open_event, uom):
        if open_event['feed_quantity'] > Decimal('1E-%d' % uom.digits):
            # if it is not an empty feed event, rounds the quantity
            open_event['feed_quantity'] = open_event['feed_quantity'].quantize(
                Decimal(str(10.0 ** -uom.digits)))
            self._animal_events.append(open_event)
        # remove it from anima'ls open events => animal hasn't open event
        del self._open_animal_event[key]


class FeedInventoryMixin(object):
    __slots__ = ()
    specie = fields.Many2One('farm.specie', 'Specie', required=True,
        readonly=True)
    location = fields.Many2One('stock.location', 'Silo', required=True,
        domain=[
            ('silo', '=', True),
            ],
        states=_STATES_WRITE_DRAFT)
    dest_locations = fields.Many2Many('farm.feed.inventory-stock.location',
        'inventory', 'location', 'Locations to fed', required=True,
        domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ],
        states=_STATES_WRITE_DRAFT)
    timestamp = fields.DateTime('Date & Time', required=True,
        states=_STATES_WRITE_DRAFT)
    # prev_inventory/prev_inventory_date
    uom = fields.Many2One('product.uom', "UOM", domain=[
            ('category', '=', Id('product', 'uom_cat_weight')),
            ], states=_STATES_WRITE_DRAFT)
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    quantity = fields.Numeric('Quantity', digits=(16, Eval('unit_digits', 2)),
        required=True, states=_STATES_WRITE_DRAFT,
        depends=['unit_digits'])
    feed_events = fields.One2Many('farm.feed.event', 'feed_inventory',
        'Feed Events', readonly=True)
    # inventory, feed_inventory
    state = fields.Selection(_INVENTORY_STATES, 'State', required=True,
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(FeedInventoryMixin, cls).__setup__()
        cls._buttons.update({
                'confirm': {
                    'invisible': Eval('state') != 'draft',
                    'icon': 'tryton-ok',
                    },
                # 'cancel': {
                #     'invisible': Eval('state') == 'cancelled',
                #     },
                # 'draft': {
                #     'invisible': Eval('state') != 'cancelled',
                #     },
                })
        cls._transitions = set((
                ('draft', 'validated'),
                ('draft', 'cancelled'),
                # ('validated', 'cancelled'),
                # ('cancelled', 'draft'),
                ))

    @classmethod
    def __register__(cls, module_name):
        super(FeedInventoryMixin, cls).__register__(module_name)

        cursor = Transaction().connection.cursor()
        sql_table = cls.__table__()

        # Migration from 5.6: rename state cancel to cancelled
        cursor.execute(*sql_table.update(
                [sql_table.state], ['cancelled'],
                where=sql_table.state == 'cancel'))

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

    @fields.depends('location')
    def on_change_location(self, name=None):
        if not self.location:
            self.dest_locations = None
            return
        self.dest_locations = self.location.locations_to_fed

    @fields.depends('uom')
    def on_change_with_unit_digits(self, name=None):
        if self.uom:
            return self.uom.digits
        return 2

    @classmethod
    def copy(cls, inventories, default=None):
        if default is None:
            default = {}
        default.update({
                'feed_events': False,
                'state': 'draft',
                })
        return super(FeedInventoryMixin, cls).copy(inventories, default)

    @classmethod
    def delete(cls, inventories):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')
        FeedInventoryLocation = pool.get('farm.feed.inventory-stock.location')

        inventory_events = []
        for inventory in inventories:
            if inventory.state not in ('draft', 'cancelled'):
                raise UserError(gettext(
                        'farm.inventory_invalid_state_to_delete',
                        inventory=inventory.rec_name))
            inventory_events += inventory.feed_events
        if inventory_events:
            FeedEvent.delete(inventory_events)

        inventory_locations = FeedInventoryLocation.search([
                ('inventory', 'in', [str(i) for i in inventories]),
                ])
        if inventory_locations:
            FeedInventoryLocation.delete(inventory_locations)

        return super(FeedInventoryMixin, cls).delete(inventories)


class FeedInventoryLocation(ModelSQL):
    'Feed Inventory - Location'
    __name__ = 'farm.feed.inventory-stock.location'

    inventory = fields.Reference('Inventory', selection='get_inventory',
        required=True)
    location = fields.Many2One('stock.location', 'Location', required=True)

    @classmethod
    def get_inventory(cls):
        IrModel = Pool().get('ir.model')
        models = IrModel.search([
                ('model', 'in', ['farm.feed.inventory',
                        'farm.feed.provisional_inventory']),
                ])
        return [(m.model, m.name) for m in models]


class FeedInventory(FeedInventoryMixin, ModelSQL, ModelView, Workflow):
    'Feed Inventory'
    __name__ = 'farm.feed.inventory'
    _order = [('timestamp', 'ASC')]

    prev_inventory = fields.Many2One('farm.feed.inventory',
        'Previous Inventory', readonly=True)

    @classmethod
    def copy(cls, inventories, default=None):
        if default is None:
            default = {}
        default.update({
                'prev_inventory': False,
                })
        return super(FeedInventory, cls).copy(inventories, default)

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
                'prev_inventory': None,
                'feed_events': [('delete_all')],
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def confirm(cls, inventories):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')
        ProvisionalInventory = pool.get('farm.feed.provisional_inventory')

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
                raise UserError(gettext('farm.invalid_inventory_quantity',
                        inventory=inventory.rec_name,
                        curr_qty=qty_in_silo,
                        ))

            # Prepare data to compute and create Feed Events
            # (using AnimalLocationStock class)
            start_date = prev_inventory.timestamp.date() + timedelta(days=1)
            if start_date >= inventory.timestamp.date():
                raise UserError(gettext('farm.invalid_inventory_date',
                        inventory=inventory.rec_name))

            warehouse_by_location = {}
            for location in inventory.dest_locations:
                warehouse_by_location[location.id] = location.warehouse.id

            animal_loc_stock = AnimalLocationStock(inventory,
                inventory.location.id, start_date, inventory.timestamp.date(),
                warehouse_by_location)
            animal_loc_stock.fill_animals_data(inventory.specie,
                inventory.timestamp.time())

            animal_days = Decimal(str(animal_loc_stock.total_animal_days))
            if animal_days == Decimal('0'):
                raise UserError(gettext(
                        'farm.no_animals_in_inventory_destinations',
                        inventory=inventory.rec_name,
                        start_date=start_date.strftime('%d/%m/%Y'),
                        ))

            consumed_qty = qty_in_silo - inv_qty
            consumed_per_animal_day = (consumed_qty / animal_days)

            lot_qty_fifo = inventory.location.get_lot_fifo(
                inventory.timestamp.date(), inventory.uom)

            # Compute Feed Events values and create them (related to inventory)
            FeedEvent.create(animal_loc_stock.get_events_vals(
                    consumed_per_animal_day, lot_qty_fifo, inventory.uom))

            inventory.prev_inventory = prev_inventory.id
            inventory.save()

        # Validate the created Feed Events
        inventories_events = FeedEvent.search([
                ('feed_inventory', 'in', [str(i) for i in inventories]),
                ])
        # The specific lot consumption is an aproximation. It could calculate
        # that a lot is consumed a bit before it is available in silo
        FeedEvent.validate_event(inventories_events,
            check_feed_available=False)

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

    #@classmethod
    #@ModelView.button
    #@Workflow.transition('cancelled')
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
    #        })

    #    # Re-validate Provisional Inventories
    #    provisional_inventories = FeedProvisionalInventory.search([
    #            ('feed_inventory', 'in', [i.id for i in inventories]),
    #            ])
    #    FeedProvisionalInventory.draft(provisional_inventories)
    #    FeedProvisionalInventory.validate(provisional_inventories)


class FeedProvisionalInventory(FeedInventoryMixin, ModelSQL, ModelView,
        Workflow):
    'Feed Provisional Inventory'
    __name__ = 'farm.feed.provisional_inventory'
    _order = [('timestamp', 'ASC')]

    prev_inventory_date = fields.Date('Previous Inventory Date', readonly=True)
    inventory = fields.Many2One('stock.inventory', 'Standard Inventory',
        readonly=True, states=_STATES_VALIDATED_ADMIN)
    feed_inventory = fields.Many2One('farm.feed.inventory', 'Inventory',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(FeedProvisionalInventory, cls).__setup__()
        cls.feed_events.domain = [
            ('state', '=', 'provisional'),
            ]
        cls._buttons.update({
                'cancel': {
                    'invisible': Eval('state') != 'validated',
                    },
                'draft': {
                    'invisible': Eval('state') != 'cancelled',
                    },
                })
        cls._transitions |= set((
                ('validated', 'cancelled'),
                ('cancelled', 'draft'),
                ))

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, inventories):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')

        inventory_events = [e for i in inventories for e in i.feed_events]
        if inventory_events:
            FeedEvent.delete(inventory_events)

        cls.write(inventories, {
                'prev_inventory_date': None,
                'inventory': None,
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def confirm(cls, inventories):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')
        FeedInventory = pool.get('farm.feed.inventory')
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
                raise UserError(gettext('farm.exists_later_real_inventories',
                        inventory=inventory.rec_name))

            prev_inventory_date = inventory._get_previous_inventory_date()
            if not prev_inventory_date:
                raise UserError(gettext('farm.missing_previous_inventory',
                        inventory=inventory.rec_name))
            inventory.prev_inventory_date = prev_inventory_date

            inv_qty = inventory.quantity
            qty_in_silo = inventory.location.get_total_quantity(
                    inventory.timestamp.date(), inventory.uom)
            if inv_qty >= qty_in_silo:
                raise UserError(gettext('farm.invalid_inventory_quantity',
                            inventory=inventory.rec_name,
                            curr_qty=qty_in_silo,
                            ))

            # Prepare data to compute and create Feed Events
            # (using AnimalLocationStock class)
            start_date = prev_inventory_date + timedelta(days=1)
            warehouse_by_location = {}
            for location in inventory.dest_locations:
                warehouse_by_location[location.id] = location.warehouse.id

            animal_loc_stock = AnimalLocationStock(inventory,
                inventory.location.id, start_date, inventory.timestamp.date(),
                warehouse_by_location)
            animal_loc_stock.fill_animals_data(inventory.specie,
                inventory.timestamp.time())

            consumed_qty = qty_in_silo - inv_qty
            consumed_per_animal_day = (consumed_qty /
                    Decimal(str(animal_loc_stock.total_animal_days)))

            # Compute provisional Feed Events values and create them
            events_vals = animal_loc_stock.get_provisional_events_vals(
                consumed_per_animal_day, inventory.uom)
            FeedEvent.create(events_vals)

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
            lines=lines)

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, inventories):
        pool = Pool()
        Date = pool.get('ir.date')
        FeedEvent = pool.get('farm.feed.event')
        StockInventory = pool.get('stock.inventory')
        StockMove = pool.get('stock.move')

        todo_stock_inventories = []
        todo_stock_moves = []
        inventory_events = []
        for inventory in inventories:
            assert inventory.state == 'validated' and inventory.inventory, (
                'Feed Provisional Inventory "%s" is not in Validated state or '
                'it doesn\'t have stock inventory.' % inventory.rec_name)
            todo_stock_inventories.append(inventory.inventory)
            todo_stock_moves += [m for l in inventory.inventory.lines
                for m in l.moves]
            inventory_events += inventory.feed_events

        deny_modify_done_cancel_bak = StockMove._deny_modify_done_cancel.copy()
        StockMove._deny_modify_done_cancel.remove('effective_date')
        today = Date.today()
        for move in todo_stock_moves:
            move.state = 'cancelled'
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
                'state': 'cancelled',
                })

        FeedEvent.draft(inventory_events)
        FeedEvent.delete(inventory_events)

    @classmethod
    def copy(cls, inventories, default=None):
        if default is None:
            default = {}
        default.update({
                'prev_inventory_date': False,
                'inventory': False,
                'feed_inventory': False,
                })
        return super(FeedProvisionalInventory, cls).copy(inventories, default)

    @classmethod
    def write(cls, *args):
        pool = Pool()
        StockInventory = pool.get('stock.inventory')
        StockMove = pool.get('stock.move')
        super(FeedProvisionalInventory, cls).write(*args)

        actions = iter(args)
        for inventories, values in zip(actions, actions):
            if values.get('state', '') == 'cancelled':
                stock_inventories = [i.inventory for i in inventories]
                stock_moves = [m for i in stock_inventories
                    for l in i.lines for m in l.moves]
                StockMove.delete(stock_moves)
                StockInventory.delete(stock_inventories)


class FeedAnimalLocationDate(ModelSQL, ModelView):
    'Feed Consumption per Animal, Location, and Date'
    __name__ = 'farm.feed.animal_location_date'
    _order = [
        ('location', 'ASC'),
        ('date', 'DESC'),
        ]

    animal_type = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('individual', 'Individual'),
        ('group', 'Group'),
        ], "Animal Type", required=True, readonly=True)
    animal = fields.Many2One('farm.animal', 'Animal', states={
            'invisible': Equal(Eval('animal_type'), 'group'),
            })
    animal_group = fields.Many2One('farm.animal.group', 'Group', states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            })
    location = fields.Many2One('stock.location', 'Location fed')
    animals_qty = fields.Integer('Num. Animals', states={
            'invisible': Not(Equal(Eval('animal_type'), 'group')),
            })
    date = fields.Date('Date')
    # uom = fields.Many2One('product.uom', "UOM", readonly=True)
    # unit_digits = fields.Function(fields.Integer('Unit Digits'),
    #     'get_unit_digits')
    consumed_qty_animal = fields.Float('Consumed Qty. per Animal',
        digits=(16, 2))
    consumed_qty = fields.Float('Consumed Qty.', digits=(16, 2))
    inventory_qty = fields.Integer('Inventories',
        help='Number of Inventories which include this date.')

    @classmethod
    def table_query(cls):
        pool = Pool()
        FeedEvent = pool.get('farm.feed.event')

        Date = cls.date.sql_type().base

        n_days = cls._days_to_compute()

        # TODO: replace by SELECT DISTINCT when it was supported by python-sql
        feed_event_tmp = FeedEvent.__table__()
        animals = feed_event_tmp.select(feed_event_tmp.animal_type,
            feed_event_tmp.animal,
            feed_event_tmp.animal_group,
            Max(feed_event_tmp.create_uid).as_('create_uid'),
            Max(feed_event_tmp.create_date).as_('create_date'),
            Max(feed_event_tmp.write_uid).as_('write_uid'),
            Max(feed_event_tmp.write_date).as_('write_date'),
            group_by=(feed_event_tmp.animal_type, feed_event_tmp.animal,
                feed_event_tmp.animal_group))

        days = With('date', recursive=True)
        days.query = Values([(Cast(Now(), Date) - n_days, )])
        days.query |= days.select(Cast(days.date + Cast('1 day', 'Interval'),
                Date),
            where=days.date <= Now())
        days.query.all_ = True
        days_q = days.select(with_=[days])

        feed_event = FeedEvent.__table__()
        feed_event = feed_event.select(feed_event.animal_type,
            feed_event.animal,
            feed_event.animal_group,
            feed_event.location,
            feed_event.quantity,
            Coalesce(feed_event.start_date,
                Cast(feed_event.timestamp, Date)).as_('start_date'),
            Cast(feed_event.timestamp, Date).as_('end_date'),
            feed_event.feed_quantity_animal_day,
            (feed_event.feed_quantity_animal_day *
                feed_event.quantity).as_('daily_consumed_qty'),
            feed_event.feed_inventory)

        query = animals.join(days_q, condition=Literal(True)).join(
            feed_event,
            condition=((feed_event.animal_type == animals.animal_type)
                & ((feed_event.animal == animals.animal)
                    | (feed_event.animal_group == animals.animal_group))
                & (feed_event.start_date <= days_q.date)
                & (feed_event.end_date >= days_q.date))
            ).select(
                (Coalesce(animals.animal, 0) * 10000000000 +
                    Coalesce(animals.animal_group, 0) * 1000000 +
                    feed_event.location * 1000 +
                    Extract('DOY', days_q.date)).as_('id'),
                Max(animals.create_uid).as_('create_uid'),
                Max(animals.create_date).as_('create_date'),
                Max(animals.write_uid).as_('write_uid'),
                Max(animals.write_date).as_('write_date'),
                animals.animal_type,
                animals.animal,
                animals.animal_group,
                feed_event.location,
                Avg(feed_event.quantity).as_('animals_qty'),
                days_q.date,
                Coalesce(Sum(feed_event.feed_quantity_animal_day), 0.0).cast(
                    cls.consumed_qty_animal.sql_type().base
                    ).as_('consumed_qty_animal'),
                Coalesce(Sum(feed_event.daily_consumed_qty), 0.0).cast(
                    cls.consumed_qty.sql_type().base
                    ).as_('consumed_qty'),
                Count(feed_event.feed_inventory).as_('inventory_qty'),
                group_by=(animals.animal_type, animals.animal,
                    animals.animal_group, feed_event.location,
                    days_q.date))
        return query

    @staticmethod
    def _days_to_compute():
        'Number of days that will be computed and show in the report'
        return 31

    # def get_unit_digits(self, name):
    #     return self.uom and self.uom.digits or 2

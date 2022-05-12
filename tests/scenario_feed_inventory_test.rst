=======================
Feed Inventory Scenario
=======================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.farm.tests.tools import create_specie, \
    ...     create_users, create_feed_product
    >>> now = datetime.datetime.now()
    >>> today = datetime.date.today()

Install module::

    >>> config = activate_modules('farm')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create specie::

    >>> specie, breed, products = create_specie('Pig')
    >>> individual_product = products['individual']
    >>> group_product = products['group']
    >>> female_product = products['female']
    >>> male_product = products['male']
    >>> semen_product = products['semen']

Create farm users::

    >>> users = create_users(company)
    >>> individual_user = users['individual']
    >>> group_user = users['group']
    >>> female_user = users['female']
    >>> male_user = users['male']

Get locations::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> production_location, = Location.find([('type', '=', 'production')])

Prepare farm locations L1, L2 and L3, and Silo location::

    >>> location1 = Location()
    >>> location1.name = 'Location 1'
    >>> location1.code = 'L1'
    >>> location1.type = 'storage'
    >>> location1.parent = warehouse.storage_location
    >>> location1.save()
    >>> location2 = Location()
    >>> location2.name = 'Location 2'
    >>> location2.code = 'L2'
    >>> location2.type = 'storage'
    >>> location2.parent = warehouse.storage_location
    >>> location2.save()
    >>> location3 = Location()
    >>> location3.name = 'Location 3'
    >>> location3.code = 'L3'
    >>> location3.type = 'storage'
    >>> location3.parent = warehouse.storage_location
    >>> location3.save()
    >>> silo1 = Location()
    >>> silo1.name = 'Silo 1'
    >>> silo1.code = 'S1'
    >>> silo1.type = 'storage'
    >>> silo1.parent = warehouse.storage_location
    >>> silo1.silo = True
    >>> silo1.locations_to_fed.append(location1)
    >>> silo1.locations_to_fed.append(location2)
    >>> silo1.locations_to_fed.append(location3)
    >>> silo1.save()

Create Feed Product and 2 Lots::

    >>> feed_product = create_feed_product('Feed', 40, 25)
    >>> Lot = Model.get('stock.lot')
    >>> feed_lot1 = Lot()
    >>> feed_lot1.number = 'F001'
    >>> feed_lot1.product = feed_product
    >>> feed_lot1.save()
    >>> feed_lot2 = Lot()
    >>> feed_lot2.number = 'F002'
    >>> feed_lot2.product = feed_product
    >>> feed_lot2.save()

Set animal_type as 'individual' and specie in context to work as in the menus::

    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'individual'

Create individual I1 in location L1 arrived 10 days before::

    >>> config.user = individual_user.id
    >>> Animal = Model.get('farm.animal')
    >>> individual1 = Animal()
    >>> individual1.type = 'individual'
    >>> individual1.specie = specie
    >>> individual1.breed = breed
    >>> individual1.number = 'I1'
    >>> individual1.initial_location = location1
    >>> individual1.arrival_date = now.date() - datetime.timedelta(days=10)
    >>> individual1.save()

Create individual I2 in location L2 arrived 6 days before::

    >>> individual2 = Animal()
    >>> individual2.type = 'individual'
    >>> individual2.specie = specie
    >>> individual2.breed = breed
    >>> individual2.number = 'I2'
    >>> individual2.arrival_date = now.date() - datetime.timedelta(days=6)
    >>> individual2.initial_location = location2
    >>> individual2.save()

Move individual I2 to location L1 5 days before::

    >>> MoveEvent = Model.get('farm.move.event')
    >>> move_individual2 = MoveEvent()
    >>> move_individual2.farm = warehouse
    >>> move_individual2.animal = individual2
    >>> move_individual2.timestamp = now - datetime.timedelta(days=5)
    >>> move_individual2.from_location = location2
    >>> move_individual2.to_location = location1
    >>> move_individual2.save()
    >>> move_individual2.click('validate_event')

Create individuals I3, I4 and I5 in location L3 arrived 5 days before::

    >>> individual3 = Animal()
    >>> individual3.breed = breed
    >>> individual3.number = 'I3'
    >>> individual3.arrival_date = now.date() - datetime.timedelta(days=5)
    >>> individual3.initial_location = location3
    >>> individual4 = Animal()
    >>> individual4.breed = breed
    >>> individual4.number = 'I4'
    >>> individual4.arrival_date = now.date() - datetime.timedelta(days=5)
    >>> individual4.initial_location = location3
    >>> individual4.save()
    >>> individual5 = Animal()
    >>> individual5.breed = breed
    >>> individual5.number = 'I5'
    >>> individual5.arrival_date = now.date() - datetime.timedelta(days=5)
    >>> individual5.initial_location = location3
    >>> individual5.save()

Move individual I4 to location L2 3 days before::

    >>> move_individual4 = MoveEvent()
    >>> move_individual4.farm = warehouse
    >>> move_individual4.animal = individual4
    >>> move_individual4.timestamp = now - datetime.timedelta(days=3)
    >>> move_individual4.from_location = location3
    >>> move_individual4.to_location = location2
    >>> move_individual4.save()
    >>> move_individual4.click('validate_event')

Set animal_type as 'group' in context::

    >>> config._context['animal_type'] = 'group'

Create group G1 with 4 units in location L1 arrived 7 days before::

    >>> config.user = group_user.id
    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group1 = AnimalGroup()
    >>> animal_group1.specie = specie
    >>> animal_group1.breed = breed
    >>> animal_group1.arrival_date = now.date() - datetime.timedelta(days=7)
    >>> animal_group1.initial_location = location1
    >>> animal_group1.initial_quantity = 4
    >>> animal_group1.save()

Move 2 units of group G1 to location L2 1 day before::

    >>> move_group1 = MoveEvent()
    >>> move_group1.animal_type = 'group'
    >>> move_group1.specie = specie
    >>> move_group1.farm = warehouse
    >>> move_group1.animal_group = animal_group1
    >>> move_group1.timestamp = now - datetime.timedelta(days=1)
    >>> move_group1.from_location = location1
    >>> move_group1.to_location = location2
    >>> move_group1.quantity = 2
    >>> move_group1.save()
    >>> move_group1.click('validate_event')

Remove animal_type from context::

    >>> del config._context['animal_type']

Put 2000 Kg of first Lot of Feed into the silo 10 days before, and 1500 Kg of
second Lot of Feed 3 days before::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_move1 = Move()
    >>> provisioning_move1.product = feed_product
    >>> provisioning_move1.lot = feed_lot1
    >>> provisioning_move1.uom = feed_product.default_uom
    >>> provisioning_move1.quantity = 2000.00
    >>> provisioning_move1.from_location = company.party.supplier_location
    >>> provisioning_move1.to_location = silo1
    >>> provisioning_move1.planned_date = now.date() - datetime.timedelta(days=8)
    >>> provisioning_move1.effective_date = now.date() - datetime.timedelta(days=8)
    >>> provisioning_move1.company = company
    >>> provisioning_move1.unit_price = feed_product.template.list_price
    >>> provisioning_move1.save()
    >>> provisioning_move1.click('do')

    >>> provisioning_move2 = Move()
    >>> provisioning_move2.product = feed_product
    >>> provisioning_move2.lot = feed_lot2
    >>> provisioning_move2.uom = feed_product.default_uom
    >>> provisioning_move2.quantity = 1500.00
    >>> provisioning_move2.from_location = company.party.supplier_location
    >>> provisioning_move2.to_location = silo1
    >>> provisioning_move2.planned_date = now.date() - datetime.timedelta(days=3)
    >>> provisioning_move2.effective_date = now.date() - datetime.timedelta(days=3)
    >>> provisioning_move2.company = company
    >>> provisioning_move2.unit_price = feed_product.template.list_price
    >>> provisioning_move2.save()
    >>> provisioning_move2.click('do')

Create initial (real) feed inventory for silo S1 and silo's locations to fed at
8 days before::

    >>> FeedInventory = Model.get('farm.feed.inventory')
    >>> feed_inventory0 = FeedInventory()
    >>> feed_inventory0.location = silo1
    >>> feed_inventory0.timestamp = now - datetime.timedelta(days=8)
    >>> feed_inventory0.quantity = Decimal('2000.00')
    >>> feed_inventory0.uom = feed_product.default_uom
    >>> feed_inventory0.save()
    >>> feed_inventory0.state
    'draft'
    >>> set([l.id for l in feed_inventory0.dest_locations]) == set([
    ...         location1.id, location2.id, location3.id])
    True

Confirm initial feed inventory. As it is the initial, it doesn't have any line
nor feed event::

    >>> feed_inventory0.click('confirm')
    >>> feed_inventory0.state
    'validated'
    >>> feed_inventory0.feed_events
    []

Create first privisional feed inventory for silo S1 and silo's locations to fed
with 1000.00 Kg at 5 days before::

    >>> FeedProvisionalInventory = Model.get('farm.feed.provisional_inventory')
    >>> feed_provisional_inventory1 = FeedProvisionalInventory()
    >>> feed_provisional_inventory1.location = silo1
    >>> feed_provisional_inventory1.timestamp = now - datetime.timedelta(days=5)
    >>> feed_provisional_inventory1.quantity = Decimal('1000.00')
    >>> feed_provisional_inventory1.uom = feed_product.default_uom
    >>> feed_provisional_inventory1.save()
    >>> feed_provisional_inventory1.state
    'draft'

Confirm first provisional feed inventory and check it has an stock inventory in
state 'Done' and the median of Consumed Quantity per Animal/Day is
approximately 50 Kg::

    >>> feed_provisional_inventory1.click('confirm')
    >>> feed_provisional_inventory1.state
    'validated'
    >>> feed_provisional_inventory1.feed_events[0].feed_quantity_animal_day
    Decimal('52.6316')
    >>> feed_provisional_inventory1.inventory.state
    'done'

Create second privisional feed inventory for silo S1 and silo's locations to
fed with 1100.00 Kg at 2 days before::

    >>> feed_provisional_inventory2 = FeedProvisionalInventory(
    ...     location=silo1,
    ...     timestamp=(now - datetime.timedelta(days=2)),
    ...     quantity=Decimal('1100.00'),
    ...     uom=feed_product.default_uom,
    ...     )
    >>> feed_provisional_inventory2.save()
    >>> feed_provisional_inventory2.state
    'draft'

Confirm second provisional feed inventory and check it has an stock inventory
state 'Done' and the median of Consumed Quantity per Animal/Day is
approximately 50 Kg::

    >>> feed_provisional_inventory2.click('confirm')
    >>> feed_provisional_inventory2.state
    'validated'
    >>> feed_provisional_inventory2.feed_events[0].feed_quantity_animal_day
    Decimal('58.3333')
    >>> feed_provisional_inventory2.inventory.state
    'done'

Create (real) feed inventory for silo S1 and silo's locations to fed with
200.00 Kg at today::

    >>> feed_inventory1 = FeedInventory()
    >>> feed_inventory1.location = silo1
    >>> feed_inventory1.timestamp = now - datetime.timedelta(days=0)
    >>> feed_inventory1.quantity = Decimal('200.00')
    >>> feed_inventory1.uom = feed_product.default_uom
    >>> feed_inventory1.save()
    >>> feed_inventory1.state
    'draft'

Confirm feed inventory. Check the current stock of Silo is 200.00 Kg and the
current lot is the second Feed Lot::

    >>> feed_inventory1.click('confirm')
    >>> feed_inventory1.state
    'validated'
    >>> silo1.reload()
    >>> silo1.current_lot == feed_lot2
    True
    >>> config._context['locations'] = [silo1.id]
    >>> (Decimal(feed_lot2.quantity).quantize(Decimal('0.01'))
    ...     - Decimal('200.00')) < Decimal('0.01')
    True

Check provisional inventories doesn't have stock inventory related (it has been
removed)::

    >>> feed_provisional_inventory2.reload()
    >>> feed_provisional_inventory2.inventory is None
    True

====================
Feed Events Scenario
====================

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

Prepare farm locations::

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
    >>> silo1 = Location()
    >>> silo1.name = 'Silo 1'
    >>> silo1.code = 'S1'
    >>> silo1.type = 'storage'
    >>> silo1.parent = warehouse.storage_location
    >>> silo1.silo = True
    >>> silo1.locations_to_fed.append(location1)
    >>> silo1.locations_to_fed.append(location2)
    >>> silo1.save()

Create feed Product and Lot::

    >>> feed_product = create_feed_product('Feed', 40, 25)
    >>> Lot = Model.get('stock.lot')
    >>> feed_lot = Lot()
    >>> feed_lot.number = 'F001'
    >>> feed_lot.product = feed_product
    >>> feed_lot.save()

Put 5,1 Kg of feed into the silo location::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_move = Move()
    >>> provisioning_move.product = feed_product
    >>> provisioning_move.uom = feed_product.default_uom
    >>> provisioning_move.quantity = 5.20
    >>> provisioning_move.from_location = company.party.supplier_location
    >>> provisioning_move.to_location = silo1
    >>> provisioning_move.planned_date = now.date()
    >>> provisioning_move.effective_date = now.date()
    >>> provisioning_move.company = company
    >>> provisioning_move.lot = feed_lot
    >>> provisioning_move.unit_price = feed_product.template.list_price
    >>> provisioning_move.save()
    >>> provisioning_move.click('assign')
    >>> provisioning_move.click('do')

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'individual'

Create individual::

    >>> Animal = Model.get('farm.animal')
    >>> individual = Animal()
    >>> individual.type = 'individual'
    >>> individual.specie = specie
    >>> individual.breed = breed
    >>> individual.initial_location = location1
    >>> individual.save()
    >>> individual.location.code
    'L1'
    >>> individual.farm.code
    'WH'

Create individual feed event::

    >>> FeedEvent = Model.get('farm.feed.event')
    >>> ProductUom = Model.get('product.uom')
    >>> gr, = ProductUom.find([('name', '=', 'Gram')])
    >>> feed_individual = FeedEvent()
    >>> feed_individual.animal_type = 'individual'
    >>> feed_individual.specie = specie
    >>> feed_individual.farm = warehouse
    >>> feed_individual.animal = individual
    >>> feed_individual.timestamp = now
    >>> feed_individual.location = individual.location
    >>> feed_individual.feed_location = silo1
    >>> feed_individual.feed_product = feed_product
    >>> feed_individual.feed_lot = feed_lot
    >>> feed_individual.uom = gr
    >>> feed_individual.feed_quantity = Decimal('2100.0')
    >>> feed_individual.save()

Validate individual feed event::

    >>> feed_individual.click('validate_event')
    >>> feed_individual.reload()
    >>> feed_individual.state
    'validated'
    >>> feed_individual.feed_quantity_animal_day
    Decimal('2100.0000')
    >>> silo1.current_lot == feed_lot
    True

Create group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup()
    >>> animal_group.specie = specie
    >>> animal_group.breed = breed
    >>> animal_group.initial_location = location2
    >>> animal_group.initial_quantity = 4
    >>> animal_group.arrival_date = now.date() - datetime.timedelta(days=7)
    >>> animal_group.save()

Create animal_group feed event::

    >>> feed_animal_group = FeedEvent()
    >>> feed_animal_group.animal_type = 'group'
    >>> feed_animal_group.specie = specie
    >>> feed_animal_group.farm = warehouse
    >>> feed_animal_group.animal_group = animal_group
    >>> feed_animal_group.quantity = 4
    >>> feed_animal_group.timestamp = now
    >>> feed_animal_group.location = location2
    >>> feed_animal_group.feed_location = silo1
    >>> feed_animal_group.feed_product = feed_product
    >>> feed_animal_group.feed_lot = feed_lot
    >>> feed_animal_group.uom = gr
    >>> feed_animal_group.feed_quantity = Decimal('3000.0')
    >>> feed_animal_group.start_date = now.date() - datetime.timedelta(days=7)
    >>> feed_animal_group.end_date = now.date()
    >>> feed_animal_group.save()

Validate animal_group feed event::

    >>> feed_animal_group.click('validate_event')
    >>> feed_animal_group.reload()
    >>> feed_animal_group.state
    'validated'
    >>> feed_animal_group.feed_quantity_animal_day
    Decimal('107.1429')
    >>> animal_group.reload()
    >>> config._context['locations'] = [silo1.id]
    >>> lot = Lot(silo1.current_lot.id)
    >>> lot.quantity
    0.1
    >>> lot.product.quantity
    0.1

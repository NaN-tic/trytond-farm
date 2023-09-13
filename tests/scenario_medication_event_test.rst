==========================
Medication Events Scenario
==========================

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
    >>> from trytond.modules.farm.tests.tools import create_specie, create_users

Install module::

    >>> config = activate_modules('farm')

Compute now and today::

    >>> now = datetime.datetime.now()
    >>> today = datetime.date.today()

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
    >>> lab1 = Location()
    >>> lab1.name = 'Laboratory 1'
    >>> lab1.code = 'Lab1'
    >>> lab1.type = 'storage'
    >>> lab1.parent = warehouse.storage_location
    >>> lab1.save()

Create Medication Product and Lot::

    >>> ProductUom = Model.get('product.uom')
    >>> g, = ProductUom.find([('name', '=', 'Gram')])
    >>> ProductTemplate = Model.get('product.template')
    >>> medication_template = ProductTemplate()
    >>> medication_template.name = 'Pig Medication'
    >>> medication_template.default_uom = g
    >>> medication_template.type='goods'
    >>> medication_template.list_price=Decimal('40')
    >>> medication_template.save()
    >>> medication_product, = medication_template.products
    >>> medication_product.cost_price=Decimal('25')
    >>> medication_product.save()
    >>> Lot = Model.get('stock.lot')
    >>> medication_lot = Lot()
    >>> medication_lot.number = 'M001'
    >>> medication_lot.product = medication_product
    >>> medication_lot.save()

Put 500 g of medication into the laboratory location::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_move = Move()
    >>> provisioning_move.product = medication_product
    >>> provisioning_move.unit = g
    >>> provisioning_move.quantity = 500
    >>> provisioning_move.from_location = company.party.supplier_location
    >>> provisioning_move.to_location = lab1
    >>> provisioning_move.planned_date = now.date()
    >>> provisioning_move.effective_date = now.date()
    >>> provisioning_move.company = company
    >>> provisioning_move.lot = medication_lot
    >>> provisioning_move.unit_price = medication_product.template.list_price
    >>> provisioning_move.currency = company.currency
    >>> provisioning_move.save()
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

Create individual medication event::

    >>> MedicationEvent = Model.get('farm.medication.event')
    >>> medication_individual = MedicationEvent()
    >>> medication_individual.animal_type = 'individual'
    >>> medication_individual.specie = specie
    >>> medication_individual.farm = warehouse
    >>> medication_individual.animal = individual
    >>> medication_individual.timestamp = now
    >>> medication_individual.medication_end_date = now.date()
    >>> medication_individual.location = individual.location
    >>> medication_individual.feed_location = lab1
    >>> medication_individual.feed_product = medication_product
    >>> medication_individual.feed_lot = medication_lot
    >>> medication_individual.uom = g
    >>> medication_individual.feed_quantity = Decimal('154.0')
    >>> medication_individual.save()

Validate individual medication event::

    >>> medication_individual.click('validate_event')
    >>> medication_individual.reload()
    >>> medication_individual.state
    'validated'

Create group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup()
    >>> animal_group.specie = specie
    >>> animal_group.breed = breed
    >>> animal_group.initial_location = location2
    >>> animal_group.initial_quantity = 4
    >>> animal_group.arrival_date = now.date() - datetime.timedelta(days=1)
    >>> animal_group.save()

Create animal_group medication event::

    >>> medication_animal_group = MedicationEvent()
    >>> medication_animal_group.animal_type = 'group'
    >>> medication_animal_group.specie = specie
    >>> medication_animal_group.farm = warehouse
    >>> medication_animal_group.animal_group = animal_group
    >>> medication_animal_group.timestamp = now
    >>> medication_animal_group.location = location2
    >>> medication_animal_group.quantity = 4
    >>> medication_animal_group.feed_location = lab1
    >>> medication_animal_group.feed_product = medication_product
    >>> medication_animal_group.feed_lot = medication_lot
    >>> medication_animal_group.uom = g
    >>> medication_animal_group.feed_quantity = Decimal('320.0')
    >>> medication_animal_group.start_date = now.date() - datetime.timedelta(days=1)
    >>> medication_animal_group.medication_end_date = now.date() + datetime.timedelta(days=3)
    >>> medication_animal_group.save()

Validate animal_group medication event::

    >>> medication_animal_group.click('validate_event')
    >>> medication_animal_group.reload()
    >>> medication_animal_group.state
    'validated'
    >>> animal_group.reload()
    >>> config._context['locations'] = [lab1.id]
    >>> medication_lot = Lot(medication_lot.id)
    >>> medication_lot.quantity
    26.0

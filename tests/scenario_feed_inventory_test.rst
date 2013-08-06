====================
Feed Events Scenario
====================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal, ROUND_HALF_EVEN
    >>> from proteus import config, Model, Wizard
    >>> now = datetime.datetime.now()
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install farm::

    >>> Module = Model.get('ir.module.module')
    >>> modules = Module.find([
    ...         ('name', '=', 'farm'),
    ...         ])
    >>> Module.install([x.id for x in modules], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Create company::

    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Company = Model.get('company.company')
    >>> Party = Model.get('party.party')
    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='NaN·tic')
    >>> party.save()
    >>> company.party = party
    >>> currencies = Currency.find([('code', '=', 'EUR')])
    >>> if not currencies:
    ...     currency = Currency(name='Euro', symbol=u'€', code='EUR',
    ...         rounding=Decimal('0.01'), mon_grouping='[3, 3, 0]',
    ...         mon_decimal_point=',')
    ...     currency.save()
    ...     CurrencyRate(date=now.date() + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> individual_template = ProductTemplate(
    ...     name='Male Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> individual_template.save()
    >>> individual_product = Product(template=individual_template)
    >>> individual_product.save()
    >>> group_template = ProductTemplate(
    ...     name='Group of Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('30'),
    ...     cost_price=Decimal('20'))
    >>> group_template.save()
    >>> group_product = Product(template=group_template)
    >>> group_product.save()

Create sequence::

    >>> Sequence = Model.get('ir.sequence')
    >>> event_order_sequence = Sequence(
    ...     name='Event Order Pig Warehouse 1',
    ...     code='farm.event.order',
    ...     padding=4)
    >>> event_order_sequence.save()
    >>> individual_sequence = Sequence(
    ...     name='Individual Pig Warehouse 1',
    ...     code='farm.animal',
    ...     padding=4)
    >>> individual_sequence.save()
    >>> group_sequence = Sequence(
    ...     name='Groups Pig Warehouse 1',
    ...     code='farm.animal.group',
    ...     padding=4)
    >>> group_sequence.save()

Prepare farm locations L1, L2 and L3, and Silo location::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> production_location = Location(
    ...     name='Production Location',
    ...     code='PROD',
    ...     type='production',
    ...     parent=warehouse)
    >>> production_location.save()
    >>> warehouse.production_location=production_location
    >>> warehouse.save()
    >>> warehouse.reload()
    >>> production_location.reload()
    >>> location1_id, location2_id, location3_id = Location.create([{
    ...         'name': 'Location 1',
    ...         'code': 'L1',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Location 2',
    ...         'code': 'L2',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Location 3',
    ...         'code': 'L3',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }], config.context)
    >>> silo1 = Location(
    ...     name='Silo 1',
    ...     code='S1',
    ...     type='storage',
    ...     parent=warehouse.storage_location,
    ...     silo=True,
    ...     locations_to_fed=[location1_id, location2_id, location3_id])
    >>> silo1.save()

Create specie::

    >>> Specie = Model.get('farm.specie')
    >>> SpecieBreed = Model.get('farm.specie.breed')
    >>> SpecieFarmLine = Model.get('farm.specie.farm_line')
    >>> pigs_specie = Specie(
    ...     name='Pigs',
    ...     male_enabled=False,
    ...     female_enabled=False,
    ...     individual_enabled=True,
    ...     individual_product=individual_product,
    ...     group_enabled=True,
    ...     group_product=group_product,
    ...     removed_location=lost_found_location,
    ...     foster_location=lost_found_location,
    ...     lost_found_location=lost_found_location,
    ...     feed_lost_found_location=lost_found_location)
    >>> pigs_specie.save()
    >>> pigs_breed = SpecieBreed(
    ...     specie=pigs_specie,
    ...     name='Holland')
    >>> pigs_breed.save()
    >>> pigs_farm_line = SpecieFarmLine(
    ...     specie=pigs_specie,
    ...     event_order_sequence=event_order_sequence,
    ...     farm=warehouse,
    ...     has_individual=True,
    ...     individual_sequence=individual_sequence,
    ...     has_group=True,
    ...     group_sequence=group_sequence)
    >>> pigs_farm_line.save()

Create Feed Product and 2 Lots::

    >>> ProductUom = Model.get('product.uom')
    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> feed_template = ProductTemplate(
    ...     name='Pig Feed',
    ...     default_uom=kg,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> feed_template.save()
    >>> feed_product = Product(template=feed_template)
    >>> feed_product.save()
    >>> Lot = Model.get('stock.lot')
    >>> feed_lot1_id, feed_lot2_id = Lot.create([{
    ...         'number': 'F001',
    ...         'product': feed_product.id,
    ...         }, {
    ...         'number': 'F002',
    ...         'product': feed_product.id,
    ...         }], config.context)

Set animal_type as 'individual' and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'individual'

Create individual I1 in location L1 arrived 10 days before::

    >>> Animal = Model.get('farm.animal')
    >>> individual1 = Animal(
    ...     type='individual',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     number='I1',
    ...     arrival_date=(now.date() - datetime.timedelta(days=10)),
    ...     initial_location=location1_id)
    >>> individual1.save()

Create individual I2 in location L2 arrived 6 days before::

    >>> individual2 = Animal(
    ...     type='individual',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     number='I2',
    ...     arrival_date=(now.date() - datetime.timedelta(days=6)),
    ...     initial_location=location2_id)
    >>> individual2.save()

Move individual I2 to location L1 5 days before::

    >>> MoveEvent = Model.get('farm.move.event')
    >>> move_individual2 = MoveEvent(
    ...     farm=warehouse,
    ...     animal=individual2,
    ...     timestamp=(now - datetime.timedelta(days=5)),
    ...     from_location=location2_id,
    ...     to_location=location1_id)
    >>> move_individual2.save()
    >>> MoveEvent.validate_event([move_individual2.id], config.context)

Create individuals I3, I4 and I5 in location L3 arrived 5 days before::

    >>> individual3_id, individual4_id, individual5_id = Animal.create([{
    ...         'breed': pigs_breed.id,
    ...         'number': 'I3',
    ...         'arrival_date': now.date() - datetime.timedelta(days=5),
    ...         'initial_location': location3_id,
    ...         }, {
    ...         'breed': pigs_breed.id,
    ...         'number': 'I4',
    ...         'arrival_date': now.date() - datetime.timedelta(days=5),
    ...         'initial_location': location3_id,
    ...         }, {
    ...         'breed': pigs_breed.id,
    ...         'number': 'I5',
    ...         'arrival_date': now.date() - datetime.timedelta(days=5),
    ...         'initial_location': location3_id,
    ...         }], config.context)

Move individual I4 to location L2 3 days before::

    >>> move_individual4 = MoveEvent(
    ...     farm=warehouse,
    ...     animal=individual4_id,
    ...     timestamp=(now - datetime.timedelta(days=3)),
    ...     from_location=location3_id,
    ...     to_location=location2_id)
    >>> move_individual4.save()
    >>> MoveEvent.validate_event([move_individual4.id], config.context)

Set animal_type as 'group' in context::

    >>> config._context['animal_type'] = 'group'

Create group G1 with 4 units in location L1 arrived 7 days before::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group1 = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     arrival_date=(now.date() - datetime.timedelta(days=7)),
    ...     initial_location=location1_id,
    ...     initial_quantity=4)
    >>> animal_group1.save()

Move 2 units of group G1 to location L2 1 day before::

    >>> move_group1 = MoveEvent(
    ...     animal_type='group',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal_group=animal_group1,
    ...     timestamp=(now - datetime.timedelta(days=1)),
    ...     from_location=location1_id,
    ...     to_location=location2_id,
    ...     quantity=2)
    >>> move_group1.save()
    >>> MoveEvent.validate_event([move_group1.id], config.context)

Remove animal_type from context::

    >>> del config._context['animal_type']

Put 2000 Kg of first Lot of Feed into the silo 10 days before, and 1500 Kg of
second Lot of Feed 3 days before::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_moves = Move.create([{
    ...         'product': feed_product.id,
    ...         'lot': feed_lot1_id,
    ...         'uom': kg.id,
    ...         'quantity': 2000.00,
    ...         'from_location': party.supplier_location.id,
    ...         'to_location': silo1.id,
    ...         'planned_date': now.date() - datetime.timedelta(days=8),
    ...         'effective_date': now.date() - datetime.timedelta(days=8),
    ...         'company': config.context.get('company'),
    ...         'unit_price': feed_product.template.list_price,
    ...         }, {
    ...         'product': feed_product.id,
    ...         'lot': feed_lot2_id,
    ...         'uom': kg.id,
    ...         'quantity': 1500.00,
    ...         'from_location': party.supplier_location.id,
    ...         'to_location': silo1.id,
    ...         'planned_date': now.date() - datetime.timedelta(days=3),
    ...         'effective_date': now.date() - datetime.timedelta(days=3),
    ...         'company': config.context.get('company'),
    ...         'unit_price': feed_product.template.list_price,
    ...         }], config.context)
    >>> Move.assign(provisioning_moves, config.context)
    >>> Move.do(provisioning_moves, config.context)

Create initial (real) feed inventory for silo S1 and silo's locations to fed at
8 days before::

    >>> FeedInventory = Model.get('farm.feed.inventory')
    >>> feed_inventory0 = FeedInventory(
    ...     location=silo1,
    ...     timestamp=(now - datetime.timedelta(days=8)),
    ...     quantity=Decimal('2000.00'),
    ...     uom=kg,
    ...     )
    >>> feed_inventory0.save()
    >>> feed_inventory0.state
    u'draft'
    >>> set([l.id for l in feed_inventory0.dest_locations]) == set([
    ...         location1_id, location2_id, location3_id])
    True

Confirm initial feed inventory. As it is the initial, it doesn't have any line
nor feed event::

    >>> FeedInventory.confirm([feed_inventory0.id], config.context)
    >>> feed_inventory0.reload()
    >>> feed_inventory0.state
    u'validated'
    >>> feed_inventory0.lines
    []
    >>> feed_inventory0.feed_events
    []

.. Create first privisional feed inventory for silo S1 and silo's locations to fed
.. with 1000.00 Kg at 5 days before::
.. 
..     >>> FeedProvisionalInventory = Model.get('farm.feed.provisional_inventory')
..     >>> feed_provisional_inventory1 = FeedProvisionalInventory(
..     ...     location=silo1,
..     ...     timestamp=(now - datetime.timedelta(days=5)),
..     ...     quantity=Decimal('1000.00'),
..     ...     uom=kg,
..     ...     )
..     >>> feed_provisional_inventory1.save()
..     >>> feed_provisional_inventory1.state
..     u'draft'
.. 
.. Confirm first provisional feed inventory and check it has an stock inventory in
.. state 'Done' and the median of Consumed Quantity per Animal/Day is
.. approximately 50 Kg::
.. 
..     >>> FeedProvisionalInventory.confirm([feed_provisional_inventory1.id],
..     ...     config.context)
..     >>> feed_provisional_inventory1.reload()
..     >>> feed_provisional_inventory1.state
..     u'validated'
..     >>> (feed_provisional_inventory1.lines[0].consumed_qty_animal_day
..     ...     - Decimal('50.0')) < Decimal('3.0')
..     True
..     >>> feed_provisional_inventory1.inventory.state
..     u'done'
.. 
.. Create second privisional feed inventory for silo S1 and silo's locations to
.. fed with 1100.00 Kg at 2 days before::
.. 
..     >>> feed_provisional_inventory2 = FeedProvisionalInventory(
..     ...     location=silo1,
..     ...     timestamp=(now - datetime.timedelta(days=2)),
..     ...     quantity=Decimal('1100.00'),
..     ...     uom=kg,
..     ...     )
..     >>> feed_provisional_inventory2.save()
..     >>> feed_provisional_inventory2.state
..     u'draft'
.. 
.. Confirm second provisional feed inventory and check it has an stock inventory
.. state 'Done' and the median of Consumed Quantity per Animal/Day is
.. approximately 50 Kg::
.. 
..     >>> FeedProvisionalInventory.confirm([feed_provisional_inventory2.id],
..     ...     config.context)
..     >>> feed_provisional_inventory2.reload()
..     >>> feed_provisional_inventory2.state
..     u'validated'
..     >>> (feed_provisional_inventory2.lines[0].consumed_qty_animal_day
..     ...     - Decimal('50.0')) < Decimal('3.0')
..     True
..     >>> feed_provisional_inventory2.inventory.state
..     u'done'

Create (real) feed inventory for silo S1 and silo's locations to fed with
200.00 Kg at today::

    >>> feed_inventory1 = FeedInventory(
    ...     location=silo1,
    ...     timestamp=(now - datetime.timedelta(days=0)),
    ...     quantity=Decimal('200.00'),
    ...     uom=kg,
    ...     )
    >>> feed_inventory1.save()
    >>> feed_inventory1.state
    u'draft'

Confirm feed inventory. Check the current stock of Silo is 200.00 Kg and the
current lot is the second Feed Lot::

    >>> FeedInventory.confirm([feed_inventory1.id], config.context)
    >>> feed_inventory1.reload()
    >>> feed_inventory1.state
    u'validated'
    >>> silo1.reload()
    >>> silo1.current_lot.id == feed_lot2_id
    True
    >>> unused = config.set_context({'locations': [silo1.id]})
    >>> (Decimal(Lot(feed_lot2_id).quantity).quantize(Decimal('0.01'))
    ...     - Decimal('200.00')) < Decimal('0.01')
    True


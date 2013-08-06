====================
Feed Events Scenario
====================

=============
General Setup
=============

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
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

Prepare farm locations::

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
    >>> location1_id, location2_id = Location.create([{
    ...         'name': 'Location 1',
    ...         'code': 'L1',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Location 2',
    ...         'code': 'L2',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }], config.context)
    >>> silo1 = Location(
    ...     name='Silo 1',
    ...     code='S1',
    ...     type='storage',
    ...     parent=warehouse.storage_location,
    ...     silo=True,
    ...     locations_to_fed=[location1_id, location2_id])
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

Create feed Product and Lot::

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
    >>> feed_lot = Lot(
    ...     number='F001',
    ...     product=feed_product)
    >>> feed_lot.save()

Put 5,1 Kg of feed into the silo location::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_moves = Move.create([{
    ...         'product': feed_product.id,
    ...         'uom': kg.id,
    ...         'quantity': 5.10,
    ...         'from_location': party.supplier_location.id,
    ...         'to_location': silo1.id,
    ...         'planned_date': now.date(),
    ...         'effective_date': now.date(),
    ...         'company': config.context.get('company'),
    ...         'lot': feed_lot.id,
    ...         'unit_price': feed_product.template.list_price,
    ...         }],
    ...     config.context)
    >>> Move.assign(provisioning_moves, config.context)
    >>> Move.do(provisioning_moves, config.context)

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'individual'

Create individual::

    >>> Animal = Model.get('farm.animal')
    >>> individual = Animal(
    ...     type='individual',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=location1_id)
    >>> individual.save()
    >>> individual.location.code
    u'L1'
    >>> individual.farm.code
    u'WH'

Create individual feed event::

    >>> FeedEvent = Model.get('farm.feed.event')
    >>> gr, = ProductUom.find([('name', '=', 'Gram')])
    >>> feed_individual = FeedEvent(
    ...     animal_type='individual',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal=individual,
    ...     timestamp=now,
    ...     location=individual.location,
    ...     feed_location=silo1,
    ...     feed_product=feed_product,
    ...     feed_lot=feed_lot,
    ...     uom=gr,
    ...     quantity=Decimal('2100.0'))
    >>> feed_individual.save()

Validate individual feed event::

    >>> FeedEvent.validate_event([feed_individual.id], config.context)
    >>> feed_individual.reload()
    >>> feed_individual.state
    u'validated'
    >>> silo1.current_lot.id == feed_lot.id
    True

Create group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=location2_id,
    ...     initial_quantity=4)
    >>> animal_group.save()

Create animal_group feed event::

    >>> feed_animal_group = FeedEvent(
    ...     animal_type='group',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal_group=animal_group,
    ...     timestamp=now,
    ...     location=location2_id,
    ...     feed_location=silo1,
    ...     feed_product=feed_product,
    ...     feed_lot=feed_lot,
    ...     uom=gr,
    ...     quantity=Decimal('3000.0'),
    ...     start_date=(now.date() - datetime.timedelta(days=7)),
    ...     end_date=now)
    >>> feed_animal_group.save()

Validate animal_group feed event::

    >>> FeedEvent.validate_event([feed_animal_group.id], config.context)
    >>> feed_animal_group.reload()
    >>> feed_animal_group.state
    u'validated'
    >>> animal_group.reload()
    >>> unused = config.set_context({'locations': [silo1.id]})
    >>> silo1.current_lot.reload()
    >>> silo1.current_lot.quantity
    0.0
    >>> silo1.current_lot.product.reload()
    >>> silo1.current_lot.product.quantity
    0.0

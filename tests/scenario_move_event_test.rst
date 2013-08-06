====================
Move Events Scenario
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

Create specie::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
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
    ...     farm=warehouse,
    ...     event_order_sequence=event_order_sequence,
    ...     has_individual=True,
    ...     individual_sequence=individual_sequence,
    ...     has_group=True,
    ...     group_sequence=group_sequence)
    >>> pigs_farm_line.save()

Create farm locations::

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

Create individual move event::

    >>> MoveEvent = Model.get('farm.move.event')
    >>> move_individual = MoveEvent(
    ...     animal_type='individual',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal=individual,
    ...     timestamp=now,
    ...     from_location=individual.location,
    ...     to_location=location2_id,
    ...     weight=Decimal('80.50'))
    >>> move_individual.save()

Animal doesn't chage its values::

    >>> individual.reload()
    >>> individual.location.id == location1_id
    True
    >>> individual.current_weight

Validate individual move event::

    >>> MoveEvent.validate_event([move_individual.id], config.context)
    >>> move_individual.reload()
    >>> move_individual.state
    u'validated'
    >>> individual.reload()
    >>> individual.location.id == location2_id
    True
    >>> individual.current_weight.weight
    Decimal('80.50')

Create group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=location2_id,
    ...     initial_quantity=4)
    >>> animal_group.save()
    >>> unused = config.set_context({
    ...         'locations': [location2_id]})
    >>> animal_group.reload()
    >>> animal_group.lot.quantity
    4.0

Create animal_group move event::

    >>> MoveEvent = Model.get('farm.move.event')
    >>> move_animal_group = MoveEvent(
    ...     animal_type='group',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal_group=animal_group,
    ...     timestamp=now,
    ...     from_location=location2_id,
    ...     to_location=location1_id,
    ...     quantity=3,
    ...     weight=Decimal('80.50'))
    >>> move_animal_group.save()

Group doesn't chage its values::

    >>> animal_group.reload()
    >>> animal_group.current_weight
    >>> animal_group.lot.quantity
    4.0

Validate animal_group move event::

    >>> MoveEvent.validate_event([move_animal_group.id], config.context)
    >>> move_animal_group.reload()
    >>> move_animal_group.state
    u'validated'
    >>> animal_group.reload()
    >>> animal_group.current_weight.weight
    Decimal('80.50')
    >>> animal_group.lot.quantity
    1.0
    >>> unused = config.set_context({'locations': [location1_id]})
    >>> animal_group.reload()
    >>> animal_group.lot.quantity
    3.0
    >>> unused = config.set_context({'locations': None})

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
    >>> from operator import attrgetter
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> now = datetime.datetime.now()
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install farm::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'farm'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])
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
    >>> female_template = ProductTemplate(
    ...     name='Female Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> female_template.save()
    >>> female_product = Product(template=female_template)
    >>> female_product.save()
    >>> semen_template = ProductTemplate(
    ...     name='Pig Semen',
    ...     default_uom=cm3,
    ...     type='goods',
    ...     consumable=True,
    ...     list_price=Decimal('400'),
    ...     cost_price=Decimal('250'))
    >>> semen_template.save()
    >>> semen_product = Product(template=semen_template)
    >>> semen_product.save()

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
    >>> female_sequence = Sequence(
    ...     name='Female Pig Warehouse 1',
    ...     code='farm.animal',
    ...     padding=4)
    >>> female_sequence.save()
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
    ...     female_enabled=True,
    ...     female_product=female_product,
    ...     semen_product=semen_product,
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
    ...     has_female=True,
    ...     female_sequence=female_sequence,
    ...     has_group=True,
    ...     group_sequence=group_sequence)
    >>> pigs_farm_line.save()

Get locations::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> production_location, = Location.find([('code', '=', 'PROD')])
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

Create farm users::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

    >>> farm_user = User()
    >>> farm_user.name = 'Farm'
    >>> farm_user.login = 'farm'
    >>> farm_user.main_company = company
    >>> farm_group, = Group.find([('name', '=', 'Farm / Females')])
    >>> farm_user.groups.append(farm_group)
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> farm_user.groups.append(stock_group)
    >>> farm_user.save()

    >>> individual_user = User()
    >>> individual_user.name = 'Individuals'
    >>> individual_user.login = 'individuals'
    >>> individual_user.main_company = company
    >>> individual_group, = Group.find([('name', '=', 'Farm / Individuals')])
    >>> individual_user.groups.append(individual_group)
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> individual_user.groups.append(stock_group)
    >>> individual_user.save()

    >>> group_user = User()
    >>> group_user.name = 'Groups'
    >>> group_user.login = 'groups'
    >>> group_user.main_company = company
    >>> group_group, = Group.find([('name', '=', 'Farm / Groups')])
    >>> group_user.groups.append(group_group)
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> group_user.groups.append(stock_group)
    >>> group_user.save()

    >>> female_user = User()
    >>> female_user.name = 'Females'
    >>> female_user.login = 'females'
    >>> female_user.main_company = company
    >>> female_group, = Group.find([('name', '=', 'Farm / Females')])
    >>> female_user.groups.append(female_group)
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> female_user.groups.append(stock_group)
    >>> female_user.save()

Create individual::

    >>> config.user = individual_user.id
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

    >>> move_individual.click('validate_event')
    >>> move_individual.state
    u'validated'
    >>> individual.reload()
    >>> individual.location.id == location2_id
    True
    >>> individual.current_weight.weight
    Decimal('80.50')

Create individual move event changing cost price::

    >>> config.user = stock_user.id
    >>> individual.lot.cost_price
    Decimal('25')
    >>> config.user = individual_user.id
    >>> move_individual = MoveEvent(
    ...     animal_type='individual',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal=individual,
    ...     timestamp=now,
    ...     from_location=individual.location,
    ...     to_location=location1_id)
    >>> move_individual.unit_price = Decimal('30.0')
    >>> move_individual.save()
    >>> move_individual.unit_price
    Decimal('30.0')
    >>> move_individual.click('validate_event')
    >>> move_individual.state
    u'validated'
    >>> individual.reload()
    >>> individual.location.id == location1_id
    True
    >>> config.user = stock_user.id
    >>> individual.lot.cost_price
    Decimal('30.0')
    >>> move_cost_line, = [x for x in individual.lot.cost_lines
    ...     if x.origin == move_individual]
    >>> move_cost_line.unit_price
    Decimal('5.0')

Create group::

    >>> config.user = group_user.id
    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=location2_id,
    ...     initial_quantity=4)
    >>> animal_group.save()
    >>> config.user = stock_user.id
    >>> with config.set_context({'locations': [location2_id]}):
    ...     animal_group.reload()
    ...     animal_group.lot.quantity
    4.0

Create animal_group move event::

    >>> config.user = group_user.id
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

    >>> config.user = stock_user.id
    >>> animal_group.reload()
    >>> animal_group.current_weight
    >>> with config.set_context({'locations': [location2_id]}):
    ...     animal_group.reload()
    ...     animal_group.lot.quantity
    4.0

Validate animal_group move event::

    >>> config.user = group_user.id
    >>> move_animal_group.click('validate_event')
    >>> move_animal_group.state
    u'validated'
    >>> animal_group.reload()
    >>> animal_group.current_weight.weight
    Decimal('80.50')
    >>> config.user = stock_user.id
    >>> with config.set_context({'locations': [location2_id]}):
    ...     animal_group.lot.quantity
    1.0
    >>> with config.set_context({'locations': [location1_id]}):
    ...     animal_group.reload()
    ...     animal_group.lot.quantity
    3.0


When moving a non weaned female its group should be also moved::

    >>> config.user = female_user.id
    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'female'
    >>> Animal = Model.get('farm.animal')
    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> female = Animal(initial_location=location1_id)
    >>> female.save()
    >>> now = datetime.datetime.now()
    >>> inseminate_event = InseminationEvent()
    >>> inseminate_event.farm = warehouse
    >>> inseminate_event.animal = female
    >>> inseminate_event.timestamp = datetime.datetime.now()
    >>> inseminate_event.click('validate_event')
    >>> now = datetime.datetime.now()
    >>> diagnosis_event = PregnancyDiagnosisEvent()
    >>> diagnosis_event.farm = warehouse
    >>> diagnosis_event.animal = female
    >>> diagnosis_event.timestamp = datetime.datetime.now()
    >>> diagnosis_event.result = 'positive'
    >>> diagnosis_event.click('validate_event')
    >>> farrow_event = FarrowingEvent()
    >>> farrow_event.farm = warehouse
    >>> farrow_event.animal = female
    >>> farrow_event.timestamp = datetime.datetime.now()
    >>> farrow_event.live = 6
    >>> farrow_event.click('validate_event')
    >>> female.reload()
    >>> farrowing_group = female.farrowing_group
    >>> move_female = MoveEvent(
    ...     farm=warehouse,
    ...     animal=female,
    ...     timestamp=now,
    ...     from_location=female.location.id,
    ...     to_location=location2_id,
    ...     weight=Decimal('80.50'))
    >>> move_female.click('validate_event')
    >>> female.reload()
    >>> female.location.id == location2_id
    True
    >>> farrowing_event, = MoveEvent.find([
    ...     ('animal_group', '=', farrowing_group.id),
    ...     ], limit=1)
    >>> farrowing_event.state
    u'validated'
    >>> farrowing_event.weight
    >>> config.user = stock_user.id
    >>> farrowing_event.from_location.id == location1_id
    True
    >>> farrowing_event.to_location.id == location2_id
    True
    >>> with config.set_context({'locations': [location2_id]}):
    ...     farrowing_group.reload()
    ...     farrowing_group.lot.quantity
    6.0

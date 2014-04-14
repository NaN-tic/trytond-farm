==============================
Transformation Events Scenario
==============================

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
    >>> liter, = ProductUom.find([('name', '=', 'Liter')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> male_template = ProductTemplate(
    ...     name='Male Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> male_template.save()
    >>> male_product = Product(template=male_template)
    >>> male_product.save()
    >>> semen_template = ProductTemplate(
    ...     name='Pig Semen',
    ...     default_uom=liter,
    ...     type='goods',
    ...     list_price=Decimal('400'),
    ...     cost_price=Decimal('250'))
    >>> semen_template.save()
    >>> semen_product = Product(template=semen_template)
    >>> semen_product.save()
    >>> female_template = ProductTemplate(
    ...     name='Female Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> female_template.save()
    >>> female_product = Product(template=female_template)
    >>> female_product.save()
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
    >>> male_sequence = Sequence(
    ...     name='Male Pig Warehouse 1',
    ...     code='farm.animal',
    ...     padding=4)
    >>> male_sequence.save()
    >>> semen_lot_sequence = Sequence(
    ...     name='Semen Extracted Lot Pig Warehouse 1',
    ...     code='stock.lot',
    ...     padding=4)
    >>> semen_lot_sequence.save()
    >>> semen_dose_lot_sequence = Sequence(
    ...     name='Semen Dose Lot Pig Warehouse 1',
    ...     code='stock.lot',
    ...     padding=4)
    >>> semen_dose_lot_sequence.save()
    >>> female_sequence = Sequence(
    ...     name='Female Pig Warehouse 1',
    ...     code='farm.animal',
    ...     padding=4)
    >>> female_sequence.save()
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

Prepare locations::

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

Create specie::

    >>> Specie = Model.get('farm.specie')
    >>> SpecieBreed = Model.get('farm.specie.breed')
    >>> SpecieFarmLine = Model.get('farm.specie.farm_line')
    >>> pigs_specie = Specie(
    ...     name='Pigs',
    ...     male_enabled=True,
    ...     male_product=male_product,
    ...     semen_product=semen_product,
    ...     female_enabled=True,
    ...     female_product=female_product,
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
    ...     has_male=True,
    ...     male_sequence=male_sequence,
    ...     semen_lot_sequence=semen_lot_sequence,
    ...     dose_lot_sequence=semen_dose_lot_sequence,
    ...     has_female=True,
    ...     female_sequence=female_sequence,
    ...     has_individual=True,
    ...     individual_sequence=individual_sequence,
    ...     has_group=True,
    ...     group_sequence=group_sequence)
    >>> pigs_farm_line.save()

Create male to be transformed to individual::

    >>> Animal = Model.get('farm.animal')
    >>> male_to_individual = Animal(
    ...     type='male',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> male_to_individual.save()
    >>> male_to_individual.location.code
    u'STO'
    >>> male_to_individual.farm.code
    u'WH'

Create transformation event::

    >>> TransformationEvent = Model.get('farm.transformation.event')
    >>> transform_male_to_individual = TransformationEvent(
    ...     animal_type='male',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=male_to_individual,
    ...     from_location=male_to_individual.location,
    ...     to_animal_type='individual',
    ...     to_location=warehouse.storage_location)
    >>> transform_male_to_individual.save()

Animal doesn't chage its values::

    >>> male_to_individual.reload()
    >>> male_to_individual.location=warehouse.storage_location
    >>> male_to_individual.active
    1

Validate transformation event::

    >>> TransformationEvent.validate_event([transform_male_to_individual.id],
    ...     config.context)
    >>> transform_male_to_individual.reload()
    >>> transform_male_to_individual.state
    u'validated'
    >>> to_animal = transform_male_to_individual.to_animal
    >>> to_animal.active
    1
    >>> to_animal.type
    u'individual'
    >>> len(to_animal.lot.cost_lines) == 1
    True
    >>> to_animal.lot.cost_price == individual_template.cost_price
    True
    >>> to_animal.location == transform_male_to_individual.to_location
    True
    >>> male_to_individual.reload()
    >>> male_to_individual.removal_date == today
    True
    >>> male_to_individual.location == warehouse.production_location
    True

..  >>> male_to_individual.active
..  0

Create female to be transformed to a new group::

    >>> female_to_group = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> female_to_group.save()
    >>> female_to_group.location.code
    u'STO'
    >>> female_to_group.farm.code
    u'WH'

Create transformation event::

    >>> transform_female_to_group = TransformationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female_to_group,
    ...     from_location=female_to_group.location,
    ...     to_animal_type='group',
    ...     to_location=warehouse.storage_location)
    >>> transform_female_to_group.save()

Animal doesn't chage its values::

    >>> female_to_group.reload()
    >>> female_to_group.location=warehouse.storage_location
    >>> female_to_group.active
    1

Validate transformation event::

    >>> TransformationEvent.validate_event([transform_female_to_group.id],
    ...     config.context)
    >>> transform_female_to_group.reload()
    >>> transform_female_to_group.state
    u'validated'
    >>> to_group = transform_female_to_group.to_animal_group
    >>> to_group.active
    1
    >>> to_animal.initial_location == transform_female_to_group.to_location
    True
    >>> female_to_group.reload()
    >>> female_to_group.removal_date == today
    True
    >>> female_to_group.location == warehouse.production_location
    True

..  >>> female_to_group.active
..  0

..  TODO maybe more test over group: quantitites, locations...

Create individual to be transformed to female::

    >>> individual_to_female = Animal(
    ...     type='individual',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     sex='female',
    ...     initial_location=warehouse.storage_location)
    >>> individual_to_female.save()
    >>> individual_to_female.location.code
    u'STO'
    >>> individual_to_female.farm.code
    u'WH'

Create transformation event::

    >>> transform_individual_to_female = TransformationEvent(
    ...     animal_type='individual',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=individual_to_female,
    ...     from_location=individual_to_female.location,
    ...     to_animal_type='female',
    ...     to_location=warehouse.storage_location)
    >>> transform_individual_to_female.save()

Animal doesn't chage its values::

    >>> individual_to_female.reload()
    >>> individual_to_female.location=warehouse.storage_location
    >>> individual_to_female.active
    1

Validate transformation event::

    >>> TransformationEvent.validate_event([transform_individual_to_female.id],
    ...     config.context)
    >>> transform_individual_to_female.reload()
    >>> transform_individual_to_female.state
    u'validated'
    >>> to_animal = transform_individual_to_female.to_animal
    >>> to_animal.active
    1
    >>> to_animal.type
    u'female'
    >>> to_animal.location == transform_individual_to_female.to_location
    True
    >>> individual_to_female.reload()
    >>> individual_to_female.removal_date == today
    True
    >>> individual_to_female.location == warehouse.production_location
    True

..  >>> individual_to_female.active
..  0

Create individual to be transformed to existing group::

    >>> individual_to_group = Animal(
    ...     type='individual',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     sex='undetermined',
    ...     initial_location=warehouse.storage_location)
    >>> individual_to_group.save()
    >>> individual_to_group.location.code
    u'STO'
    >>> individual_to_group.farm.code
    u'WH'

Create existing group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> context_tmp = config.context.copy()
    >>> config._context.update({
    ...     'animal_type': 'group',
    ...     })
    >>> existing_group = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location,
    ...     initial_quantity=4,
    ...     arrival_date=(today - relativedelta(days=3)),
    ...     )
    >>> existing_group.save()
    >>> config._context = context_tmp

Create transformation event::

    >>> transform_individual_to_group = TransformationEvent(
    ...     animal_type='individual',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=individual_to_group,
    ...     from_location=individual_to_group.location,
    ...     to_animal_type='group',
    ...     to_location=warehouse.storage_location,
    ...     to_animal_group=existing_group)
    >>> transform_individual_to_group.save()

Validate transformation event::

    >>> TransformationEvent.validate_event([transform_individual_to_group.id],
    ...     config.context)
    >>> transform_individual_to_group.reload()
    >>> transform_individual_to_group.state
    u'validated'
    >>> individual_to_group.reload()
    >>> individual_to_group.removal_date == today
    True
    >>> individual_to_group.location == warehouse.production_location
    True

..  >>> individual_to_group.active
..  0

    >>> existing_group.reload()
    >>> existing_group.active
    1

..  TODO maybe more test over group: quantitites, locations...

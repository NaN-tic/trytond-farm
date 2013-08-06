=======================
Weaning Events Scenario
=======================

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

Create specie's products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> female_template = ProductTemplate(
    ...     name='Female Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> female_template.save()
    >>> female_product = Product(template=female_template)
    >>> female_product.save()
    >>> group_template = ProductTemplate(
    ...     name='Group of Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('30'),
    ...     cost_price=Decimal('20'))
    >>> group_template.save()
    >>> group_product = Product(template=group_template)
    >>> group_product.save()
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
    >>> other_location_ids = Location.create([{
    ...         'name': 'Other Location 1',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Other Location 2',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Other Location 3',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Other Location 4',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }, {
    ...         'name': 'Other Location 5',
    ...         'type': 'storage',
    ...         'parent': warehouse.storage_location.id,
    ...         }], config.context)

Create specie::

    >>> Specie = Model.get('farm.specie')
    >>> SpecieBreed = Model.get('farm.specie.breed')
    >>> SpecieFarmLine = Model.get('farm.specie.farm_line')
    >>> pigs_specie = Specie(
    ...     name='Pigs',
    ...     male_enabled=False,
    ...     female_enabled=True,
    ...     female_product=female_product,
    ...     semen_product=semen_product,
    ...     individual_enabled=False,
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
    ...     has_male=False,
    ...     has_female=True,
    ...     female_sequence=female_sequence,
    ...     has_individual=False,
    ...     has_group=True,
    ...     group_sequence=group_sequence)
    >>> pigs_farm_line.save()

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'female'

Create some females to be inseminated, check their pregnancy state, farrow them
to could test different weaning events::

    >>> Animal = Model.get('farm.animal')
    >>> female_ids = Animal.create([{
    ...         'type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'breed': pigs_breed.id,
    ...         'initial_location': other_location_ids[0],
    ...         }, {
    ...         'type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'breed': pigs_breed.id,
    ...         'initial_location': other_location_ids[1],
    ...         }, {
    ...         'type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'breed': pigs_breed.id,
    ...         'initial_location': other_location_ids[2],
    ...         }, {
    ...         'type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'breed': pigs_breed.id,
    ...         'initial_location': other_location_ids[3],
    ...         }], config.context)
    >>> females = [Animal(i) for i in female_ids]
    >>> all(f.farm.code == 'WH' for f in females)
    True
    >>> not any(bool(f.current_cycle) for f in females)
    True
    >>> all(f.state == 'prospective' for f in females)
    True

Create insemination events for the females without dose BoM nor Lot and
validate them and check the females state::

    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> now = datetime.datetime.now()
    >>> inseminate_events = InseminationEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': f.id,
    ...         } for f in females], config.context)
    >>> InseminationEvent.validate_event(inseminate_events, config.context)
    >>> all(InseminationEvent(i).state == 'validated'
    ...     for i in inseminate_events)
    True
    >>> females = [Animal(i) for i in female_ids]
    >>> all(f.current_cycle.state == 'mated' for f in females)
    True
    >>> all(f.state == 'mated' for f in females)
    True

Create pregnancy diagnosis events with positive result, validate them and check
females state and pregnancy state::

    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> now = datetime.datetime.now()
    >>> diagnosis_events = PregnancyDiagnosisEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': f.id,
    ...         'result': 'positive',
    ...         } for f in females], config.context)
    >>> PregnancyDiagnosisEvent.validate_event(diagnosis_events, config.context)
    >>> all(PregnancyDiagnosisEvent(i).state == 'validated'
    ...     for i in diagnosis_events)
    True
    >>> females = [Animal(i) for i in female_ids]
    >>> all(f.current_cycle.pregnant for f in females)
    True
    >>> all(f.current_cycle.state == 'pregnant' for f in females)
    True

Create a farrowing event for each female with 6, 7, 8 and 9 lives respectively,
validate them and check females state and female's live values::

    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> now = datetime.datetime.now()
    >>> farrow_events = FarrowingEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': females[i].id,
    ...         'live': 6 + i,
    ...         } for i in range(0, len(females))], config.context)
    >>> FarrowingEvent.validate_event(farrow_events, config.context)
    >>> all(FarrowingEvent(i).state == 'validated' for i in farrow_events)
    True
    >>> females = [Animal(i) for i in female_ids]
    >>> not any(f.current_cycle.pregnant for f in females)
    True
    >>> all(f.current_cycle.state == 'lactating' for f in females)
    True
    >>> all(f.state == 'mated' for f in females)
    True
    >>> females[0].current_cycle.live
    6
    >>> females[-1].current_cycle.live == (6 + len(females) - 1)
    True

Create a weaning event for first female (6 lives) with 6 as quantity, with
current female location as destination location for female and group and
without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female1 = females[0]
    >>> weaning_event1 = WeaningEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     quantity=6,
    ...     female_to_location=female1.location,
    ...     weaned_to_location=female1.location)
    >>> weaning_event1.save()

Validate weaning event::

    >>> WeaningEvent.validate_event([weaning_event1.id], config.context)
    >>> weaning_event1.reload()
    >>> weaning_event1.state
    u'validated'

Check female's current cycle state is 'unmated' and its weaned value is 6 and
the weaning event doesn't have female, weaned nor lost moves::

    >>> female1.reload()
    >>> female1.current_cycle.state
    u'unmated'
    >>> female1.current_cycle.weaned
    6
    >>> female1.current_cycle.weaning_event.female_move
    >>> female1.current_cycle.weaning_event.weaned_move
    >>> female1.current_cycle.weaning_event.lost_move

Create a weaning event for second female (7 lives) with 6 as quantity, with
current female location as destination of weaned group but not for destination
female location and without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female2 = females[1]
    >>> weaning_event2 = WeaningEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female2,
    ...     quantity=6,
    ...     female_to_location=other_location_ids[-1],
    ...     weaned_to_location=female2.location)
    >>> weaning_event2.save()

Validate weaning event::

    >>> WeaningEvent.validate_event([weaning_event2.id], config.context)
    >>> weaning_event2.reload()
    >>> weaning_event2.state
    u'validated'

Check female's current cycle state is 'unmated' and its weaned value is 6 and
the weaning event has female and lost moves but not weaned group move::

    >>> female2.reload()
    >>> female2.current_cycle.state
    u'unmated'
    >>> female2.current_cycle.weaned
    6
    >>> female2.current_cycle.weaning_event.female_move.state
    u'done'
    >>> female2.current_cycle.weaning_event.weaned_move
    >>> female2.current_cycle.weaning_event.lost_move.quantity
    1.0

Create a weaning event for third female (8 lives) with 8 as quantity, with
different destination location for female and group and without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female3 = females[2]
    >>> weaning_event3 = WeaningEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female3,
    ...     quantity=8,
    ...     female_to_location=other_location_ids[-1],
    ...     weaned_to_location=other_location_ids[-1])
    >>> weaning_event3.save()

Validate weaning event::

    >>> WeaningEvent.validate_event([weaning_event3.id], config.context)
    >>> weaning_event3.reload()
    >>> weaning_event3.state
    u'validated'

Check female's current cycle state is 'unmated' and its weaned value is 8 and
the weaning event has female and weaned group moves but not lost move::

    >>> female3.reload()
    >>> female3.current_cycle.state
    u'unmated'
    >>> female3.current_cycle.weaned
    8
    >>> female3.current_cycle.weaning_event.female_move.state
    u'done'
    >>> female3.current_cycle.weaning_event.weaned_move.quantity
    8.0
    >>> female3.current_cycle.weaning_event.lost_move

Create a group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup(
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=other_location_ids[-1],
    ...     initial_quantity=4)
    >>> animal_group.save()

Create a weaning event for third female (9 lives) with 7 as quantity, with
current female location as destination of female and group but with weaned
group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female4 = females[3]
    >>> weaning_event4 = WeaningEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female4,
    ...     quantity=7,
    ...     female_to_location=female4.location,
    ...     weaned_to_location=female4.location,
    ...     weaned_group=animal_group)
    >>> weaning_event4.save()

Validate weaning event::

    >>> WeaningEvent.validate_event([weaning_event4.id], config.context)
    >>> weaning_event4.reload()
    >>> weaning_event4.state
    u'validated'

Check female's current cycle state is 'unmated' and its weaned value is 7 and
the weaning event has lost move and **transformation event** but not female nor
weaned group moves::

    >>> female4.reload()
    >>> female4.current_cycle.state
    u'unmated'
    >>> female4.current_cycle.weaned
    7
    >>> female4.current_cycle.weaning_event.female_move
    >>> female4.current_cycle.weaning_event.weaned_move
    >>> female4.current_cycle.weaning_event.lost_move.quantity
    2.0
    >>> female4.current_cycle.weaning_event.transformation_event.state
    u'validated'


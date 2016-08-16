======================
Foster Events Scenario
======================

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

Get locations::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> production_location, = Location.find([('code', '=', 'PROD')])

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

Create farm user::

    >>> Group = Model.get('res.group')
    >>> farm_user = User()
    >>> farm_user.name = 'Sale'
    >>> farm_user.login = 'sale'
    >>> farm_user.main_company = company
    >>> farm_group, = Group.find([('name', '=', 'Farm / Females')])
    >>> farm_user.groups.append(farm_group)
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> farm_user.groups.append(stock_group)
    >>> farm_user.save()
    >>> config.user = farm_user.id

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'female'

Create two females to be inseminated, check their pregnancy state, farrow them
and do some foster events between them::

    >>> Animal = Model.get('farm.animal')
    >>> female1 = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> female1.save()
    >>> female1.location.code
    u'STO'
    >>> female1.farm.code
    u'WH'
    >>> female1.current_cycle
    >>> female1.state
    u'prospective'
    >>> female2 = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> female2.save()
    >>> female2.location.code
    u'STO'
    >>> female2.farm.code
    u'WH'
    >>> female2.current_cycle
    >>> female2.state
    u'prospective'

Create insemination events for the females without dose BoM nor Lot and
validate them::

    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> now = datetime.datetime.now()
    >>> inseminate_events = InseminationEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female2.id,
    ...         }], config.context)
    >>> InseminationEvent.validate_event(inseminate_events, config.context)
    >>> all(InseminationEvent(i).state == 'validated'
    ...     for i in inseminate_events)
    True

Check the females are mated::

    >>> female1.reload()
    >>> female1.state
    u'mated'
    >>> female1.current_cycle.state
    u'mated'
    >>> female2.reload()
    >>> female2.state
    u'mated'
    >>> female2.current_cycle.state
    u'mated'

Create pregnancy diagnosis events with positive result and validate them::

    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> now = datetime.datetime.now()
    >>> diagnosis_events = PregnancyDiagnosisEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         'result': 'positive',
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female2.id,
    ...         'result': 'positive',
    ...         }], config.context)
    >>> PregnancyDiagnosisEvent.validate_event(diagnosis_events, config.context)
    >>> all(PregnancyDiagnosisEvent(i).state == 'validated'
    ...     for i in diagnosis_events)
    True

Check females are pregnant::

    >>> female1.reload()
    >>> female1.current_cycle.state
    u'pregnant'
    >>> female1.current_cycle.pregnant
    1
    >>> female2.reload()
    >>> female2.current_cycle.state
    u'pregnant'
    >>> female2.current_cycle.pregnant
    1

Create a farrowing event for each female with 7 and 8 lives and validate them::

    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> now = datetime.datetime.now()
    >>> farrow_events = FarrowingEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         'live': 7,
    ...         'stillborn': 2,
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': pigs_specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female2.id,
    ...         'live': 8,
    ...         'stillborn': 1,
    ...         'mummified': 2,
    ...         }], config.context)
    >>> FarrowingEvent.validate_event(farrow_events, config.context)
    >>> all(FarrowingEvent(i).state == 'validated' for i in farrow_events)
    True

Check females are not pregnant, their current cycle are in 'lactating' state,
they are 'mated' and check females functional fields values::

    >>> female1.reload()
    >>> female1.current_cycle.pregnant
    0
    >>> female1.current_cycle.state
    u'lactating'
    >>> female1.state
    u'mated'
    >>> female1.current_cycle.live
    7
    >>> female1.current_cycle.dead
    2
    >>> female2.reload()
    >>> female2.current_cycle.pregnant
    0
    >>> female2.current_cycle.state
    u'lactating'
    >>> female2.state
    u'mated'
    >>> female2.current_cycle.live
    8
    >>> female2.current_cycle.dead
    3

Create a foster event for first female with -1 quantity (foster out) and
without pair female::

    >>> FosterEvent = Model.get('farm.foster.event')
    >>> now = datetime.datetime.now()
    >>> foster_event1 = FosterEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     quantity=-1)
    >>> foster_event1.save()

Validate foster event::

    >>> FosterEvent.validate_event([foster_event1.id], config.context)
    >>> foster_event1.reload()
    >>> foster_event1.state
    u'validated'

Check female's current cycle is still 'lactating', it has 1 foster event and
it's fostered value is -1::

    >>> female1.reload()
    >>> female1.current_cycle.pregnant
    False
    >>> female1.current_cycle.state
    u'lactating'
    >>> len(female1.current_cycle.foster_events)
    1
    >>> female1.current_cycle.fostered
    -1

Create a foster event for second female with +2 quantity (foster in) and
without pair female::

    >>> foster_event2 = FosterEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female2,
    ...     quantity=2)
    >>> foster_event2.save()

Validate foster event::

    >>> FosterEvent.validate_event([foster_event2.id], config.context)
    >>> foster_event2.reload()
    >>> foster_event2.state
    u'validated'

Check female's current cycle is still 'lactating', it has 1 foster event and
it's fostered value is 2::

    >>> female2.reload()
    >>> female2.current_cycle.pregnant
    False
    >>> female2.current_cycle.state
    u'lactating'
    >>> len(female2.current_cycle.foster_events)
    1
    >>> female2.current_cycle.fostered
    2


Create a foster event for first female with +4 quantity (foster in) and
with the second female as pair female::

    >>> now = datetime.datetime.now()
    >>> foster_event3= FosterEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     quantity=4,
    ...     pair_female=female2)
    >>> foster_event3.save()

Validate foster event::

    >>> FosterEvent.validate_event([foster_event3.id], config.context)
    >>> foster_event3.reload()
    >>> foster_event3.state
    u'validated'

Check foster event has Pair female foster event and it is validated:

    >>> foster_event3.pair_event != False
    True
    >>> foster_event3.pair_event.state
    u'validated'

Check the current cycle of the both females are still 'lactating', they has 2
foster events and their fostered value is +3 and -2 respectively::

    >>> female1.reload()
    >>> female2.reload()
    >>> any(f.current_cycle.pregnant for f in [female1, female2])
    False
    >>> all(f.current_cycle.state == 'lactating' for f in [female1, female2])
    True
    >>> len(female1.current_cycle.foster_events)
    2
    >>> female1.current_cycle.fostered
    3
    >>> len(female2.current_cycle.foster_events)
    2
    >>> female2.current_cycle.fostered
    -2

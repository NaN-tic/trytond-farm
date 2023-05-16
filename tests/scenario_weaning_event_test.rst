=======================
Weaning Events Scenario
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

Prepare locations::

    >>> location1 = Location()
    >>> location1.name = 'Other Location 1'
    >>> location1.type = 'storage'
    >>> location1.parent = warehouse.storage_location
    >>> location1.save()
    >>> location2 = Location()
    >>> location2.name = 'Other Location 2'
    >>> location2.type = 'storage'
    >>> location2.parent = warehouse.storage_location
    >>> location2.save()
    >>> location3 = Location()
    >>> location3.name = 'Other Location 3'
    >>> location3.type = 'storage'
    >>> location3.parent = warehouse.storage_location
    >>> location3.save()
    >>> location4 = Location()
    >>> location4.name = 'Other Location 4'
    >>> location4.type = 'storage'
    >>> location4.parent = warehouse.storage_location
    >>> location4.save()
    >>> location5 = Location()
    >>> location5.name = 'Other Location 5'
    >>> location5.type = 'storage'
    >>> location5.parent = warehouse.storage_location
    >>> location5.save()

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'female'

Create some females to be inseminated, check their pregnancy state, farrow them
to could test different weaning events::

    >>> Animal = Model.get('farm.animal')
    >>> female1 = Animal()
    >>> female1.type = 'female'
    >>> female1.specie = specie
    >>> female1.breed = breed
    >>> female1.initial_location = location1
    >>> female1.save()
    >>> female2 = Animal()
    >>> female2.type = 'female'
    >>> female2.specie = specie
    >>> female2.breed = breed
    >>> female2.initial_location = location2
    >>> female2.save()
    >>> female3 = Animal()
    >>> female3.type = 'female'
    >>> female3.specie = specie
    >>> female3.breed = breed
    >>> female3.initial_location = location3
    >>> female3.save()
    >>> female4 = Animal()
    >>> female4.type = 'female'
    >>> female4.specie = specie
    >>> female4.breed = breed
    >>> female4.initial_location = location4
    >>> female4.save()
    >>> females = [female1, female2, female3, female4]
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
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': f.id,
    ...         } for f in females], config.context)
    >>> InseminationEvent.validate_event(inseminate_events, config.context)
    >>> all(InseminationEvent(i).state == 'validated'
    ...     for i in inseminate_events)
    True
    >>> females = [Animal(x.id) for x in females]
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
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': f.id,
    ...         'result': 'positive',
    ...         } for f in females], config.context)
    >>> PregnancyDiagnosisEvent.validate_event(diagnosis_events, config.context)
    >>> all(PregnancyDiagnosisEvent(i).state == 'validated'
    ...     for i in diagnosis_events)
    True
    >>> females = [Animal(x.id) for x in females]
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
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': females[i].id,
    ...         'live': 6 + i,
    ...         } for i in range(0, len(females))], config.context)
    >>> FarrowingEvent.validate_event(farrow_events, config.context)
    >>> all(FarrowingEvent(i).state == 'validated' for i in farrow_events)
    True
    >>> all(FarrowingEvent(i).produced_group.lot.cost_price == Decimal('20.0')
    ...     for i in farrow_events)
    True
    >>> females = [Animal(x.id) for x in females]
    >>> not any(f.current_cycle.pregnant for f in females)
    True
    >>> all(f.current_cycle.state == 'lactating' for f in females)
    True
    >>> all(f.state == 'mated' for f in females)
    True
    >>> females[0].current_cycle.live
    6
    >>> females[0].current_cycle.removed
    >>> females[-1].current_cycle.live == (6 + len(females) - 1)
    True

Create a weaning event for first female (6 lives) with 6 as quantity, with
current female location as destination location for female and group and
without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female1 = females[0]
    >>> weaning_event1 = WeaningEvent()
    >>> weaning_event1.animal_type = 'female'
    >>> weaning_event1.specie = specie
    >>> weaning_event1.farm = warehouse
    >>> weaning_event1.timestamp = now
    >>> weaning_event1.animal = female1
    >>> weaning_event1.quantity = 6
    >>> weaning_event1.female_to_location = female1.location
    >>> weaning_event1.weaned_to_location = female1.location
    >>> weaning_event1.save()

Validate weaning event::

    >>> weaning_event1.click('validate_event')
    >>> weaning_event1.reload()
    >>> weaning_event1.state
    'validated'

Check female's current cycle state is 'unmated' and its weaned value is 6 and
the weaning event doesn't have female, weaned nor lost moves::

    >>> female1.reload()
    >>> female1.current_cycle.state
    'unmated'
    >>> female1.current_cycle.weaned
    6
    >>> female1.current_cycle.removed
    0
    >>> female1.current_cycle.weaning_event.female_move
    >>> female1.current_cycle.weaning_event.weaned_move
    >>> female1.current_cycle.weaning_event.lost_move
    >>> lot = weaning_event1.farrowing_group.lot
    >>> lot.cost_price == Decimal('20.0000')
    True

Create a weaning event for second female (7 lives) with 6 as quantity, with
current female location as destination of weaned group but not for destination
female location and without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female2 = females[1]
    >>> weaning_event2 = WeaningEvent()
    >>> weaning_event2.animal_type = 'female'
    >>> weaning_event2.specie = specie
    >>> weaning_event2.farm = warehouse
    >>> weaning_event2.timestamp = now
    >>> weaning_event2.animal = female2
    >>> weaning_event2.quantity = 6
    >>> weaning_event2.female_to_location = location5
    >>> weaning_event2.weaned_to_location = female2.location
    >>> weaning_event2.save()

Validate weaning event::

    >>> weaning_event2.click('validate_event')
    >>> weaning_event2.state
    'validated'

Check female's current cycle state is 'unmated' and its weaned value is 6 and
the weaning event has female and lost moves but not weaned group move::

    >>> female2.reload()
    >>> female2.current_cycle.state
    'unmated'
    >>> female2.current_cycle.weaned
    6
    >>> female2.current_cycle.removed
    1
    >>> female2.current_cycle.weaning_event.female_move.state
    'done'
    >>> female2.current_cycle.weaning_event.weaned_move
    >>> female2.current_cycle.weaning_event.lost_move.quantity
    1.0

Create a weaning event for third female (8 lives) with 8 as quantity, with
different destination location for female and group and without weaned group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female3 = females[2]
    >>> weaning_event3 = WeaningEvent()
    >>> weaning_event3.animal_type = 'female'
    >>> weaning_event3.specie = specie
    >>> weaning_event3.farm = warehouse
    >>> weaning_event3.timestamp = now
    >>> weaning_event3.animal = female3
    >>> weaning_event3.quantity = 8
    >>> weaning_event3.female_to_location = location5
    >>> weaning_event3.weaned_to_location = location5
    >>> weaning_event3.save()

Validate weaning event::

    >>> weaning_event3.click('validate_event')
    >>> weaning_event3.state
    'validated'

Check female's current cycle state is 'unmated' and its weaned value is 8 and
the weaning event has female and weaned group moves but not lost move::

    >>> female3.reload()
    >>> female3.current_cycle.state
    'unmated'
    >>> female3.current_cycle.weaned
    8
    >>> female3.current_cycle.weaning_event.female_move.state
    'done'
    >>> female3.current_cycle.weaning_event.weaned_move.quantity
    8.0
    >>> female3.current_cycle.weaning_event.lost_move

Create a group::

    >>> AnimalGroup = Model.get('farm.animal.group')
    >>> animal_group = AnimalGroup()
    >>> animal_group.specie = specie
    >>> animal_group.breed = breed
    >>> animal_group.initial_location = location5
    >>> animal_group.initial_quantity = 4
    >>> animal_group.save()

Create a weaning event for third female (9 lives) with 7 as quantity, with
current female location as destination of female and group but with weaned
group::

    >>> WeaningEvent = Model.get('farm.weaning.event')
    >>> now = datetime.datetime.now()
    >>> female4 = females[3]
    >>> weaning_event4 = WeaningEvent()
    >>> weaning_event4.animal_type = 'female'
    >>> weaning_event4.specie = specie
    >>> weaning_event4.farm = warehouse
    >>> weaning_event4.timestamp = now
    >>> weaning_event4.animal = female4
    >>> weaning_event4.quantity = 7
    >>> weaning_event4.female_to_location = female4.location
    >>> weaning_event4.weaned_to_location = female4.location
    >>> weaning_event4.weaned_group = animal_group
    >>> weaning_event4.save()

Validate weaning event::

    >>> weaning_event4.click('validate_event')
    >>> weaning_event4.state
    'validated'

Check female's current cycle state is 'unmated' and its weaned value is 7 and
the weaning event has lost move and **transformation event** but not female nor
weaned group moves::

    >>> female4.reload()
    >>> female4.current_cycle.state
    'unmated'
    >>> female4.current_cycle.weaned
    7
    >>> female4.current_cycle.weaning_event.female_move
    >>> female4.current_cycle.weaning_event.weaned_move
    >>> female4.current_cycle.weaning_event.lost_move.quantity
    2.0
    >>> female4.current_cycle.weaning_event.transformation_event.state
    'validated'
    >>> lot = weaning_event4.weaned_group.lot
    >>> lot.cost_price == Decimal('20.0000')
    True

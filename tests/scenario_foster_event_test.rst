======================
Foster Events Scenario
======================

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

Set user and context::

    >>> config.user = female_user.id
    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'female'

Create two females to be inseminated, check their pregnancy state, farrow them
and do some foster events between them::

    >>> Animal = Model.get('farm.animal')
    >>> female1 = Animal()
    >>> female1.type = 'female'
    >>> female1.specie = specie
    >>> female1.breed = breed
    >>> female1.initial_location = warehouse.storage_location
    >>> female1.save()
    >>> female1.location.code
    'STO'
    >>> female1.farm.code
    'WH'
    >>> female1.current_cycle
    >>> female1.state
    'prospective'
    >>> female2 = Animal()
    >>> female2.type = 'female'
    >>> female2.specie = specie
    >>> female2.breed = breed
    >>> female2.initial_location = warehouse.storage_location
    >>> female2.save()
    >>> female2.location.code
    'STO'
    >>> female2.farm.code
    'WH'
    >>> female2.current_cycle
    >>> female2.state
    'prospective'

Create insemination events for the females without dose BoM nor Lot and
validate them::

    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> now = datetime.datetime.now()
    >>> inseminate_events = InseminationEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
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
    'mated'
    >>> female1.current_cycle.state
    'mated'
    >>> female2.reload()
    >>> female2.state
    'mated'
    >>> female2.current_cycle.state
    'mated'

Create pregnancy diagnosis events with positive result and validate them::

    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> now = datetime.datetime.now()
    >>> diagnosis_events = PregnancyDiagnosisEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         'result': 'positive',
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
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
    'pregnant'
    >>> female1.current_cycle.pregnant
    1
    >>> female2.reload()
    >>> female2.current_cycle.state
    'pregnant'
    >>> female2.current_cycle.pregnant
    1

Create a farrowing event for each female with 7 and 8 lives and validate them::

    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> now = datetime.datetime.now()
    >>> farrow_events = FarrowingEvent.create([{
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
    ...         'farm': warehouse.id,
    ...         'timestamp': now,
    ...         'animal': female1.id,
    ...         'live': 7,
    ...         'stillborn': 2,
    ...         }, {
    ...         'animal_type': 'female',
    ...         'specie': specie.id,
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
    'lactating'
    >>> female1.state
    'mated'
    >>> female1.current_cycle.live
    7
    >>> female1.current_cycle.dead
    2
    >>> female2.reload()
    >>> female2.current_cycle.pregnant
    0
    >>> female2.current_cycle.state
    'lactating'
    >>> female2.state
    'mated'
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
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     quantity=-1)
    >>> foster_event1.save()

Validate foster event::

    >>> FosterEvent.validate_event([foster_event1.id], config.context)
    >>> foster_event1.reload()
    >>> foster_event1.state
    'validated'

Check female's current cycle is still 'lactating', it has 1 foster event and
it's fostered value is -1::

    >>> female1.reload()
    >>> female1.current_cycle.pregnant
    False
    >>> female1.current_cycle.state
    'lactating'
    >>> len(female1.current_cycle.foster_events)
    1
    >>> female1.current_cycle.fostered
    -1

Create a foster event for second female with +2 quantity (foster in) and
without pair female::

    >>> foster_event2 = FosterEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female2,
    ...     quantity=2)
    >>> foster_event2.save()

Validate foster event::

    >>> FosterEvent.validate_event([foster_event2.id], config.context)
    >>> foster_event2.reload()
    >>> foster_event2.state
    'validated'

Check female's current cycle is still 'lactating', it has 1 foster event and
it's fostered value is 2::

    >>> female2.reload()
    >>> female2.current_cycle.pregnant
    False
    >>> female2.current_cycle.state
    'lactating'
    >>> len(female2.current_cycle.foster_events)
    1
    >>> female2.current_cycle.fostered
    2


Create a foster event for first female with +4 quantity (foster in) and
with the second female as pair female::

    >>> now = datetime.datetime.now()
    >>> foster_event3= FosterEvent(
    ...     animal_type='female',
    ...     specie=specie,
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
    'validated'

Check foster event has Pair female foster event and it is validated:

    >>> foster_event3.pair_event != False
    True
    >>> foster_event3.pair_event.state
    'validated'

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

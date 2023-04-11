=========================
Farrowing Events Scenario
=========================

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

Prepare user and context::

    >>> config.user = female_user.id
    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'female'

Create female to be inseminated, check it's pregnancy state and farrow two
times (one without lives and second with)::

    >>> Animal = Model.get('farm.animal')
    >>> female = Animal()
    >>> female.type = 'female'
    >>> female.specie = specie
    >>> female.breed = breed
    >>> female.initial_location = warehouse.storage_location
    >>> female.save()
    >>> female.location.code
    'STO'
    >>> female.farm.code
    'WH'
    >>> female.current_cycle
    >>> female.state
    'prospective'

Create insemination event without dose BoM nor Lot and validate it::

    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> now = datetime.datetime.now()
    >>> inseminate_female = InseminationEvent()
    >>> inseminate_female.animal_type = 'female'
    >>> inseminate_female.specie = specie
    >>> inseminate_female.farm = warehouse
    >>> inseminate_female.timestamp = now
    >>> inseminate_female.animal = female
    >>> inseminate_female.save()
    >>> InseminationEvent.validate_event([inseminate_female.id],
    ...     config.context)
    >>> inseminate_female.reload()
    >>> inseminate_female.state
    'validated'

Check female is mated::

    >>> female.reload()
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'mated'

Create pregnancy diagnosis event with positive result and validate it::

    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> now = datetime.datetime.now()
    >>> diagnose_female = PregnancyDiagnosisEvent()
    >>> diagnose_female.animal_type = 'female'
    >>> diagnose_female.specie = specie
    >>> diagnose_female.farm = warehouse
    >>> diagnose_female.timestamp = now
    >>> diagnose_female.animal = female
    >>> diagnose_female.result = 'positive'
    >>> diagnose_female.save()
    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female.id],
    ...     config.context)
    >>> diagnose_female.reload()
    >>> diagnose_female.state
    'validated'

Check female is pregnant::

    >>> female.reload()
    >>> female.current_cycle.state
    'pregnant'
    >>> female.current_cycle.pregnant
    1

Create farrowing event without lives::

    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> FarrowingProblem = Model.get('farm.farrowing.problem')
    >>> farrowing_problem = FarrowingProblem.find([], limit=1)[0]
    >>> now = datetime.datetime.now()
    >>> farrow_event = FarrowingEvent()
    >>> farrow_event.animal_type = 'female'
    >>> farrow_event.specie = specie
    >>> farrow_event.farm = warehouse
    >>> farrow_event.timestamp = now
    >>> farrow_event.animal = female
    >>> farrow_event.live = 0
    >>> farrow_event.stillborn = 4
    >>> farrow_event.mummified = 2
    >>> farrow_event.problem = farrowing_problem
    >>> farrow_event.save()

Validate farrowing event::

    >>> FarrowingEvent.validate_event([farrow_event.id], config.context)
    >>> farrow_event.reload()
    >>> farrow_event.state
    'validated'

Check female is not pregnant, its current cycle is in 'unmated' state, it is in
'prospective' state and check female functional fields values::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    False
    >>> female.current_cycle.state
    'unmated'
    >>> female.state
    'prospective'
    >>> female.last_produced_group
    >>> female.current_cycle.live
    0
    >>> female.current_cycle.dead
    6

Create second insemination event without dose BoM nor Lot and validate it::

    >>> now = datetime.datetime.now()
    >>> inseminate_female2 = InseminationEvent()
    >>> inseminate_female2.animal_type = 'female'
    >>> inseminate_female2.specie = specie
    >>> inseminate_female2.farm = warehouse
    >>> inseminate_female2.timestamp = now
    >>> inseminate_female2.animal = female
    >>> inseminate_female2.save()
    >>> InseminationEvent.validate_event([inseminate_female2.id],
    ...     config.context)
    >>> inseminate_female2.reload()
    >>> inseminate_female2.state
    'validated'

Check female has two cycles with diferent sequences, it and its current
cycle is mated and the first cycle (old) is unmated::

    >>> female.reload()
    >>> len(female.cycles)
    2
    >>> female.cycles[0].sequence != female.cycles[1].sequence
    1
    >>> female.current_cycle.state
    'mated'
    >>> female.state
    'mated'
    >>> female.cycles[0].state
    'unmated'

Create second pregnancy diagnosis event with positive result and validate it::

    >>> now = datetime.datetime.now()
    >>> diagnose_female2 = PregnancyDiagnosisEvent()
    >>> diagnose_female2.animal_type = 'female'
    >>> diagnose_female2.specie = specie
    >>> diagnose_female2.farm = warehouse
    >>> diagnose_female2.timestamp = now
    >>> diagnose_female2.animal = female
    >>> diagnose_female2.result = 'positive'
    >>> diagnose_female2.save()
    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female2.id],
    ...     config.context)
    >>> diagnose_female2.reload()
    >>> diagnose_female2.state
    'validated'

Check female is pregnant::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    1
    >>> female.current_cycle.state
    'pregnant'

Create second farrowing event with lives::

    >>> now = datetime.datetime.now()
    >>> farrow_event2 = FarrowingEvent()
    >>> farrow_event2.animal_type = 'female'
    >>> farrow_event2.specie = specie
    >>> farrow_event2.farm = warehouse
    >>> farrow_event2.timestamp = now
    >>> farrow_event2.animal = female
    >>> farrow_event2.live = 7
    >>> farrow_event2.stillborn = 2
    >>> farrow_event2.save()

Validate farrowing event::

    >>> FarrowingEvent.validate_event([farrow_event2.id], config.context)
    >>> farrow_event2.reload()
    >>> farrow_event2.state
    'validated'

Check female is not pregnant, its current cycle are in 'lactating' state,
it is 'mated' and check female functional fields values::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    0
    >>> female.current_cycle.state
    'lactating'
    >>> female.state
    'mated'
    >>> female.current_cycle.live
    7
    >>> female.current_cycle.dead
    2

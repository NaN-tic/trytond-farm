=====================
Abort Events Scenario
=====================

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

Set user and context::

    >>> config.user = female_user.id
    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'female'

Create female to be inseminated, check it's pregnancy state and abort two
times::

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
    >>> diagnose_female = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='positive')
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

Create abort event::

    >>> AbortEvent = Model.get('farm.abort.event')
    >>> now = datetime.datetime.now()
    >>> abort_female = AbortEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female)
    >>> abort_female.save()

Validate abort event::

    >>> AbortEvent.validate_event([abort_female.id], config.context)
    >>> abort_female.reload()
    >>> abort_female.state
    'validated'

Check female is not pregnant, it is in 'prospective' state and its current
cycle is 'unmated'::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    0
    >>> female.current_cycle.state
    'unmated'
    >>> female.state
    'prospective'

Create second insemination event without dose BoM nor Lot and validate it::

    >>> now = datetime.datetime.now()
    >>> inseminate_female2 = InseminationEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female)
    >>> inseminate_female2.save()
    >>> InseminationEvent.validate_event([inseminate_female2.id],
    ...     config.context)
    >>> inseminate_female2.reload()
    >>> inseminate_female2.state
    'validated'

Check female has two cycles but both with the same sequence, it and its current
cycle is mated and the first cycle (old) is unmated::

    >>> female.reload()
    >>> len(female.cycles)
    2
    >>> female.cycles[0].sequence == female.cycles[1].sequence
    1
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'mated'
    >>> female.cycles[0].state
    'unmated'

Create second pregnancy diagnosis event with positive result and validate it::

    >>> now = datetime.datetime.now()
    >>> diagnose_female2 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='positive')
    >>> diagnose_female2.save()
    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female2.id],
    ...     config.context)
    >>> diagnose_female2.reload()
    >>> diagnose_female2.state
    'validated'

Check female is pregnant::

    >>> female.reload()
    >>> female.current_cycle.state
    'pregnant'
    >>> female.current_cycle.pregnant
    1

Create second abort event::

    >>> now = datetime.datetime.now()
    >>> abort_female2 = AbortEvent(
    ...     animal_type='female',
    ...     specie=specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female)
    >>> abort_female2.save()

Validate abort event::

    >>> AbortEvent.validate_event([abort_female2.id], config.context)
    >>> abort_female2.reload()
    >>> abort_female2.state
    'validated'

Check female is not pregnant and it and its current cycle is 'unmated'::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    0
    >>> female.current_cycle.state
    'unmated'
    >>> female.state
    'unmated'

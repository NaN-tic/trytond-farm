===================================
Pregnancy Diagnosis Events Scenario
===================================

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

Create female to be inseminated and check it's pregnancy state and restart the
cycle::

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
    >>> inseminate_female.dose_lot
    >>> InseminationEvent.validate_event([inseminate_female.id],
    ...     config.context)
    >>> inseminate_female.reload()
    >>> inseminate_female.state
    'validated'

Check female is mated::

    >>> female.reload()
    >>> female.current_cycle.state
    'mated'
    >>> female.state
    'mated'

Create pregnancy diagnosis event with negative result::

    >>> PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
    >>> now = datetime.datetime.now()
    >>> diagnose_female1 = PregnancyDiagnosisEvent()
    >>> diagnose_female1.animal_type='female'
    >>> diagnose_female1.specie=specie
    >>> diagnose_female1.farm=warehouse
    >>> diagnose_female1.timestamp=now
    >>> diagnose_female1.animal=female
    >>> diagnose_female1.result='negative'
    >>> diagnose_female1.save()

Validate pregnancy diagnosis event::

    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female1.id],
    ...     config.context)
    >>> diagnose_female1.reload()
    >>> diagnose_female1.state
    'validated'

Check female is not pregnant, it is mated and has one pregnancy diagnosis
event::

    >>> female.reload()
    >>> female.current_cycle.pregnant
    0
    >>> female.current_cycle.state
    'mated'
    >>> female.state
    'mated'
    >>> len(female.current_cycle.diagnosis_events)
    1

Create pregnancy diagnosis event with positive result::

    >>> now = datetime.datetime.now()
    >>> diagnose_female2 = PregnancyDiagnosisEvent()
    >>> diagnose_female2.animal_type='female'
    >>> diagnose_female2.specie=specie
    >>> diagnose_female2.farm=warehouse
    >>> diagnose_female2.timestamp=now
    >>> diagnose_female2.animal=female
    >>> diagnose_female2.result='positive'
    >>> diagnose_female2.save()

Validate pregnancy diagnosis event::

    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female2.id],
    ...     config.context)
    >>> diagnose_female2.reload()
    >>> diagnose_female2.state
    'validated'

Check female is pregnant, it is mated and has two pregnancy diagnosis events::

    >>> female.reload()
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'pregnant'
    >>> female.current_cycle.pregnant
    1
    >>> len(female.current_cycle.diagnosis_events)
    2

Create pregnancy diagnosis event with nonconclusive result::

    >>> now = datetime.datetime.now()
    >>> diagnose_female3 = PregnancyDiagnosisEvent()
    >>> diagnose_female3.animal_type = 'female'
    >>> diagnose_female3.specie = specie
    >>> diagnose_female3.farm = warehouse
    >>> diagnose_female3.timestamp = now
    >>> diagnose_female3.animal = female
    >>> diagnose_female3.result = 'nonconclusive'
    >>> diagnose_female3.save()

Validate pregnancy diagnosis event::

    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female3.id],
    ...     config.context)
    >>> diagnose_female3.reload()
    >>> diagnose_female3.state
    'validated'

Check female is not pregnant, it is mated and has three pregnancy diagnosis
events::

    >>> female.reload()
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'mated'
    >>> female.current_cycle.pregnant
    0
    >>> len(female.current_cycle.diagnosis_events)
    3

Create pregnancy diagnosis event with positive result::

    >>> now = datetime.datetime.now()
    >>> diagnose_female4 = PregnancyDiagnosisEvent()
    >>> diagnose_female4.animal_type = 'female'
    >>> diagnose_female4.specie = specie
    >>> diagnose_female4.farm = warehouse
    >>> diagnose_female4.timestamp = now
    >>> diagnose_female4.animal = female
    >>> diagnose_female4.result = 'positive'
    >>> diagnose_female4.save()

Validate pregnancy diagnosis event::

    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female4.id],
    ...     config.context)
    >>> diagnose_female4.reload()
    >>> diagnose_female4.state
    'validated'

Check female is pregnant, it is mated and has four pregnancy diagnosis events::

    >>> female.reload()
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'pregnant'
    >>> female.current_cycle.pregnant
    1
    >>> len(female.current_cycle.diagnosis_events)
    4

Create pregnancy diagnosis event with not-pregnant result::

    >>> now = datetime.datetime.now()
    >>> diagnose_female5 = PregnancyDiagnosisEvent()
    >>> diagnose_female5.animal_type = 'female'
    >>> diagnose_female5.specie = specie
    >>> diagnose_female5.farm = warehouse
    >>> diagnose_female5.timestamp = now
    >>> diagnose_female5.animal = female
    >>> diagnose_female5.result = 'not-pregnant'
    >>> diagnose_female5.save()

Validate pregnancy diagnosis event::

    >>> PregnancyDiagnosisEvent.validate_event([diagnose_female5.id],
    ...     config.context)
    >>> diagnose_female5.reload()
    >>> diagnose_female5.state
    'validated'

Check female is not pregnant, it is mated and has five pregnancy diagnosis
events::

    >>> female.reload()
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'mated'
    >>> female.current_cycle.pregnant
    0
    >>> len(female.current_cycle.diagnosis_events)
    5

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

Check female has two cycles but both with the same sequence, it and the both of
its cycles are mated::

    >>> female.reload()
    >>> len(female.cycles)
    2
    >>> female.cycles[0].sequence == female.cycles[1].sequence
    1
    >>> female.state
    'mated'
    >>> female.current_cycle.state
    'mated'
    >>> all([c.state == 'mated' for c in female.cycles])
    1

===================================
Pregnancy Diagnosis Events Scenario
===================================

=============
General Setup
=============

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
    >>> now = datetime.datetime.now()
    >>> today = datetime.date.today()

Install module::

    >>> config = activate_modules('farm')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

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
    ...     male_enabled=False,
    ...     female_enabled=True,
    ...     female_product=female_product,
    ...     semen_product=semen_product,
    ...     individual_enabled=False,
    ...     group_enabled=False,
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
    ...     has_group=False)
    >>> pigs_farm_line.save()

Create farm user::

    >>> Group = Model.get('res.group')
    >>> farm_user = User()
    >>> farm_user.name = 'Farm'
    >>> farm_user.login = 'farm'
    >>> farm_user.main_company = company
    >>> farm_group, = Group.find([('name', '=', 'Farm / Females')])
    >>> farm_user.groups.append(farm_group)
    >>> farm_user.save()
    >>> config.user = farm_user.id

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'female'

Create female to be inseminated and check it's pregnancy state and restart the
cycle::

    >>> Animal = Model.get('farm.animal')
    >>> female = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
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
    >>> inseminate_female = InseminationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female)
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
    >>> diagnose_female1 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='negative')
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
    >>> diagnose_female2 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='positive')
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
    >>> diagnose_female3 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='nonconclusive')
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
    >>> diagnose_female4 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='positive')
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
    >>> diagnose_female5 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     result='not-pregnant')
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
    >>> inseminate_female2 = InseminationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female)
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

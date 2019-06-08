=========================
Farrowing Events Scenario
=========================

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
    >>> group_template = ProductTemplate(
    ...     name='Group of Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('30'),
    ...     farrowing_price=Decimal('10'),
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

Create female to be inseminated, check it's pregnancy state and farrow two
times (one without lives and second with)::

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
    ...     specie=pigs_specie,
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

Create farrowing event without lives::

    >>> FarrowingEvent = Model.get('farm.farrowing.event')
    >>> FarrowingProblem = Model.get('farm.farrowing.problem')
    >>> farrowing_problem = FarrowingProblem.find([], limit=1)[0]
    >>> now = datetime.datetime.now()
    >>> farrow_event = FarrowingEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     live=0,
    ...     stillborn=4,
    ...     mummified=2,
    ...     problem=farrowing_problem)
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
    >>> diagnose_female2 = PregnancyDiagnosisEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
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
    >>> female.current_cycle.pregnant
    1
    >>> female.current_cycle.state
    'pregnant'

Create second farrowing event with lives::

    >>> now = datetime.datetime.now()
    >>> farrow_event2 = FarrowingEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female,
    ...     live=7,
    ...     stillborn=2)
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

Female childs must have the farrowing cost::

    >>> group = farrow_event2.produced_group
    >>> len(group.lot.cost_lines)
    1
    >>> group.lot.cost_price == Decimal('10.0')
    True

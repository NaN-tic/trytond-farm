============================
Insemination Events Scenario
============================

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

Create dose Product, BoM and Lot::

    >>> blister_template = ProductTemplate(
    ...     name='100 cm3 blister',
    ...     default_uom=unit,
    ...     type='goods',
    ...     consumable=True,
    ...     list_price=Decimal('1'),
    ...     cost_price=Decimal('1'))
    >>> blister_template.save()
    >>> blister_product = Product(template=blister_template)
    >>> blister_product.save()
    >>> dose_template = ProductTemplate(
    ...     name='100 cm3 semen dose',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('10'),
    ...     cost_price=Decimal('8'))
    >>> dose_template.save()
    >>> dose_product = Product(template=dose_template)
    >>> dose_product.save()
    >>> Bom = Model.get('production.bom')
    >>> BomInput = Model.get('production.bom.input')
    >>> BomOutput = Model.get('production.bom.output')
    >>> dose_bom = Bom(
    ...     name='100 cm3 semen dose',
    ...     semen_dose=True,
    ...     specie=pigs_specie.id,
    ...     inputs=[
    ...         BomInput(
    ...             product=blister_product,
    ...             uom=unit,
    ...             quantity=1),
    ...         BomInput(
    ...             product=semen_product,
    ...             uom=cm3,
    ...             quantity=100.00),
    ...         ],
    ...     outputs=[
    ...         BomOutput(
    ...             product=dose_product,
    ...             uom=unit,
    ...             quantity=1.00),
    ...         ],
    ...     )
    >>> dose_bom.save()
    >>> dose_bom.reload()
    >>> ProductBom = Model.get('product.product-production.bom')
    >>> dose_product.boms.append(ProductBom(
    ...         bom=dose_bom,
    ...         sequence=1))
    >>> dose_product.save()
    >>> dose_product.reload()
    >>> Lot = Model.get('stock.lot')
    >>> dose_lot = Lot(
    ...     number='S001',
    ...     product=dose_product)
    >>> dose_lot.save()

Put two units of dose and one of semen in farm storage location::

    >>> Move = Model.get('stock.move')
    >>> now = datetime.datetime.now()
    >>> provisioning_moves_vals = [{
    ...         'product': dose_product.id,
    ...         'uom': unit.id,
    ...         'quantity': 2.0,
    ...         'from_location': production_location.id,
    ...         'to_location': warehouse.storage_location.id,
    ...         'planned_date': now.date(),
    ...         'effective_date': now.date(),
    ...         'company': config.context.get('company'),
    ...         'lot': dose_lot.id,
    ...         'unit_price': dose_product.template.list_price,
    ...     }, {
    ...         'product': semen_product.id,
    ...         'uom': cm3.id,
    ...         'quantity': 1.0,
    ...         'from_location': production_location.id,
    ...         'to_location': warehouse.storage_location.id,
    ...         'planned_date': now.date(),
    ...         'effective_date': now.date(),
    ...         'company': config.context.get('company'),
    ...         'unit_price': semen_product.template.list_price,
    ...     }]
    >>> provisioning_moves = Move.create(provisioning_moves_vals,
    ...     config.context)
    >>> Move.assign(provisioning_moves, config.context)
    >>> Move.do(provisioning_moves, config.context)

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

Create first female to be inseminated::

    >>> Animal = Model.get('farm.animal')
    >>> female1 = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> female1.save()
    >>> female1.location.code
    'STO'
    >>> female1.farm.code
    'WH'
    >>> female1.current_cycle
    >>> female1.state
    'prospective'

Create insemination event with dose BoM and Lot::

    >>> InseminationEvent = Model.get('farm.insemination.event')
    >>> now = datetime.datetime.now()
    >>> inseminate_female1 = InseminationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     dose_bom=dose_bom,
    ...     dose_lot=dose_lot)
    >>> inseminate_female1.save()

Validate insemination event::

    >>> InseminationEvent.validate_event([inseminate_female1.id],
    ...     config.context)
    >>> inseminate_female1.reload()
    >>> inseminate_female1.state
    'validated'

Check female is mated::

    >>> female1.reload()
    >>> female1.state
    'mated'
    >>> female1.current_cycle.state
    'mated'

Create insemination event with dose BoM but not Lot::

    >>> now = datetime.datetime.now()
    >>> inseminate_female12 = InseminationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female1,
    ...     dose_bom=dose_bom)
    >>> inseminate_female12.save()

Validate insemination event::

    >>> InseminationEvent.validate_event([inseminate_female12.id],
    ...     config.context)
    >>> inseminate_female12.reload()
    >>> inseminate_female12.state
    'validated'

Check female is mated and has two insemination events::

    >>> female1.reload()
    >>> female1.state
    'mated'
    >>> female1.current_cycle.state
    'mated'
    >>> len(female1.current_cycle.insemination_events)
    2

Create second female to be inseminated::

    >>> female2 = Animal(
    ...     type='female',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> female2.save()
    >>> female2.location.code
    'STO'
    >>> female2.farm.code
    'WH'
    >>> female2.current_cycle
    >>> female2.state
    'prospective'

Create insemination event without dose BoM nor Lot::

    >>> now = datetime.datetime.now()
    >>> inseminate_female2 = InseminationEvent(
    ...     animal_type='female',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=female2)
    >>> inseminate_female2.save()

Validate insemination event::

    >>> InseminationEvent.validate_event([inseminate_female2.id],
    ...     config.context)
    >>> inseminate_female2.reload()
    >>> inseminate_female2.state
    'validated'

Check female is mated::

    >>> female2.reload()
    >>> female2.state
    'mated'
    >>> female2.current_cycle.state
    'mated'

================================
Semen Extraction Events Scenario
================================

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
    >>> male_template = ProductTemplate(
    ...     name='Male Pig',
    ...     default_uom=unit,
    ...     type='goods',
    ...     list_price=Decimal('40'),
    ...     cost_price=Decimal('25'))
    >>> male_template.save()
    >>> male_product = Product(template=male_template)
    >>> male_product.save()
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
    >>> male_sequence = Sequence(
    ...     name='Male Pig Warehouse 1',
    ...     code='farm.animal',
    ...     padding=4)
    >>> male_sequence.save()
    >>> semen_lot_sequence = Sequence(
    ...     name='Semen Extracted Lot Pig Warehouse 1',
    ...     code='stock.lot',
    ...     padding=4)
    >>> semen_lot_sequence.save()
    >>> semen_dose_lot_sequence = Sequence(
    ...     name='Semen Dose Lot Pig Warehouse 1',
    ...     code='stock.lot',
    ...     padding=4)
    >>> semen_dose_lot_sequence.save()

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
    >>> location1 = Location(
    ...     name='Location 1',
    ...     code='L1',
    ...     type='storage',
    ...     parent=warehouse.storage_location)
    >>> location1.save()
    >>> lab1 = Location(
    ...     name='Laboratory 1',
    ...     code='Lab1',
    ...     type='storage',
    ...     parent=warehouse.storage_location)
    >>> lab1.save()

Create Quality Configuration and Semen Quality Test Template::

    >>> quality_sequence, = Sequence.find([('code','=','quality.test')])
    >>> Model_ = Model.get('ir.model')
    >>> product_model, = Model_.find([('model','=','product.product')])
    >>> lot_model, = Model_.find([('model','=','stock.lot')])
    >>> QualityConfiguration = Model.get('quality.configuration')
    >>> QualityConfigLine = Model.get('quality.configuration.line')
    >>> QualityConfiguration(
    ...     allowed_documents=[
    ...         QualityConfigLine(
    ...             quality_sequence=quality_sequence,
    ...             document=product_model),
    ...         QualityConfigLine(
    ...             quality_sequence=quality_sequence,
    ...             document=lot_model),
    ...         ]).save()
    >>> QualityTemplate = Model.get('quality.template')
    >>> quality_template = QualityTemplate(
    ...     name='Semen Quality Template',
    ...     document=semen_product,
    ...     formula='1.5',
    ...     unit=cm3)
    >>> quality_template.save()

Create specie::

    >>> Specie = Model.get('farm.specie')
    >>> SpecieBreed = Model.get('farm.specie.breed')
    >>> SpecieFarmLine = Model.get('farm.specie.farm_line')
    >>> pigs_specie = Specie(
    ...     name='Pigs',
    ...     male_enabled=True,
    ...     male_product=male_product,
    ...     female_enabled=False,
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
    ...     has_male=True,
    ...     male_sequence=male_sequence,
    ...     semen_lot_sequence=semen_lot_sequence,
    ...     dose_lot_sequence=semen_dose_lot_sequence,
    ...     has_female=False,
    ...     has_individual=False,
    ...     has_group=False)
    >>> pigs_farm_line.save()

Create dose Product and BoM::

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
    ...             quantity=1),
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

Set animal_type and specie in context to work as in the menus::

    >>> config._context['specie'] = pigs_specie.id
    >>> config._context['animal_type'] = 'male'

Create a male::

    >>> Animal = Model.get('farm.animal')
    >>> male1 = Animal(
    ...     type='male',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=location1)
    >>> male1.save()
    >>> male1.location.code
    u'L1'
    >>> male1.farm.code
    u'WH'

Create semen extraction event::

    >>> SemenExtractionEvent = Model.get('farm.semen_extraction.event')
    >>> now = datetime.datetime.now()
    >>> extraction1 = SemenExtractionEvent(
    ...     animal_type='male',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     timestamp=now,
    ...     animal=male1,
    ...     untreated_semen_uom=cm3,
    ...     untreated_semen_qty=Decimal('410.0'),
    ...     dose_location=lab1,
    ...     dose_bom=dose_bom)
    >>> extraction1.save()

Check test is created and functional fields::

    >>> extraction1.test is not None
    True
    >>> extraction1.test.unit.name
    u'Cubic centimeter'
    >>> extraction1.formula_result
    1.5
    >>> extraction1.semen_calculated_qty
    615.0
    >>> extraction1.solvent_calculated_qty
    205.0

Set real semen produced quantity and check calculated doses::

    >>> extraction1.semen_qty = Decimal('610.0')
    >>> extraction1.save()
    >>> extraction1.reload()
    >>> extraction1.dose_calculated_units
    6.1

Add produced doses::

    >>> Dose = Model.get('farm.semen_extraction.dose')
    >>> dose1 = Dose(
    ...     event=extraction1,
    ...     sequence=1,
    ...     bom=dose_bom,
    ...     quantity=6)
    >>> dose1.save()

Check dose and deliveries functional fields::

    >>> extraction1.reload()
    >>> extraction1.doses_semen_qty
    600.0
    >>> extraction1.semen_remaining_qty
    10.0

Validate semen extraction event::

    >>> SemenExtractionEvent.validate_event([extraction1.id], config.context)
    >>> extraction1.reload()
    >>> extraction1.state
    u'validated'
    >>> extraction1.semen_lot is not None
    True
    >>> extraction1.doses[0].production.state
    u'done'
    >>> extraction1.doses[0].lot is not None
    True
    >>> extraction1.animal.reload()
    >>> extraction1.animal.last_extraction == now.date()
    True

Create an internal shipment to serve produced doses::

    >>> Move = Model.get('stock.move')
    >>> Shipment = Model.get('stock.shipment.internal')
    >>> shipment = Shipment()
    >>> shipment.from_location=lab1
    >>> shipment.to_location=location1
    >>> move = shipment.moves.new()
    >>> move.from_location = lab1
    >>> move.to_location = location1
    >>> move.product = dose_product
    >>> move.lot = extraction1.doses[0].lot
    >>> move.quantity = 5
    >>> move.unit_price=blister_product.template.cost_price
    >>> shipment.save()


Process shipment to check doe lots are in expected location::

    >>> shipment.click('wait')
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('done')
    >>> shipment.reload()
    >>> shipment.state
    u'done'


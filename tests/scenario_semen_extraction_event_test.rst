================================
Semen Extraction Events Scenario
================================

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

Prepare locations:

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

    >>> ProductUom = Model.get('product.uom')
    >>> cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> Sequence = Model.get('ir.sequence')
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

Create dose Product and BoM::

    >>> ProductTemplate = Model.get('product.template')
    >>> blister_template = ProductTemplate()
    >>> blister_template.name = '100 cm3 blister'
    >>> blister_template.default_uom = unit
    >>> blister_template.type = 'goods'
    >>> blister_template.consumable = True
    >>> blister_template.list_price = Decimal('1')
    >>> blister_template.save()
    >>> blister_product, = blister_template.products
    >>> blister_product.cost_price = Decimal('1')
    >>> blister_product.save()
    >>> dose_template = ProductTemplate()
    >>> dose_template.name = '100 cm3 semen dose'
    >>> dose_template.default_uom = unit
    >>> dose_template.type = 'goods'
    >>> dose_template.list_price = Decimal('10')
    >>> dose_template.producible = True
    >>> dose_template.save()
    >>> dose_product, = dose_template.products
    >>> dose_product.cost_price = Decimal('8')
    >>> dose_product.save()
    >>> Bom = Model.get('production.bom')
    >>> BomInput = Model.get('production.bom.input')
    >>> BomOutput = Model.get('production.bom.output')
    >>> dose_bom = Bom(
    ...     name='100 cm3 semen dose',
    ...     semen_dose=True,
    ...     specie=specie.id,
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

    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'male'

Create a male::

    >>> Animal = Model.get('farm.animal')
    >>> male1 = Animal(
    ...     type='male',
    ...     specie=specie,
    ...     breed=breed,
    ...     initial_location=location1)
    >>> male1.save()
    >>> male1.location.code
    'L1'
    >>> male1.farm.code
    'WH'

Create semen extraction event::

    >>> SemenExtractionEvent = Model.get('farm.semen_extraction.event')
    >>> now = datetime.datetime.now()
    >>> extraction1 = SemenExtractionEvent()
    >>> extraction1.animal_type = 'male'
    >>> extraction1.specie = specie
    >>> extraction1.farm = warehouse
    >>> extraction1.timestamp = now
    >>> extraction1.animal = male1
    >>> extraction1.untreated_semen_uom = cm3
    >>> extraction1.untreated_semen_qty = Decimal('410.0')
    >>> extraction1.dose_location = lab1
    >>> extraction1.dose_bom = dose_bom
    >>> extraction1.save()

Check test is created and functional fields::

    >>> extraction1.test is not None
    True
    >>> extraction1.test.unit.name
    'Cubic centimeter'
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
    >>> dose1 = Dose()
    >>> dose1.event = extraction1
    >>> dose1.sequence = 1
    >>> dose1.bom = dose_bom
    >>> dose1.quantity = 6
    >>> dose1.save()

Check dose functional fields::

    >>> extraction1.reload()
    >>> extraction1.doses_semen_qty
    600.0
    >>> extraction1.semen_remaining_qty
    10.0

Validate semen extraction event::

    >>> extraction1.click('validate_event')
    >>> extraction1.reload()
    >>> extraction1.state
    'validated'
    >>> extraction1.semen_lot is not None
    True
    >>> extraction1.doses[0].production.state
    'done'
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
    'done'


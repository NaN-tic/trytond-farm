=======================
Removal Events Scenario
=======================

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

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> liter, = ProductUom.find([('name', '=', 'Liter')])
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
    ...     default_uom=liter,
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

Create specie::

    >>> Location = Model.get('stock.location')
    >>> lost_found_location, = Location.find([('type', '=', 'lost_found')])
    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> Specie = Model.get('farm.specie')
    >>> SpecieBreed = Model.get('farm.specie.breed')
    >>> SpecieFarmLine = Model.get('farm.specie.farm_line')
    >>> pigs_specie = Specie(
    ...     name='Pigs',
    ...     male_enabled=True,
    ...     male_product=male_product,
    ...     semen_product=semen_product,
    ...     female_enabled=False,
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
    ...     dose_lot_sequence=semen_dose_lot_sequence)
    >>> pigs_farm_line.save()

Create stock user::

    >>> Group = Model.get('res.group')
    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create farm users::

    >>> male_user = User()
    >>> male_user.name = 'Males'
    >>> male_user.login = 'males'
    >>> male_user.main_company = company
    >>> male_group, = Group.find([('name', '=', 'Farm / Males')])
    >>> male_user.groups.append(male_group)
    >>> male_user.save()

Create male::

    >>> config.user = male_user.id
    >>> Animal = Model.get('farm.animal')
    >>> male = Animal(
    ...     type='male',
    ...     specie=pigs_specie,
    ...     breed=pigs_breed,
    ...     initial_location=warehouse.storage_location)
    >>> male.save()
    >>> male.location.code
    u'STO'
    >>> male.farm.code
    u'WH'

Create removal event::

    >>> RemovalType = Model.get('farm.removal.type')
    >>> removal_type = RemovalType.find([], limit=1)[0]
    >>> RemovalReason = Model.get('farm.removal.reason')
    >>> removal_reason = RemovalReason.find([], limit=1)[0]
    >>> RemovalEvent = Model.get('farm.removal.event')
    >>> remove_male = RemovalEvent(
    ...     animal_type='male',
    ...     specie=pigs_specie,
    ...     farm=warehouse,
    ...     animal=male,
    ...     timestamp=now,
    ...     from_location=male.location,
    ...     removal_type=removal_type,
    ...     reason=removal_reason)
    >>> remove_male.save()

Animal doesn't chage its values::

    >>> male.reload()
    >>> male.removal_date
    >>> male.removal_reason
    >>> bool(male.active)
    True

Validate removal event::

    >>> remove_male.click('validate_event')
    >>> remove_male.reload()
    >>> remove_male.state
    u'validated'
    >>> male.reload()
    >>> male.removal_date == today
    True
    >>> male.removal_reason == removal_reason
    True
    >>> male.location == male.specie.removed_location
    True
    >>> bool(male.active)
    False

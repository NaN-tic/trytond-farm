=======================
Removal Events Scenario
=======================

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

    >>> config.user = male_user.id
    >>> config._context['specie'] = specie.id
    >>> config._context['animal_type'] = 'female'

Create male::

    >>> Animal = Model.get('farm.animal')
    >>> male = Animal()
    >>> male.type = 'male'
    >>> male.specie = specie
    >>> male.breed = breed
    >>> male.initial_location = warehouse.storage_location
    >>> male.save()
    >>> male.location.code
    'STO'
    >>> male.farm.code
    'WH'

Create removal event::

    >>> RemovalType = Model.get('farm.removal.type')
    >>> removal_type = RemovalType.find([], limit=1)[0]
    >>> RemovalReason = Model.get('farm.removal.reason')
    >>> removal_reason = RemovalReason.find([], limit=1)[0]
    >>> RemovalEvent = Model.get('farm.removal.event')
    >>> remove_male = RemovalEvent()
    >>> remove_male.animal_type = 'male'
    >>> remove_male.specie = specie
    >>> remove_male.farm = warehouse
    >>> remove_male.animal = male
    >>> remove_male.timestamp = now
    >>> remove_male.from_location = male.location
    >>> remove_male.removal_type = removal_type
    >>> remove_male.reason = removal_reason
    >>> remove_male.save()

Animal doesn't change its values::

    >>> male.reload()
    >>> male.removal_date
    >>> male.removal_reason
    >>> bool(male.active)
    True

Validate removal event::

    >>> remove_male.click('validate_event')
    >>> remove_male.reload()
    >>> remove_male.state
    'validated'
    >>> male.reload()
    >>> male.removal_date == today
    True
    >>> male.removal_reason == removal_reason
    True
    >>> male.location == male.specie.removed_location
    True
    >>> bool(male.active)
    False

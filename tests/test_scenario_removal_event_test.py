import datetime
import unittest

from proteus import Model
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.farm.tests.tools import create_specie, create_users
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install module
        config = activate_modules('farm')

        # Compute now and today
        now = datetime.datetime.now()
        today = datetime.date.today()

        # Create company
        _ = create_company()
        company = get_company()

        # Create specie
        specie, breed, _ = create_specie('Pig')

        # Create farm users
        users = create_users(company)
        male_user = users['male']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])

        # Set user and context
        config.user = male_user.id
        config._context['specie'] = specie.id
        config._context['animal_type'] = 'female'

        # Create male
        Animal = Model.get('farm.animal')
        male = Animal()
        male.type = 'male'
        male.specie = specie
        male.breed = breed
        male.initial_location = warehouse.storage_location
        male.save()
        self.assertEqual(male.location.code, 'STO')
        self.assertEqual(male.farm.code, 'WH')

        # Create removal event
        RemovalType = Model.get('farm.removal.type')
        removal_type = RemovalType.find([], limit=1)[0]
        RemovalReason = Model.get('farm.removal.reason')
        removal_reason = RemovalReason.find([], limit=1)[0]
        RemovalEvent = Model.get('farm.removal.event')
        remove_male = RemovalEvent()
        remove_male.animal_type = 'male'
        remove_male.specie = specie
        remove_male.farm = warehouse
        remove_male.animal = male
        remove_male.timestamp = now
        remove_male.from_location = male.location
        remove_male.removal_type = removal_type
        remove_male.reason = removal_reason
        remove_male.save()

        # Animal doesn't change its values
        male.reload()
        male.removal_date
        male.removal_reason
        self.assertEqual(bool(male.active), True)

        # Validate removal event
        remove_male.click('validate_event')
        remove_male.reload()
        self.assertEqual(remove_male.state, 'validated')
        male.reload()
        self.assertEqual(male.removal_date, today)
        self.assertEqual(male.removal_reason, removal_reason)
        self.assertEqual(male.location, male.specie.removed_location)
        self.assertEqual(bool(male.active), False)

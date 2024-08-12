import datetime
import unittest

from dateutil.relativedelta import relativedelta
from proteus import Model
from trytond.modules.company.tests.tools import create_company
from trytond.modules.farm.tests.tools import create_specie
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

        # Create company
        _ = create_company()

        # Create specie
        specie, breed, products = create_specie('Pig')
        individual_product = products['individual']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])

        # Create male to be transformed to individual
        Animal = Model.get('farm.animal')
        male_to_individual = Animal(type='male',
                                    specie=specie,
                                    breed=breed,
                                    initial_location=warehouse.storage_location)
        male_to_individual.save()
        self.assertEqual(male_to_individual.location.code, 'STO')
        self.assertEqual(male_to_individual.farm.code, 'WH')

        # Compute today and now
        now = datetime.datetime.now()
        today = datetime.date.today()

        # Create transformation event
        TransformationEvent = Model.get('farm.transformation.event')
        transform_male_to_individual = TransformationEvent(
            animal_type='male',
            specie=specie,
            farm=warehouse,
            timestamp=now,
            animal=male_to_individual,
            from_location=male_to_individual.location,
            to_animal_type='individual',
            to_location=warehouse.storage_location)
        transform_male_to_individual.save()

        # Animal doesn't chage its values
        male_to_individual.reload()
        male_to_individual.location = warehouse.storage_location
        self.assertEqual(male_to_individual.active, 1)

        # Validate transformation event
        TransformationEvent.validate_event([transform_male_to_individual.id],
                                           config.context)
        transform_male_to_individual.reload()
        self.assertEqual(transform_male_to_individual.state, 'validated')
        to_animal = transform_male_to_individual.to_animal
        self.assertEqual(to_animal.active, 1)
        self.assertEqual(to_animal.type, 'individual')
        self.assertEqual(to_animal.lot.cost_price,
                         individual_product.cost_price)
        self.assertEqual(to_animal.location,
                         transform_male_to_individual.to_location)
        male_to_individual.reload()
        self.assertEqual(male_to_individual.removal_date, today)
        self.assertEqual(male_to_individual.location,
                         warehouse.production_location)

        # ..  >>> male_to_individual.active
        # ..  0

        # Create female to be transformed to a new group
        female_to_group = Animal(type='female',
                                 specie=specie,
                                 breed=breed,
                                 initial_location=warehouse.storage_location)
        female_to_group.save()
        self.assertEqual(female_to_group.location.code, 'STO')
        self.assertEqual(female_to_group.farm.code, 'WH')

        # Create transformation event
        transform_female_to_group = TransformationEvent(
            animal_type='female',
            specie=specie,
            farm=warehouse,
            timestamp=now,
            animal=female_to_group,
            from_location=female_to_group.location,
            to_animal_type='group',
            to_location=warehouse.storage_location)
        transform_female_to_group.save()

        # Animal doesn't chage its values
        female_to_group.reload()
        female_to_group.location = warehouse.storage_location
        self.assertEqual(female_to_group.active, 1)

        # Validate transformation event
        TransformationEvent.validate_event([transform_female_to_group.id],
                                           config.context)
        transform_female_to_group.reload()
        self.assertEqual(transform_female_to_group.state, 'validated')
        to_group = transform_female_to_group.to_animal_group
        self.assertEqual(to_group.active, 1)
        self.assertEqual(to_animal.initial_location,
                         transform_female_to_group.to_location)
        female_to_group.reload()
        self.assertEqual(female_to_group.removal_date, today)
        self.assertEqual(female_to_group.location,
                         warehouse.production_location)

        # ..  >>> female_to_group.active
        # ..  0
        # ..  TODO maybe more test over group: quantitites, locations...

        # Create individual to be transformed to female
        individual_to_female = Animal(
            type='individual',
            specie=specie,
            breed=breed,
            sex='female',
            initial_location=warehouse.storage_location)
        individual_to_female.save()
        self.assertEqual(individual_to_female.location.code, 'STO')
        self.assertEqual(individual_to_female.farm.code, 'WH')

        # Create transformation event
        transform_individual_to_female = TransformationEvent(
            animal_type='individual',
            specie=specie,
            farm=warehouse,
            timestamp=now,
            animal=individual_to_female,
            from_location=individual_to_female.location,
            to_animal_type='female',
            to_location=warehouse.storage_location)
        transform_individual_to_female.save()

        # Animal doesn't chage its values
        individual_to_female.reload()
        individual_to_female.location = warehouse.storage_location
        self.assertEqual(individual_to_female.active, 1)

        # Validate transformation event
        TransformationEvent.validate_event([transform_individual_to_female.id],
                                           config.context)
        transform_individual_to_female.reload()
        self.assertEqual(transform_individual_to_female.state, 'validated')
        to_animal = transform_individual_to_female.to_animal
        self.assertEqual(to_animal.active, 1)
        self.assertEqual(to_animal.type, 'female')
        self.assertEqual(to_animal.location,
                         transform_individual_to_female.to_location)
        individual_to_female.reload()
        self.assertEqual(individual_to_female.removal_date, today)
        self.assertEqual(individual_to_female.location,
                         warehouse.production_location)

        # ..  >>> individual_to_female.active
        # ..  0

        # Create individual to be transformed to existing group
        individual_to_group = Animal(
            type='individual',
            specie=specie,
            breed=breed,
            sex='undetermined',
            initial_location=warehouse.storage_location)
        individual_to_group.save()
        self.assertEqual(individual_to_group.location.code, 'STO')
        self.assertEqual(individual_to_group.farm.code, 'WH')

        # Create existing group
        AnimalGroup = Model.get('farm.animal.group')
        context_tmp = config.context.copy()
        config._context.update({
            'animal_type': 'group',
        })
        existing_group = AnimalGroup(
            specie=specie,
            breed=breed,
            initial_location=warehouse.storage_location,
            initial_quantity=4,
            arrival_date=(today - relativedelta(days=3)),
        )
        existing_group.save()
        config._context = context_tmp

        # Create transformation event
        transform_individual_to_group = TransformationEvent(
            animal_type='individual',
            specie=specie,
            farm=warehouse,
            timestamp=now,
            animal=individual_to_group,
            from_location=individual_to_group.location,
            to_animal_type='group',
            to_location=warehouse.storage_location,
            to_animal_group=existing_group)
        transform_individual_to_group.save()

        # Validate transformation event
        TransformationEvent.validate_event([transform_individual_to_group.id],
                                           config.context)
        transform_individual_to_group.reload()
        self.assertEqual(transform_individual_to_group.state, 'validated')
        individual_to_group.reload()
        self.assertEqual(individual_to_group.removal_date, today)
        self.assertEqual(individual_to_group.location,
                         warehouse.production_location)

        # ..  >>> individual_to_group.active
        # ..  0
        existing_group.reload()
        self.assertEqual(existing_group.active, 1)
        # ..  TODO maybe more test over group: quantitites, locations...

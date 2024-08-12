import datetime
import unittest
from decimal import Decimal

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

        # Create company
        _ = create_company()
        company = get_company()

        # Create specie
        specie, breed, products = create_specie('Pig')

        # Create farm users
        users = create_users(company)
        individual_user = users['individual']
        group_user = users['group']
        female_user = users['female']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])

        # Create locations
        location1 = Location()
        location1.name = 'Location 1'
        location1.code = 'L1'
        location1.type = 'storage'
        location1.parent = warehouse.storage_location
        location1.save()
        location2 = Location()
        location2.name = 'Location 2'
        location2.code = 'L2'
        location2.type = 'storage'
        location2.parent = warehouse.storage_location
        location2.save()

        # Create individual
        config.user = individual_user.id
        Animal = Model.get('farm.animal')
        individual = Animal()
        individual.type = 'individual'
        individual.specie = specie
        individual.breed = breed
        individual.initial_location = location1
        individual.save()
        self.assertEqual(individual.location.code, 'L1')
        self.assertEqual(individual.farm.code, 'WH')

        # Create individual move event
        MoveEvent = Model.get('farm.move.event')
        move_individual = MoveEvent()
        move_individual.animal_type = 'individual'
        move_individual.specie = specie
        move_individual.farm = warehouse
        move_individual.animal = individual
        move_individual.quantity = 1
        move_individual.timestamp = now
        move_individual.from_location = individual.location
        move_individual.to_location = location2
        move_individual.weight = Decimal('80.50')
        move_individual.save()

        # Animal doesn't change its values
        individual.reload()
        self.assertEqual(individual.location, location1)
        individual.current_weight

        # Validate individual move event
        move_individual.click('validate_event')
        self.assertEqual(move_individual.state, 'validated')
        individual.reload()
        self.assertEqual(individual.location, location2)
        self.assertEqual(individual.current_weight.weight, Decimal('80.50'))

        # Create individual move event changing cost price
        self.assertEqual(individual.lot.cost_price, Decimal('25.0000'))
        config.user = individual_user.id
        move_individual = MoveEvent()
        move_individual.animal_type = 'individual'
        move_individual.specie = specie
        move_individual.farm = warehouse
        move_individual.animal = individual
        move_individual.timestamp = now
        move_individual.from_location = individual.location
        move_individual.to_location = location1
        move_individual.unit_price = Decimal('30.0')
        move_individual.save()
        self.assertEqual(move_individual.unit_price, Decimal('30.0'))
        move_individual.click('validate_event')
        self.assertEqual(move_individual.state, 'validated')
        individual.reload()
        self.assertEqual(individual.location, location1)
        self.assertEqual(individual.lot.cost_price, Decimal('25.0000'))

        # Create group
        config.user = group_user.id
        AnimalGroup = Model.get('farm.animal.group')
        animal_group = AnimalGroup(specie=specie,
                                   breed=breed,
                                   initial_location=location2,
                                   initial_quantity=4)
        animal_group.save()

        with config.set_context({'locations': [location2.id]}):
            animal_group = AnimalGroup(animal_group.id)
            self.assertEqual(animal_group.lot.quantity, 4.0)

        # Create animal_group move event
        config.user = group_user.id
        MoveEvent = Model.get('farm.move.event')
        move_animal_group = MoveEvent()
        move_animal_group.animal_type = 'group'
        move_animal_group.specie = specie
        move_animal_group.farm = warehouse
        move_animal_group.animal_group = animal_group
        move_animal_group.timestamp = now
        move_animal_group.from_location = location2
        move_animal_group.to_location = location1
        move_animal_group.quantity = 3
        move_animal_group.weight = Decimal('80.50')
        move_animal_group.save()

        # Group doesn't change its values
        animal_group.reload()
        animal_group.current_weight

        with config.set_context({'locations': [location2.id]}):
            animal_group = AnimalGroup(animal_group.id)
            self.assertEqual(animal_group.lot.quantity, 4.0)

        # Validate animal_group move event
        move_animal_group.click('validate_event')
        self.assertEqual(move_animal_group.state, 'validated')
        animal_group.reload()
        self.assertEqual(animal_group.current_weight.weight, Decimal('80.50'))

        with config.set_context({'locations': [location2.id]}):
            animal_group = AnimalGroup(animal_group.id)
            self.assertEqual(animal_group.lot.quantity, 1.0)

        with config.set_context({'locations': [location1.id]}):
            animal_group = AnimalGroup(animal_group.id)
            self.assertEqual(animal_group.lot.quantity, 3.0)

        # When moving a non weaned female its group should also be moved
        config.user = female_user.id
        config._context['specie'] = specie.id
        config._context['animal_type'] = 'female'
        Animal = Model.get('farm.animal')
        InseminationEvent = Model.get('farm.insemination.event')
        PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
        FarrowingEvent = Model.get('farm.farrowing.event')
        female = Animal()
        female.type = 'female'
        female.specie = specie
        female.breed = breed
        female.initial_location = location1
        female.save()
        now = datetime.datetime.now()
        inseminate_event = InseminationEvent()
        inseminate_event.farm = warehouse
        inseminate_event.animal = female
        inseminate_event.timestamp = datetime.datetime.now()
        inseminate_event.click('validate_event')
        now = datetime.datetime.now()
        diagnosis_event = PregnancyDiagnosisEvent()
        diagnosis_event.farm = warehouse
        diagnosis_event.animal = female
        diagnosis_event.timestamp = datetime.datetime.now()
        diagnosis_event.result = 'positive'
        diagnosis_event.click('validate_event')
        farrow_event = FarrowingEvent()
        farrow_event.farm = warehouse
        farrow_event.animal = female
        farrow_event.timestamp = datetime.datetime.now()
        farrow_event.live = 6
        farrow_event.click('validate_event')
        female.reload()
        farrowing_group = female.farrowing_group

        with config.set_context({'locations': [female.location.id]}):
            farrowing_group = AnimalGroup(female.farrowing_group.id)
            self.assertEqual(farrowing_group.lot.quantity, 6.0)

        move_female = MoveEvent()
        move_female.animal_type = 'female'
        move_female.specie = specie
        move_female.farm = warehouse
        move_female.animal = female
        move_female.quantity = 1
        move_female.timestamp = now
        move_female.from_location = female.location
        move_female.to_location = location2
        move_female.weight = Decimal('80.50')
        move_female.save()
        move_female.click('validate_event')
        female.reload()
        self.assertEqual(female.location, location2)
        farrowing_event, = MoveEvent.find([
            ('animal_group', '=', farrowing_group.id),
        ],
                                          limit=1)
        self.assertEqual(farrowing_event.state, 'validated')
        farrowing_event.weight
        self.assertEqual(farrowing_event.from_location, location1)
        self.assertEqual(farrowing_event.to_location, location2)

        with config.set_context({'locations': [location2.id]}):
            farrowing_group = AnimalGroup(farrowing_group.id)
            self.assertEqual(farrowing_group.lot.quantity, 6.0)

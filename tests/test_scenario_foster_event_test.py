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

        # Create company
        _ = create_company()
        company = get_company()

        # Create specie
        specie, breed, _ = create_specie('Pig')

        # Create farm users
        users = create_users(company)
        female_user = users['female']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])

        # Set user and context
        config.user = female_user.id
        config._context['specie'] = specie.id
        config._context['animal_type'] = 'female'

        # Create two females to be inseminated, check their pregnancy state, farrow them
        # and do some foster events between them
        Animal = Model.get('farm.animal')
        female1 = Animal()
        female1.type = 'female'
        female1.specie = specie
        female1.breed = breed
        female1.initial_location = warehouse.storage_location
        female1.save()
        self.assertEqual(female1.location.code, 'STO')
        self.assertEqual(female1.farm.code, 'WH')
        female1.current_cycle
        self.assertEqual(female1.state, 'prospective')
        female2 = Animal()
        female2.type = 'female'
        female2.specie = specie
        female2.breed = breed
        female2.initial_location = warehouse.storage_location
        female2.save()
        self.assertEqual(female2.location.code, 'STO')
        self.assertEqual(female2.farm.code, 'WH')
        female2.current_cycle
        self.assertEqual(female2.state, 'prospective')

        # Create insemination events for the females without dose BoM nor Lot and
        # validate them
        InseminationEvent = Model.get('farm.insemination.event')
        now = datetime.datetime.now()
        inseminate_events = InseminationEvent.create([{
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female1.id,
        }, {
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female2.id,
        }], config.context)
        InseminationEvent.validate_event(inseminate_events, config.context)
        self.assertEqual(
            all(
                InseminationEvent(i).state == 'validated'
                for i in inseminate_events), True)

        # Check the females are mated
        female1.reload()
        self.assertEqual(female1.state, 'mated')
        self.assertEqual(female1.current_cycle.state, 'mated')
        female2.reload()
        self.assertEqual(female2.state, 'mated')
        self.assertEqual(female2.current_cycle.state, 'mated')

        # Create pregnancy diagnosis events with positive result and validate them
        PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
        now = datetime.datetime.now()
        diagnosis_events = PregnancyDiagnosisEvent.create([{
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female1.id,
            'result': 'positive',
        }, {
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female2.id,
            'result': 'positive',
        }], config.context)
        PregnancyDiagnosisEvent.validate_event(diagnosis_events, config.context)
        self.assertEqual(
            all(
                PregnancyDiagnosisEvent(i).state == 'validated'
                for i in diagnosis_events), True)

        # Check females are pregnant
        female1.reload()
        self.assertEqual(female1.current_cycle.state, 'pregnant')
        self.assertEqual(female1.current_cycle.pregnant, 1)
        female2.reload()
        self.assertEqual(female2.current_cycle.state, 'pregnant')
        self.assertEqual(female2.current_cycle.pregnant, 1)

        # Create a farrowing event for each female with 7 and 8 lives and validate them
        FarrowingEvent = Model.get('farm.farrowing.event')
        now = datetime.datetime.now()
        farrow_events = FarrowingEvent.create([{
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female1.id,
            'live': 7,
            'stillborn': 2,
        }, {
            'animal_type': 'female',
            'specie': specie.id,
            'farm': warehouse.id,
            'timestamp': now,
            'animal': female2.id,
            'live': 8,
            'stillborn': 1,
            'mummified': 2,
        }], config.context)
        FarrowingEvent.validate_event(farrow_events, config.context)
        self.assertEqual(
            all(FarrowingEvent(i).state == 'validated' for i in farrow_events),
            True)

        # Check females are not pregnant, their current cycle are in 'lactating' state,
        # they are 'mated' and check females functional fields values
        female1.reload()
        self.assertEqual(female1.current_cycle.pregnant, 0)
        self.assertEqual(female1.current_cycle.state, 'lactating')
        self.assertEqual(female1.state, 'mated')
        self.assertEqual(female1.current_cycle.live, 7)
        self.assertEqual(female1.current_cycle.dead, 2)
        female2.reload()
        self.assertEqual(female2.current_cycle.pregnant, 0)
        self.assertEqual(female2.current_cycle.state, 'lactating')
        self.assertEqual(female2.state, 'mated')
        self.assertEqual(female2.current_cycle.live, 8)
        self.assertEqual(female2.current_cycle.dead, 3)

        # Create a foster event for first female with -1 quantity (foster out) and
        # without pair female
        FosterEvent = Model.get('farm.foster.event')
        now = datetime.datetime.now()
        foster_event1 = FosterEvent(animal_type='female',
                                    specie=specie,
                                    farm=warehouse,
                                    timestamp=now,
                                    animal=female1,
                                    quantity=-1)
        foster_event1.save()

        # Validate foster event
        FosterEvent.validate_event([foster_event1.id], config.context)
        foster_event1.reload()
        self.assertEqual(foster_event1.state, 'validated')

        # Check female's current cycle is still 'lactating', it has 1 foster event and
        # it's fostered value is -1
        female1.reload()
        self.assertEqual(female1.current_cycle.pregnant, False)
        self.assertEqual(female1.current_cycle.state, 'lactating')
        self.assertEqual(len(female1.current_cycle.foster_events), 1)
        self.assertEqual(female1.current_cycle.fostered, -1)

        # Create a foster event for second female with +2 quantity (foster in) and
        # without pair female
        foster_event2 = FosterEvent(animal_type='female',
                                    specie=specie,
                                    farm=warehouse,
                                    timestamp=now,
                                    animal=female2,
                                    quantity=2)
        foster_event2.save()

        # Validate foster event
        FosterEvent.validate_event([foster_event2.id], config.context)
        foster_event2.reload()
        self.assertEqual(foster_event2.state, 'validated')

        # Check female's current cycle is still 'lactating', it has 1 foster event and
        # it's fostered value is 2
        female2.reload()
        self.assertEqual(female2.current_cycle.pregnant, False)
        self.assertEqual(female2.current_cycle.state, 'lactating')
        self.assertEqual(len(female2.current_cycle.foster_events), 1)
        self.assertEqual(female2.current_cycle.fostered, 2)

        # Create a foster event for first female with +4 quantity (foster in) and
        # with the second female as pair female
        now = datetime.datetime.now()
        foster_event3 = FosterEvent(animal_type='female',
                                    specie=specie,
                                    farm=warehouse,
                                    timestamp=now,
                                    animal=female1,
                                    quantity=4,
                                    pair_female=female2)
        foster_event3.save()

        # Validate foster event
        FosterEvent.validate_event([foster_event3.id], config.context)
        foster_event3.reload()
        self.assertEqual(foster_event3.state, 'validated')

        # Check foster event has Pair female foster event and it is validated:
        self.assertNotEqual(foster_event3.pair_event, False)
        self.assertEqual(foster_event3.pair_event.state, 'validated')

        # Check the current cycle of the both females are still 'lactating', they has 2
        # foster events and their fostered value is +3 and -2 respectively
        female1.reload()
        female2.reload()
        self.assertEqual(
            any(f.current_cycle.pregnant for f in [female1, female2]), False)
        self.assertEqual(
            all(f.current_cycle.state == 'lactating'
                for f in [female1, female2]), True)
        self.assertEqual(len(female1.current_cycle.foster_events), 2)
        self.assertEqual(female1.current_cycle.fostered, 3)
        self.assertEqual(len(female2.current_cycle.foster_events), 2)
        self.assertEqual(female2.current_cycle.fostered, -2)

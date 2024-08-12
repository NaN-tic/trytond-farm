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
        female_user = users['female']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])

        # Prepare user and context
        config.user = female_user.id
        config._context['specie'] = specie.id
        config._context['animal_type'] = 'female'

        # Create female to be inseminated, check it's pregnancy state and farrow two
        # times (one without lives and second with)
        Animal = Model.get('farm.animal')
        female = Animal()
        female.type = 'female'
        female.specie = specie
        female.breed = breed
        female.initial_location = warehouse.storage_location
        female.save()
        self.assertEqual(female.location.code, 'STO')
        self.assertEqual(female.farm.code, 'WH')
        female.current_cycle
        self.assertEqual(female.state, 'prospective')

        # Create insemination event without dose BoM nor Lot and validate it
        InseminationEvent = Model.get('farm.insemination.event')
        now = datetime.datetime.now()
        inseminate_female = InseminationEvent()
        inseminate_female.animal_type = 'female'
        inseminate_female.specie = specie
        inseminate_female.farm = warehouse
        inseminate_female.timestamp = now
        inseminate_female.animal = female
        inseminate_female.save()
        InseminationEvent.validate_event([inseminate_female.id], config.context)
        inseminate_female.reload()
        self.assertEqual(inseminate_female.state, 'validated')

        # Check female is mated
        female.reload()
        self.assertEqual(female.state, 'mated')
        self.assertEqual(female.current_cycle.state, 'mated')

        # Create pregnancy diagnosis event with positive result and validate it
        PregnancyDiagnosisEvent = Model.get('farm.pregnancy_diagnosis.event')
        now = datetime.datetime.now()
        diagnose_female = PregnancyDiagnosisEvent()
        diagnose_female.animal_type = 'female'
        diagnose_female.specie = specie
        diagnose_female.farm = warehouse
        diagnose_female.timestamp = now
        diagnose_female.animal = female
        diagnose_female.result = 'positive'
        diagnose_female.save()
        PregnancyDiagnosisEvent.validate_event([diagnose_female.id],
                                               config.context)
        diagnose_female.reload()
        self.assertEqual(diagnose_female.state, 'validated')

        # Check female is pregnant
        female.reload()
        self.assertEqual(female.current_cycle.state, 'pregnant')
        self.assertEqual(female.current_cycle.pregnant, 1)

        # Create farrowing event without lives
        FarrowingEvent = Model.get('farm.farrowing.event')
        FarrowingProblem = Model.get('farm.farrowing.problem')
        farrowing_problem = FarrowingProblem.find([], limit=1)[0]
        now = datetime.datetime.now()
        farrow_event = FarrowingEvent()
        farrow_event.animal_type = 'female'
        farrow_event.specie = specie
        farrow_event.farm = warehouse
        farrow_event.timestamp = now
        farrow_event.animal = female
        farrow_event.live = 0
        farrow_event.stillborn = 4
        farrow_event.mummified = 2
        farrow_event.problem = farrowing_problem
        farrow_event.save()

        # Validate farrowing event
        FarrowingEvent.validate_event([farrow_event.id], config.context)
        farrow_event.reload()
        self.assertEqual(farrow_event.state, 'validated')

        # Check female is not pregnant, its current cycle is in 'unmated' state, it is in
        # 'prospective' state and check female functional fields values
        female.reload()
        self.assertEqual(female.current_cycle.pregnant, False)
        self.assertEqual(female.current_cycle.state, 'unmated')
        self.assertEqual(female.state, 'prospective')
        female.last_produced_group
        self.assertEqual(female.current_cycle.live, 0)
        self.assertEqual(female.current_cycle.dead, 6)

        # Create second insemination event without dose BoM nor Lot and validate it
        now = datetime.datetime.now()
        inseminate_female2 = InseminationEvent()
        inseminate_female2.animal_type = 'female'
        inseminate_female2.specie = specie
        inseminate_female2.farm = warehouse
        inseminate_female2.timestamp = now
        inseminate_female2.animal = female
        inseminate_female2.save()
        InseminationEvent.validate_event([inseminate_female2.id],
                                         config.context)
        inseminate_female2.reload()
        self.assertEqual(inseminate_female2.state, 'validated')

        # Check female has two cycles with diferent sequences, it and its current
        # cycle is mated and the first cycle (old) is unmated
        female.reload()
        self.assertEqual(len(female.cycles), 2)
        self.assertNotEqual(female.cycles[0].sequence,
                            female.cycles[1].sequence)
        self.assertEqual(female.current_cycle.state, 'mated')
        self.assertEqual(female.state, 'mated')
        self.assertEqual(female.cycles[0].state, 'unmated')

        # Create second pregnancy diagnosis event with positive result and validate it
        now = datetime.datetime.now()
        diagnose_female2 = PregnancyDiagnosisEvent()
        diagnose_female2.animal_type = 'female'
        diagnose_female2.specie = specie
        diagnose_female2.farm = warehouse
        diagnose_female2.timestamp = now
        diagnose_female2.animal = female
        diagnose_female2.result = 'positive'
        diagnose_female2.save()
        PregnancyDiagnosisEvent.validate_event([diagnose_female2.id],
                                               config.context)
        diagnose_female2.reload()
        self.assertEqual(diagnose_female2.state, 'validated')

        # Check female is pregnant
        female.reload()
        self.assertEqual(female.current_cycle.pregnant, 1)
        self.assertEqual(female.current_cycle.state, 'pregnant')

        # Create second farrowing event with lives
        now = datetime.datetime.now()
        farrow_event2 = FarrowingEvent()
        farrow_event2.animal_type = 'female'
        farrow_event2.specie = specie
        farrow_event2.farm = warehouse
        farrow_event2.timestamp = now
        farrow_event2.animal = female
        farrow_event2.live = 7
        farrow_event2.stillborn = 2
        farrow_event2.save()

        # Validate farrowing event
        FarrowingEvent.validate_event([farrow_event2.id], config.context)
        farrow_event2.reload()
        self.assertEqual(farrow_event2.state, 'validated')

        # Check female is not pregnant, its current cycle are in 'lactating' state,
        # it is 'mated' and check female functional fields values
        female.reload()
        self.assertEqual(female.current_cycle.pregnant, 0)
        self.assertEqual(female.current_cycle.state, 'lactating')
        self.assertEqual(female.state, 'mated')
        self.assertEqual(female.current_cycle.live, 7)
        self.assertEqual(female.current_cycle.dead, 2)

        # Female childs must have the farrowing cost
        group = farrow_event2.produced_group
        self.assertEqual(group.lot.cost_price, Decimal('20.0'))

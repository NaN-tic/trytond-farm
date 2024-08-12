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
        specie, breed, products = create_specie('Pig')

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

        # Create female to be inseminated, check it's pregnancy state and abort two
        # times
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
        diagnose_female = PregnancyDiagnosisEvent(animal_type='female',
                                                  specie=specie,
                                                  farm=warehouse,
                                                  timestamp=now,
                                                  animal=female,
                                                  result='positive')
        diagnose_female.save()
        PregnancyDiagnosisEvent.validate_event([diagnose_female.id],
                                               config.context)
        diagnose_female.reload()
        self.assertEqual(diagnose_female.state, 'validated')

        # Check female is pregnant
        female.reload()
        self.assertEqual(female.current_cycle.state, 'pregnant')
        self.assertEqual(female.current_cycle.pregnant, 1)

        # Create abort event
        AbortEvent = Model.get('farm.abort.event')
        now = datetime.datetime.now()
        abort_female = AbortEvent(animal_type='female',
                                  specie=specie,
                                  farm=warehouse,
                                  timestamp=now,
                                  animal=female)
        abort_female.save()

        # Validate abort event
        AbortEvent.validate_event([abort_female.id], config.context)
        abort_female.reload()
        self.assertEqual(abort_female.state, 'validated')

        # Check female is not pregnant, it is in 'prospective' state and its current
        # cycle is 'unmated'
        female.reload()
        self.assertEqual(female.current_cycle.pregnant, 0)
        self.assertEqual(female.current_cycle.state, 'unmated')
        self.assertEqual(female.state, 'prospective')

        # Create second insemination event without dose BoM nor Lot and validate it
        now = datetime.datetime.now()
        inseminate_female2 = InseminationEvent(animal_type='female',
                                               specie=specie,
                                               farm=warehouse,
                                               timestamp=now,
                                               animal=female)
        inseminate_female2.save()
        InseminationEvent.validate_event([inseminate_female2.id],
                                         config.context)
        inseminate_female2.reload()
        self.assertEqual(inseminate_female2.state, 'validated')

        # Check female has two cycles but both with the same sequence, it and its current
        # cycle is mated and the first cycle (old) is unmated
        female.reload()
        self.assertEqual(len(female.cycles), 2)
        self.assertEqual(female.cycles[0].sequence, female.cycles[1].sequence)
        self.assertEqual(female.state, 'mated')
        self.assertEqual(female.current_cycle.state, 'mated')
        self.assertEqual(female.cycles[0].state, 'unmated')

        # Create second pregnancy diagnosis event with positive result and validate it
        now = datetime.datetime.now()
        diagnose_female2 = PregnancyDiagnosisEvent(animal_type='female',
                                                   specie=specie,
                                                   farm=warehouse,
                                                   timestamp=now,
                                                   animal=female,
                                                   result='positive')
        diagnose_female2.save()
        PregnancyDiagnosisEvent.validate_event([diagnose_female2.id],
                                               config.context)
        diagnose_female2.reload()
        self.assertEqual(diagnose_female2.state, 'validated')

        # Check female is pregnant
        female.reload()
        self.assertEqual(female.current_cycle.state, 'pregnant')
        self.assertEqual(female.current_cycle.pregnant, 1)

        # Create second abort event
        now = datetime.datetime.now()
        abort_female2 = AbortEvent(animal_type='female',
                                   specie=specie,
                                   farm=warehouse,
                                   timestamp=now,
                                   animal=female)
        abort_female2.save()

        # Validate abort event
        AbortEvent.validate_event([abort_female2.id], config.context)
        abort_female2.reload()
        self.assertEqual(abort_female2.state, 'validated')

        # Check female is not pregnant and it and its current cycle is 'unmated'
        female.reload()
        self.assertEqual(female.current_cycle.pregnant, 0)
        self.assertEqual(female.current_cycle.state, 'unmated')
        self.assertEqual(female.state, 'unmated')

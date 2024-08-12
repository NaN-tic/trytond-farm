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
        semen_product = products['semen']

        # Create farm users
        users = create_users(company)
        female_user = users['female']

        # Get locations
        Location = Model.get('stock.location')
        warehouse, = Location.find([('type', '=', 'warehouse')])
        production_location, = Location.find([('type', '=', 'production')])

        # Create dose Product, BoM and Lot
        ProductUom = Model.get('product.uom')
        unit, = ProductUom.find([('name', '=', 'Unit')])
        cm3, = ProductUom.find([('name', '=', 'Cubic centimeter')])
        ProductTemplate = Model.get('product.template')
        blister_template = ProductTemplate()
        blister_template.name = '100 cm3 blister'
        blister_template.default_uom = unit
        blister_template.type = 'goods'
        blister_template.consumable = True
        blister_template.list_price = Decimal('1')
        blister_template.save()
        blister_product, = blister_template.products
        blister_product.save()
        dose_template = ProductTemplate()
        dose_template.name = '100 cm3 semen dose'
        dose_template.default_uom = unit
        dose_template.type = 'goods'
        dose_template.producible = True
        dose_template.list_price = Decimal('10')
        dose_template.save()
        dose_product, = dose_template.products
        Bom = Model.get('production.bom')
        BomInput = Model.get('production.bom.input')
        BomOutput = Model.get('production.bom.output')
        dose_bom = Bom(
            name='100 cm3 semen dose',
            semen_dose=True,
            specie=specie,
            inputs=[
                BomInput(product=blister_product, uom=unit, quantity=1),
                BomInput(product=semen_product, uom=cm3, quantity=100.00),
            ],
            outputs=[
                BomOutput(product=dose_product, uom=unit, quantity=1.00),
            ],
        )
        dose_bom.save()
        dose_bom.reload()
        ProductBom = Model.get('product.product-production.bom')
        dose_product.boms.append(ProductBom(bom=dose_bom, sequence=1))
        dose_product.save()
        dose_product.reload()
        Lot = Model.get('stock.lot')
        dose_lot = Lot(number='S001', product=dose_product)
        dose_lot.save()

        # Put two units of dose and one of semen in farm storage location
        Move = Model.get('stock.move')
        now = datetime.datetime.now()
        provisioning_move1 = Move()
        provisioning_move1.product = dose_product
        provisioning_move1.uom = unit
        provisioning_move1.quantity = 2.0
        provisioning_move1.from_location = production_location
        provisioning_move1.to_location = warehouse.storage_location
        provisioning_move1.planned_date = now.date()
        provisioning_move1.effective_date = now.date()
        provisioning_move1.company = company
        provisioning_move1.lot = dose_lot
        provisioning_move1.unit_price = dose_product.template.list_price
        provisioning_move1.currency = company.currency
        provisioning_move1.save()
        provisioning_move1.click('do')
        provisioning_move2 = Move()
        provisioning_move2.product = semen_product
        provisioning_move2.uom = cm3
        provisioning_move2.quantity = 1.0
        provisioning_move2.from_location = production_location
        provisioning_move2.to_location = warehouse.storage_location
        provisioning_move2.planned_date = now.date()
        provisioning_move2.effective_date = now.date()
        provisioning_move2.company = company
        provisioning_move2.unit_price = semen_product.template.list_price
        provisioning_move2.currency = company.currency
        provisioning_move2.save()
        provisioning_move2.click('do')

        # Set user and context
        config.user = female_user.id
        config._context['specie'] = specie.id
        config._context['animal_type'] = 'female'

        # Create first female to be inseminated
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

        # Create insemination event with dose BoM and Lot
        InseminationEvent = Model.get('farm.insemination.event')
        now = datetime.datetime.now()
        inseminate_female1 = InseminationEvent()
        inseminate_female1.animal_type = 'female'
        inseminate_female1.specie = specie
        inseminate_female1.farm = warehouse
        inseminate_female1.timestamp = now
        inseminate_female1.animal = female1
        inseminate_female1.dose_bom = dose_bom
        inseminate_female1.dose_lot = dose_lot
        inseminate_female1.save()

        # Validate insemination event
        inseminate_female1.click('validate_event')
        inseminate_female1.reload()
        self.assertEqual(inseminate_female1.state, 'validated')

        # Check female is mated
        female1.reload()
        self.assertEqual(female1.state, 'mated')
        self.assertEqual(female1.current_cycle.state, 'mated')

        # Create insemination event with dose BoM but not Lot
        now = datetime.datetime.now()
        inseminate_female12 = InseminationEvent()
        inseminate_female12.animal_type = 'female'
        inseminate_female12.specie = specie
        inseminate_female12.farm = warehouse
        inseminate_female12.timestamp = now
        inseminate_female12.animal = female1
        inseminate_female12.dose_bom = dose_bom
        inseminate_female12.save()

        # Validate insemination event
        inseminate_female12.click('validate_event')
        inseminate_female12.reload()
        self.assertEqual(inseminate_female12.state, 'validated')

        # Check female is mated and has two insemination events
        female1.reload()
        self.assertEqual(female1.state, 'mated')
        self.assertEqual(female1.current_cycle.state, 'mated')
        self.assertEqual(len(female1.current_cycle.insemination_events), 2)

        # Create second female to be inseminated
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

        # Create insemination event without dose BoM nor Lot
        now = datetime.datetime.now()
        inseminate_female2 = InseminationEvent()
        inseminate_female2.animal_type = 'female'
        inseminate_female2.specie = specie
        inseminate_female2.farm = warehouse
        inseminate_female2.timestamp = now
        inseminate_female2.animal = female2
        inseminate_female2.save()

        # Validate insemination event
        inseminate_female2.click('validate_event')
        inseminate_female2.reload()
        self.assertEqual(inseminate_female2.state, 'validated')

        # Check female is mated
        female2.reload()
        self.assertEqual(female2.state, 'mated')
        self.assertEqual(female2.current_cycle.state, 'mated')

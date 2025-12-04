#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
import math
from datetime import datetime, date, timedelta
from decimal import Decimal
from trytond.model import fields, ModelView, ModelSQL, Workflow, Check, Unique
from trytond.pyson import Bool, Equal, Eval, Id, If
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.exceptions import UserError
from trytond.model.exceptions import ValidationError
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, _EVENT_STATES, _STATES_WRITE_DRAFT,\
    _STATES_VALIDATED, _STATES_VALIDATED_ADMIN


class SemenExtractionEvent(AbstractEvent):
    '''Farm Semen Extraction Event'''
    __name__ = 'farm.semen_extraction.event'
    _table = 'farm_semen_extraction_event'

    reference = fields.Char('Reference')
    semen_product = fields.Function(fields.Many2One('product.product',
            "Semen's Product"),
        'on_change_with_semen_product')
    untreated_semen_uom = fields.Many2One('product.uom', 'Semen Extracted UOM',
        domain=[('category', '=', Id('product', 'uom_cat_volume'))],
        required=True,
        states=_STATES_WRITE_DRAFT)
    untreated_semen_unit_digits = fields.Function(
        fields.Integer('Semen Extracted Unit Digits'),
        'on_change_with_untreated_semen_unit_digits')
    untreated_semen_qty = fields.Float('Semen Extracted Qty.',
        digits=(16, Eval('untreated_semen_unit_digits', 3)), required=True,
        states=_STATES_WRITE_DRAFT,
        depends=['untreated_semen_unit_digits'],
        help='The amount of untreated semen taken from male.')
    test_required = fields.Boolean('Test Required',
        help='Check to require quality test')
    test = fields.One2One('farm.semen_extraction.event-quality.test', 'event',
        'test', string='Quality Test', readonly=False, domain=[
            # TODO: Falla el test al cridar el super().create()
            #('document', '=', 'product.product', Eval('semen_product')),
            #('unit.category', '=', Id('product', 'uom_cat_volume')),
            #('unit', '=', Id('product', 'uom_cubic_centimeter')),
            ],
        states={
            'required': Eval('test_required', True) & (Eval('id', 0) > 0),
            'invisible': ~Eval('test_required', True),
            })
    formula_uom = fields.Function(fields.Many2One('product.uom',
            'Formula UOM'), 'get_formula_uom')
    formula_unit_digits = fields.Function(
        fields.Integer('Formula Unit Digits'), 'get_formula_unit_digits')
    formula_result = fields.Function(fields.Float('Formula Result',
            digits=(16, Eval('formula_unit_digits', 2)),
            depends=['formula_unit_digits'],
            help='Value calculated by the formula of Quality Test.'),
        'get_formula_result')
    solvent_calculated_qty = fields.Function(
        fields.Float('Calc. Semen Solvent Qty.',
            digits=(16, Eval('formula_unit_digits', 2)),
            depends=['formula_unit_digits'],
            help='The theorical amount of solvent to add to the extracted '
            'semen (in UoM of the formula), calculated from the amount '
            'extracted and the value of the formula.'),
        'get_semen_quantities')
    semen_calculated_qty = fields.Function(
        fields.Float('Calc. Semen Produced Qty.',
            digits=(16, Eval('formula_unit_digits', 2)),
            depends=['formula_unit_digits'],
            help='The theorical amount of mixture of semen produced (in UoM '
            'of the formula), calculated from the amount extracted and the '
            'value of the formula.'),
        'get_semen_quantities')
    semen_qty = fields.Float('Semen Produced Qty.',
        digits=(16, Eval('formula_unit_digits', 3)),
        depends=['formula_unit_digits'],
        help='The amount of mixture of semen produced (in the UoM of formula)')
    semen_lot = fields.Many2One('stock.lot', 'Semen Lot', readonly=True,
        domain=[
            ('product', '=', Eval('semen_product')),
            ('quantity', '>', 0.0)
            ], states=_STATES_VALIDATED, search_context={
            'locations': If(Bool(Eval('farm')), [Eval('farm')], []),
            'stock_date_end': date.today(),
            })
    semen_move = fields.Many2One('stock.move', 'Semen Move', readonly=True,
        domain=[
            ('lot', '=', Eval('semen_lot')),
            ('unit', '=', Eval('formula_uom')),
            ], states=_STATES_VALIDATED_ADMIN)
    dose_location = fields.Many2One('stock.location', 'Doses Location',
        domain=[
            ('warehouse', '=', Eval('farm')),
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ], required=True, states=_STATES_WRITE_DRAFT,
        help="Destination location of semen doses")
    dose_bom = fields.Many2One('production.bom', 'Dose Container', domain=[
            ('semen_dose', '=', True),
            ('specie', '=', Eval('specie')),
            ], states=_STATES_WRITE_DRAFT)
    dose_calculated_units = fields.Function(fields.Float('Calculated Doses',
            digits=(16, 2),
            help='Calculates the number of doses based on Container (BoM) and '
            'Semen Produced Qty. The quantity is expressed in the UoM of the '
            'Container.\n'
            'You have to save the event to see this calculated value.'),
        'on_change_with_dose_calculated_units')
    doses = fields.One2Many('farm.semen_extraction.dose', 'event', 'Doses',
        states=_STATES_WRITE_DRAFT)
    doses_semen_qty = fields.Function(fields.Float('Dose Semen Qty.',
            digits=(16, Eval('formula_unit_digits', 2)), states={
                'invisible': Equal(Eval('state'), 'validated'),
                }, depends=['formula_unit_digits'],
            help='Total quantity of semen in the doses of list (expressed in '
            'the UoM of the formula).'),
        'on_change_with_doses_semen_qty')
    semen_remaining_qty = fields.Function(fields.Float('Remaining Semen',
            digits=(16, Eval('formula_unit_digits', 2)), states={
                'invisible': Equal(Eval('state'), 'validated'),
                }, depends=['formula_unit_digits'],
            help='The remaining quantity of semen of the specified doses '
            '(expressed in the UoM of the formula).'),
        'on_change_with_semen_remaining_qty')

    @classmethod
    def __setup__(cls):
        super(SemenExtractionEvent, cls).__setup__()
        cls.animal.domain += [
            ('type', '=', 'male'),
            ]
        t = cls.__table__()
        cls._sql_constraints += [
            ('untreated_semen_qty_positive',
                Check(t, t.untreated_semen_qty > 0.0),
                'farm.check_semen_extraction_quantity_positive'),
            ]
        cls._buttons.update({
            'calculate_doses': {
                'invisible': Eval('state') != 'draft',
                'readonly': Bool(Eval('doses')),
                'icon': 'tryton-forward',
                },
            })

    @staticmethod
    def default_animal_type():
        return 'male'

    @staticmethod
    def default_untreated_semen_uom():
        ModelData = Pool().get('ir.model.data')
        return ModelData.get_id('product', 'uom_cubic_centimeter')

    @staticmethod
    def valid_animal_types():
        return ['male']

    @fields.depends('specie')
    def on_change_with_semen_product(self, name=None):
        return self.specie and self.specie.semen_product.id

    @fields.depends('untreated_semen_uom')
    def on_change_with_untreated_semen_unit_digits(self, name=None):
        return (self.untreated_semen_uom and self.untreated_semen_uom.digits
            or 3)

    def get_formula_uom(self, name):
        return self.test and self.test.unit and self.test.unit.id

    def get_formula_unit_digits(self, name):
        return self.test and self.test.unit_digits or 2

    def get_formula_result(self, name):
        return self.test and self.test.formula_result

    @classmethod
    def get_semen_quantities(cls, extraction_events, names):
        Uom = Pool().get('product.uom')
        res = {
            'semen_calculated_qty': {},
            'solvent_calculated_qty': {},
            }
        for extraction_event in extraction_events:
            res['semen_calculated_qty'][extraction_event.id] = 0.0
            res['solvent_calculated_qty'][extraction_event.id] = 0.0
            untreated_semen_qty = Uom.compute_qty(
                extraction_event.untreated_semen_uom,
                extraction_event.untreated_semen_qty,
                (extraction_event.formula_uom if extraction_event.test_required
                    else extraction_event.untreated_semen_uom))
            semen_calculated_qty = ((extraction_event.formula_result or 0.0) *
                    untreated_semen_qty)
            res['semen_calculated_qty'][extraction_event.id] = (
                semen_calculated_qty)
            res['solvent_calculated_qty'][extraction_event.id] = (
                semen_calculated_qty - untreated_semen_qty)
        if 'semen_calculated_qty' not in names:
            del res['semen_calculated_qty']
        if 'solvent_calculated_qty' not in names:
            del res['solvent_calculated_qty']
        return res

    @fields.depends('specie', 'dose_bom', 'formula_uom', 'semen_qty')
    def on_change_with_dose_calculated_units(self, name=None):
        Uom = Pool().get('product.uom')
        if not self.dose_bom or not self.semen_qty:
            return 0.0

        semen_product = self.specie.semen_product
        dose_product = self.dose_bom.output_products[0]
        dose_uom = self.dose_bom.outputs[0].unit
        factor = self.dose_bom.compute_factor(dose_product, 1.0, dose_uom)
        consumed_semen_qty = 0.0  # by 1 unit of dose
        for input_ in self.dose_bom.inputs:
            if input_.product == semen_product:
                consumed_semen_qty = input_.compute_quantity(factor)
                if not self.formula_uom:
                    continue
                consumed_semen_qty = Uom.compute_qty(self.formula_uom,
                    consumed_semen_qty, input_.unit)
                break
        assert consumed_semen_qty > 0.0, ('BOM of semen extraction event "%s" '
            'generetes 0.0 consumed semen qty' % self.id)
        n_doses = float(self.semen_qty) / consumed_semen_qty
        digits = self.__class__.dose_calculated_units.digits[1]
        return float(Decimal(n_doses).quantize(Decimal(str(10.0 ** -digits))))

    @fields.depends('semen_qty', 'doses')
    def on_change_with_doses_semen_qty(self, name=None):
        return self._doses_semen_quantities()['doses_semen_qty']

    @fields.depends('semen_qty', 'doses')
    def on_change_with_semen_remaining_qty(self, name=None):
        return self._doses_semen_quantities()['semen_remaining_qty']

    def _doses_semen_quantities(self):
        res = {
            'doses_semen_qty': 0.0,
            'semen_remaining_qty': self.semen_qty or 0.0,
            }
        if self.semen_qty is None or not self.doses:
            return res
        for dose in self.doses:
            res['doses_semen_qty'] += dose.semen_qty or 0.0
        res['semen_remaining_qty'] = self.semen_qty - res['doses_semen_qty']
        return res

    @fields.depends('farm')
    def on_change_with_dose_location(self, name=None):
        return self.farm and self.farm.storage_location.id or None

    @classmethod
    def validate(cls, extraction_events):
        super(SemenExtractionEvent, cls).validate(extraction_events)
        for extraction_event in extraction_events:
            extraction_event.check_doses_semen_quantity()

    def check_doses_semen_quantity(self):
        # It doesn't check 'Validated' events because it was checked before
        # validating and if it changes is because BoM definition has changed
        # and it can't modify past events
        if self.state == 'valid':
            return
        if self.semen_remaining_qty < 0.0:
            raise ValidationError(gettext('farm.more_semen_in_doses_than_produced',
                    event=self.rec_name))

    @classmethod
    @ModelView.button
    def calculate_doses(cls, events):
        Dose = Pool().get('farm.semen_extraction.dose')
        for extraction_event in events:
            if extraction_event.doses:
                raise UserError(gettext('farm.dose_already_defined',
                        event=extraction_event.rec_name))
            if not extraction_event.dose_bom:
                continue
            n_doses = math.floor(extraction_event.dose_calculated_units)
            new_dose = Dose(
                event=extraction_event.id,
                sequence=1,
                bom=extraction_event.dose_bom.id,
                quantity=n_doses)
            new_dose.save()

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Create and validate Production Move for semen extraction, creating a
        Production Lot for semen extracted (see __doc__ of
        _create_semen_production function for more details).

        Create and validate Production Move for Doses creation from semen
        extracted, creating a Production Lot for each dose (see __doc__ of
        _create_doses_production function for more details).
        """
        pool = Pool()
        Move = pool.get('stock.move')
        Production = pool.get('production')
        QualityTest = pool.get('quality.test')

        todo_moves = []
        todo_productions = []
        for extraction_event in events:
            assert (not extraction_event.semen_move and
                not extraction_event.semen_lot), ('Semen move and lot must '
                    'to be empty to validate the Extraction Event %s'
                    % extraction_event.id)
            if not extraction_event.doses:
                raise UserError(gettext('farm.no_doses_on_validate',
                        event=extraction_event.rec_name))

            if extraction_event.test_required:
                to_aprove = (extraction_event.test.state == 'confirmed')
                if extraction_event.test.state == 'draft':
                    QualityTest.confirmed([extraction_event.test])
                    to_aprove = True
                if to_aprove:
                    QualityTest.successful([extraction_event.test])
                quality_test = QualityTest(extraction_event.test)

                if not quality_test.success:
                    raise UserError(gettext('farm.quality_test_not_succeeded',
                            test=quality_test.rec_name,
                            event=extraction_event.rec_name,
                            ))

            semen_move = extraction_event._get_semen_move()
            semen_move.save()
            todo_moves.append(semen_move)

            extraction_event.semen_move = semen_move
            extraction_event.semen_lot = semen_move.lot
            extraction_event.test.document = semen_move.lot
            extraction_event.test.save()

            for dose in extraction_event.doses:
                assert not dose.production, (
                    'Production must to be empty for all doses to validate '
                    'the Extraction Event "%s"' % extraction_event.rec_name)
                dose_production = dose._get_production(semen_move.lot)
                dose_production.save()
                todo_productions.append(dose_production)

                dose.production = dose_production
                dose.save()

            extraction_event.save()
            extraction_event.animal.update_last_extraction(extraction_event)

        Move.assign(todo_moves)
        Move.do(todo_moves)

        Production.wait(todo_productions)
        Production.assign_try(todo_productions)
        Production.run(todo_productions)
        Production.do(todo_productions)

    def _get_semen_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Company = pool.get('company.company')

        context = Transaction().context
        company = Company(context['company'])

        semen_lot = self._get_semen_lot()
        semen_lot.save()

        return Move(
            product=self.specie.semen_product,
            unit=self.formula_uom,
            quantity=self.semen_qty,
            from_location=self.farm.production_location,
            to_location=self.dose_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=company,
            lot=semen_lot,
            unit_price=self.specie.semen_product.cost_price,
            currency=company.currency,
            origin=self)

    def _get_semen_lot(self):
        pool = Pool()
        FarmLine = pool.get('farm.specie.farm_line')
        Lot = pool.get('stock.lot')

        farm_line, = FarmLine.search([
                ('specie', '=', self.specie.id),
                ('farm', '=', self.farm.id),
                ('has_male', '=', True),
                ])
        return Lot(
            number=farm_line.semen_lot_sequence.get(),
            product=self.specie.semen_product.id)

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        QualityTemplate = pool.get('quality.template')
        QualityTest = pool.get('quality.test')
        Specie = pool.get('farm.specie')

        todo_tests = []
        vlist = [x.copy() for x in vlist]
        for values in vlist:
            if values.get('test'):
                continue
            specie_id = values.get('specie') or cls.default_specie()
            if specie_id:
                specie = Specie(specie_id)
                semen_prod_ref = 'product.product,%d' % specie.semen_product.id
                # Configure the test in specie?
                templates = QualityTemplate.search([
                        ('document', '=', semen_prod_ref),
                        ])
                if not templates:
                    raise UserError(gettext(
                            'farm.missing_quality_template_for_semen',
                            product=specie.semen_product.rec_name))
                test = QualityTest(
                    test_date=values.get('timestamp') or datetime.today(),
                    templates=[templates[0]],
                    document=semen_prod_ref,
                    )
                test.save()
                values['test'] = test.id
                todo_tests.append(test)
        if todo_tests:
            QualityTest.apply_templates(todo_tests)
        return super(SemenExtractionEvent, cls).create(vlist)

    @classmethod
    def copy(cls, extraction_events, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'test': None,
                'semen_lot': None,
                'semen_move': None,
                })
        return super(SemenExtractionEvent, cls).copy(extraction_events,
            default=default)

    @classmethod
    def delete(cls, events):
        QualityTest = Pool().get('quality.test')

        males = []
        tests = []
        for event in events:
            males.append(event.animal)
            if event.test:
                tests.append(event.test)
        if tests:
            QualityTest.write(tests, {
                    'semen_extraction': False,
                    })
        res = super(SemenExtractionEvent, cls).delete(events)
        if tests:
            QualityTest.delete(tests)
        for male in males:
            male.update_last_extraction()
        return res


class SemenExtractionEventQualityTest(ModelSQL):
    "Semen Extraction Event - Quality Test"
    __name__ = 'farm.semen_extraction.event-quality.test'

    event = fields.Many2One('farm.semen_extraction.event',
        'Semen Extraction Event', required=True, ondelete='RESTRICT')
    test = fields.Many2One('quality.test', 'Quality Test', required=True,
        ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(SemenExtractionEventQualityTest, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('event_unique', Unique(t, t.event),
                'farm.semen_extraction_unique'),
            ('test_unique', Unique(t, t.test), 'farm.quality_test_unique'),
            ]


class SemenExtractionDose(ModelSQL, ModelView):
    'Farm Semen Extraction Dose'
    __name__ = 'farm.semen_extraction.dose'
    _order = [
        ('event', 'ASC'),
        ('sequence', 'ASC'),
        ]

    event = fields.Many2One('farm.semen_extraction.event', 'Event',
        required=True, ondelete='CASCADE')
    specie = fields.Function(fields.Many2One('farm.specie',
            "Specie"),
        'on_change_with_specie')
    semen_unit_digits = fields.Function(fields.Integer('Semen Unit Digits'),
        'get_semen_unit_digits')
    state = fields.Function(fields.Selection(_EVENT_STATES, 'Event State'),
        'on_change_with_state')
    sequence = fields.Integer('Line Num.', required=True)
    bom = fields.Many2One('production.bom', 'Container', required=True,
        domain=[
            ('semen_dose', '=', True),
            ('specie', '=', Eval('specie')),
        ], states=_STATES_WRITE_DRAFT)
    quantity = fields.Integer('Quantity (Units)', required=True,
        states=_STATES_WRITE_DRAFT)
    semen_qty = fields.Function(fields.Float('Semen Qty.',
            digits=(16, Eval('semen_unit_digits', 2)), states={
                'invisible': Equal(Eval('state'), 'validated'),
                }, depends=['semen_unit_digits'],
            help='Total quantity of semen in the dose (expressed in Formula '
            'UoM).'),
        'on_change_with_semen_qty')
    dose_product = fields.Function(fields.Many2One('product.product',
            "dose_product"),
        'on_change_with_dose_product')
    production = fields.Many2One('production', 'Dose Production',
        readonly=True, states=_STATES_VALIDATED_ADMIN)
    lot = fields.Many2One('stock.lot', 'Lot', readonly=True, domain=[
            ('product', '=', Eval('dose_product')),
        ], states=_STATES_VALIDATED)

    @classmethod
    def __setup__(cls):
        super(SemenExtractionDose, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('event_sequence_uniq', Unique(t, t.event, t.sequence),
                'farm.dose_line_unique'),
            ('event_bom_uniq', Unique(t, t.event, t.bom),
                'farm.dose_event_bom_unique'),
            ('quantity_positive', Check(t, t.quantity > 0),
                'farm.check_dose_quantity_positive'),
            ]

    # TODO: these defaults should not be necessary, but...
    @staticmethod
    def default_specie():
        return Pool().get('farm.semen_extraction.event').default_specie()

    @staticmethod
    def default_state():
        return Pool().get('farm.semen_extraction.event').default_state()

    @staticmethod
    def default_sequence():
        return 0

    def get_rec_name(self, name):
        return "#%d (%s)" % (self.sequence,
            self.lot and self.lot.rec_name or self.bom.rec_name)

    @fields.depends('event', '_parent_event.specie')
    def on_change_with_specie(self, name=None):
        return self.event and self.event.specie.id or None

    def get_semen_unit_digits(self, name):
        return self.event and self.event.formula_unit_digits

    @fields.depends('event', '_parent_event.state')
    def on_change_with_state(self, name=None):
        return self.event and self.event.state or 'draft'

    @fields.depends('_parent_event.specie', '_parent_event.formula_uom',
        'event', 'bom', 'quantity')
    def on_change_with_semen_qty(self, name=None):
        Uom = Pool().get('product.uom')
        if not self.event or not self.bom or not self.quantity:
            return
        semen_product = self.event.specie.semen_product
        dose_product = self.bom.output_products[0]
        dose_uom = self.bom.outputs[0].unit
        factor = self.bom.compute_factor(dose_product, self.quantity, dose_uom)
        semen_qty = 0.0  # by 1 unit of dose
        for input_ in self.bom.inputs:
            if input_.product == semen_product:
                semen_qty = input_.compute_quantity(factor)
                if not self.event.formula_uom:
                    continue
                semen_qty = Uom.compute_qty(self.event.formula_uom, semen_qty,
                    input_.unit)
                break
        return semen_qty

    @fields.depends('bom')
    def on_change_with_dose_product(self, name=None):
        return self.bom and self.bom.output_products[0].id

    @classmethod
    def validate(cls, extraction_doses):
        ExtractionEvent = Pool().get('farm.semen_extraction.event')
        super(SemenExtractionDose, cls).validate(extraction_doses)
        events = list(set(ed.event for ed in extraction_doses))
        ExtractionEvent.validate(events)

    def _get_production(self, semen_lot):
        pool = Pool()
        Production = pool.get('production')
        Company = pool.get('company.company')

        context = Transaction().context
        company = Company(context['company'])

        production = Production(
            reference=self.rec_name,
            effective_date=self.event.timestamp.date(),
            company=company,
            warehouse=self.event.farm,
            location=self.event.farm.production_location,
            product=self.bom.output_products[0],
            bom=self.bom,
            unit=self.bom.outputs[0].unit,
            quantity=self.quantity,
            state='draft')

        production.set_moves()
        for input_move in production.inputs:
            if input_move.product.id == self.specie.semen_product.id:
                input_move.lot = semen_lot
            input_move.from_location = self.event.dose_location
            input_move.save()

        dose_lot = self._get_lot()
        dose_lot.save()

        production.outputs[0].lot = dose_lot
        production.outputs[0].to_location = self.event.dose_location
        production.outputs[0].save()

        self.lot = dose_lot
        return production

    def _get_lot(self):
        pool = Pool()
        FarmLine = pool.get('farm.specie.farm_line')
        Lot = pool.get('stock.lot')

        farm_line, = FarmLine.search([
                ('specie', '=', self.event.specie.id),
                ('farm', '=', self.event.farm.id),
                ('has_male', '=', True),
                ])

        number = []
        number.append(self.event.animal.breed.rec_name)
        number.append(self.event.animal.rec_name)
        if self.event.reference:
            number.append(self.event.reference)
        number.append(farm_line.dose_lot_sequence.get())
        number = '/'.join(number)
        return Lot(number=number, product=self.dose_product.id,
            expiration_date=(self.event.timestamp +
                timedelta(days=self.dose_product.expiration_time or 4)).date())

    @classmethod
    def copy(cls, doses, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'production': None,
                'lot': None,
                })
        return super(SemenExtractionDose, cls).copy(doses, default=default)

    @classmethod
    def delete(cls, doses):
        for dose in doses:
            if dose.state != 'draft':
                raise UserError(gettext('farm.semen_invalid_state_to_delete',
                        dose=dose.rec_name))
        return super(SemenExtractionDose, cls).delete(doses)

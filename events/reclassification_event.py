# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.exceptions import UserError
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Equal, Eval, Not
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.i18n import gettext

from .abstract_event import AbstractEvent, _STATES_VALIDATED_ADMIN, \
    _DEPENDS_VALIDATED_ADMIN


class ReclassficationEvent(AbstractEvent):
    '''Farm Reclassification Event'''
    __name__ = 'farm.reclassification.event'
    _table = 'farm_reclassification_event'

    reclassification_product = fields.Many2One(
        'product.product', "Reclassification Product", required=True,
        domain=[('id', 'in', Eval('valid_products'))],
        states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, depends=['animal_type', 'state', 'valid_products'])
    valid_products = fields.Function(fields.Many2Many(
        'product.product', None, None, 'Valid Products'),
        'on_change_with_valid_products')
    in_move = fields.Many2One(
        'stock.move', 'Input Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN, depends=_DEPENDS_VALIDATED_ADMIN)
    out_move = fields.Many2One(
        'stock.move', 'Output Stock Move',
        readonly=True, states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN)
    to_location = fields.Many2One('stock.location', 'Destination',
        required=True, states={
            'readonly': Not(Equal(Eval('state'), 'draft')),
            }, domain=[
            ('type', '=', 'storage'),
            ('silo', '=', False),
            ], depends=['state'])
    unit_digits = fields.Function(fields.Integer('Unit Digits'),
        'on_change_with_unit_digits')
    weight = fields.Numeric('Weight',
        digits=(16, Eval('unit_digits', 2)),
        depends=['unit_digits'])

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.animal.domain += [
            ('farm', '=', Eval('farm')),
            ('location.type', '=', 'storage'),
            ('type', '=', 'individual'),
            ]
        if 'farm' not in cls.animal.depends:
            cls.animal.depends.add('farm')

        cls._buttons.update({
            'draft': {
                'invisible': True,
                },
        })

    @fields.depends('animal')
    def on_change_with_valid_products(self, name=None):
        if self.animal and self.animal.specie:
            return [p.id for p in self.animal.specie.reclassification_products]
        return []

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Create the input and output stock moves.
        """
        pool = Pool()
        Move = pool.get('stock.move')
        FarmAnimalWeightRecord = pool.get('farm.animal.weight')

        for reclass_event in events:
            if reclass_event.in_move and reclass_event.out_move:
                raise UserError(gettext(
                    'farm.related_stock_moves',
                    event=reclass_event.id,
                    in_move=reclass_event.in_move.id,
                    out_move=reclass_event.out_move.id
                ))
            if (reclass_event.animal.lot.product ==
                    reclass_event.reclassification_product):
                raise UserError(gettext(
                    'farm.invalid_reclassification_product',
                    event=reclass_event.id,
                    product=reclass_event.reclassification_product
                ))

            new_in_move = reclass_event._get_event_input_move()
            new_in_move.save()
            Move.assign([new_in_move])
            Move.do([new_in_move])
            new_out_move = reclass_event._get_event_output_move()
            new_out_move.save()
            Move.assign([new_out_move])
            Move.do([new_out_move])
            if reclass_event.weight:
                weight_record = FarmAnimalWeightRecord()
                weight_record.animal = reclass_event.animal
                weight_record.weight = reclass_event.weight
                weight_record.timestamp = reclass_event.timestamp
                weight_record.save()
            reclass_event.in_move = new_in_move
            reclass_event.out_move = new_out_move
            reclass_event.save()

    @fields.depends('animal', 'valid_products', 'to_location')
    def on_change_animal(self):
        super().on_change_animal()
        if not self.animal:
            return
        self.to_location = self.animal.location

    @fields.depends('animal')
    def on_change_with_unit_digits(self, name=None):
        pool = Pool()
        UOM = pool.get('product.uom')
        if Pool().get('ir.model.data').get_id('product', 'uom_kilogram'):
            return UOM(Pool().get('ir.model.data').get_id(
                'product', 'uom_kilogram')).digits
        return 2

    def _get_new_lot_values(self):
        """
        Prepare values to create the new stock.lot for the reclassificated
        animal. It returns a dictionary with values to create stock.lot
        """
        pool = Pool()
        Lot = pool.get('stock.lot')
        if not self.animal:
            return {}
        product = self.reclassification_product
        lot_tmp = Lot(product=product)
        # TODO Improve the manage of animal/lot number, currently using
        # the animal number to create the new lot
        res = {
            'number': self.animal.number,
            'product': product.id,
            'animal_type': self.animal.type,
            'animal': self.animal,
            }
        return res

    def _get_event_input_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Company = pool.get('company.company')

        context = Transaction().context
        company = Company(context['company'])

        if self.animal_type == 'group':
            lot = self.animal_group.lot
        else:
            lot = self.animal.lot
        production_location = self.farm.production_location
        return Move(
            product=lot.product,
            uom=lot.product.default_uom,
            quantity=1,
            from_location=self.animal.location,
            to_location=production_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=company,
            lot=lot,
            origin=self,
            )

    def _get_event_output_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        Lot = pool.get('stock.lot')
        Company = pool.get('company.company')

        context = Transaction().context
        company = Company(context['company'])

        lots = Lot.create([self._get_new_lot_values()])
        if lots:
            lot, = lots
            lot.save()
        self.animal.lot = lot
        self.animal.save()
        production_location = self.farm.production_location

        return Move(
            product=lot.product,
            uom=lot.product.default_uom,
            quantity=1,
            from_location=production_location,
            to_location=self.to_location,
            planned_date=self.timestamp.date(),
            effective_date=self.timestamp.date(),
            company=company,
            lot=lot,
            unit_price=lot.product.cost_price,
            origin=self,
            )

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'reclassification_product': None,
                'to_location': None,
                'in_move': None,
                'out_move': None,
                'weight': None,
                })
        return super().copy(records, default=default)

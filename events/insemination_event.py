#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Bool, Equal, Eval, If
from trytond.pool import Pool
from trytond.transaction import Transaction

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED, _DEPENDS_VALIDATED, \
    _STATES_VALIDATED_ADMIN, _DEPENDS_VALIDATED_ADMIN

__all__ = ['InseminationEvent']


class InseminationEvent(AbstractEvent):
    '''Farm Insemination Event'''
    __name__ = 'farm.insemination.event'
    _table = 'farm_insemination_event'

    dose_bom = fields.Many2One('production.bom', 'Dose', domain=[
            ('semen_dose', '=', True),
            ('specie', '=', Eval('specie')),
            ], states=_STATES_WRITE_DRAFT,
        depends=_DEPENDS_WRITE_DRAFT + ['specie'])
    dose_product = fields.Function(fields.Many2One('product.product',
            'Dose Product', on_change_with=['dose_bom'], depends=['dose_bom']),
        'on_change_with_dose_product')
    # TODO: (no fer) add flag in context to restrict lots with stock in 'farm'
    # locations
    dose_lot = fields.Many2One('stock.lot', 'Dose Lot', domain=[
            If(Bool(Eval('dose_product')),
                ('product', '=', Eval('dose_product', 0)),
                ()),
            ], states=_STATES_WRITE_DRAFT,
        on_change_with=['farm', 'timestamp', 'dose_product'],
        depends=_DEPENDS_WRITE_DRAFT + ['dose_product'])
    female_cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])
    move = fields.Many2One('stock.move', 'Stock Move', readonly=True,
        states=_STATES_VALIDATED_ADMIN,
        depends=_DEPENDS_VALIDATED_ADMIN + ['dose_lot'])

    @classmethod
    def __setup__(cls):
        super(InseminationEvent, cls).__setup__()
        cls.animal.domain += [
            ('type', '=', 'female'),
            If(Equal(Eval('state'), 'draft'),
                ['OR', [
                        ('current_cycle', '=', None),
                    ], [
                        ('current_cycle.state', 'in', ('mated', 'unmated')),
                    ], ],
                []),
            ]
        cls._error_messages.update({
                'dose_not_in_farm': ('There isn\'t any unit of dose '
                    '"%(dose)s" selected in the insemination event '
                    '"%(event)s" in the farm "%(farm)s" at "%(timestamp)s".'),
                })

    @staticmethod
    def default_animal_type():
        return 'female'

    @staticmethod
    def valid_animal_types():
        return ['female']

    def get_rec_name(self, name):
        cycle = (self.female_cycle and self.female_cycle.sequence or
            self.animal.current_cycle and self.animal.current_cycle.sequence
            or None)
        if cycle:
            return "%s on cycle %s %s" % (self.animal.rec_name, cycle,
                self.timestamp)
        return super(InseminationEvent, self).get_rec_name(name)

    def on_change_with_dose_product(self, name=None):
        return (self.dose_bom and self.dose_bom.output_products and
            self.dose_bom.output_products[0].id or None)

    def on_change_with_dose_lot(self, name=None):
        Lot = Pool().get('stock.lot')

        if not self.dose_product:
            return
        with Transaction().set_context(
                locations=[self.farm.storage_location.id],
                stock_date_end=self.timestamp.date()):
            lots = Lot.search([
                ('product', '=', self.dose_product.id),
                ('quantity', '>', 0),
                ])
            if len(lots) == 1:
                return lots[0].id

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        - If the female has no open cycles start a new one.
        - Allow the event only if the cycle has state in ('mated','unmated')

        Creates and validates a production move with:
        In move:
        - What: Female Product + Lot (animal_id),
            From: Current Location, To: Production Location
        - What: Dose Product + (optional) Lot (dose_product_id, dose_lot_id),
            From: warehouse_id.lot_stock_id.id, To: Production Location
        Out move:
        - What: Female Product + Lot (female_id),
            From: Production Location, To: Current Location
        """
        pool = Pool()
        FemaleCycle = pool.get('farm.animal.female_cycle')
        Move = pool.get('stock.move')

        todo_moves = []
        for insemination_event in events:
            assert not insemination_event.move, ('Insemination Event "%s" '
                'already has the related stock move: "%s".' % (
                    insemination_event.id, insemination_event.move.id))
            if not insemination_event._check_dose_in_farm():
                cls.raise_user_error('dose_not_in_farm', {
                        'event': insemination_event.rec_name,
                        'dose': (insemination_event.dose_lot and
                            insemination_event.dose_lot.rec_name or
                            insemination_event.dose_product and
                            insemination_event.dose_product.rec_name or
                            insemination_event.specie.semen_product and
                            insemination_event.specie.semen_product.rec_name),
                        'farm': insemination_event.farm.rec_name,
                        'timestamp': insemination_event.timestamp,
                        })
            current_cycle = insemination_event.animal.current_cycle
            # It creates a new cycle if a diagnosis event has been done
            if (not current_cycle or current_cycle.farrowing_event or
                    current_cycle.abort_event):
                current_cycle = FemaleCycle(animal=insemination_event.animal)
                current_cycle.save()
                insemination_event.animal.current_cycle = current_cycle
                insemination_event.animal.save()
            insemination_event.female_cycle = current_cycle

            event_move = insemination_event._get_event_move()
            event_move.save()
            insemination_event.move = event_move
            todo_moves.append(event_move)

            insemination_event.save()
            current_cycle.update_state(insemination_event)
        Move.assign(todo_moves)
        Move.do(todo_moves)

    def _check_dose_in_farm(self):
        if self.dose_lot:
            with Transaction().set_context(
                    locations=[self.farm.storage_location.id],
                    stock_date_end=self.timestamp.date()):
                return self.dose_lot.quantity > 0
        product = self.dose_product or self.specie.semen_product
        if product.consumable:
            return True
        with Transaction().set_context(
                stock_date_end=self.timestamp.date(),
                locations=[self.farm.storage_location.id]):
            return product.quantity > 0

    def _get_event_move(self):
        pool = Pool()
        Move = pool.get('stock.move')
        context = Transaction().context

        if self.dose_bom:
            return Move(
                product=self.dose_product.id,
                uom=self.dose_product.default_uom.id,
                quantity=1,
                from_location=self.farm.storage_location.id,
                to_location=self.farm.production_location.id,
                planned_date=self.timestamp.date(),
                effective_date=self.timestamp.date(),
                company=context.get('company'),
                lot=self.dose_lot and self.dose_lot.id or None,
                origin=self,
                )
        else:
            return Move(
                product=self.specie.semen_product.id,
                uom=self.specie.semen_product.default_uom.id,
                quantity=1,
                from_location=self.farm.storage_location.id,
                to_location=self.farm.production_location.id,
                planned_date=self.timestamp.date(),
                effective_date=self.timestamp.date(),
                company=context.get('company'),
                origin=self,
                )

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'female_cycle': None,
                'move': None,
                })
        return super(InseminationEvent, cls).copy(records, default=default)

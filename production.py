#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Bool, Eval, Id, If, Not, Or
from trytond.pool import PoolMeta

__all__ = ['BOM']
__metaclass__ = PoolMeta


class BOM:
    __name__ = 'production.bom'

    semen_dose = fields.Boolean('Semen Dose')
    specie = fields.Many2One('farm.specie', 'Dose Specie', states={
            'required': Bool(Eval('semen_dose', 0)),
            'invisible': Not(Bool(Eval('semen_dose', 0))),
            }, depends=['semen_dose'])

    @classmethod
    def __setup__(cls):
        super(BOM, cls).__setup__()
        for field in (cls.inputs, cls.outputs):
            states = field.states or {}
            if 'required' in states:
                states['required'] = Or(Bool(Eval('semen_dose', 0)),
                    states['required'])
            else:
                states['required'] = Bool(Eval('semen_dose', 0))
            field.states = states
            field.depends.append('semen_dose')
        cls.outputs.size = If(Bool(Eval('semen_dose', 0)), 1,
                cls.outputs.size or -1)
        cls.outputs.domain.append(('uom', '=', Id('product', 'uom_unit')))
        cls._error_messages.update({
                'missing_semen_input': 'The Semen Dose BOM "%s" doesn\'t have '
                    'any input for the Specie\'s Semen Product.',
                })

    @classmethod
    def validate(cls, boms):
        super(BOM, cls).validate(boms)
        for bom in boms:
            bom.check_specie_semen_in_inputs()

    def check_specie_semen_in_inputs(self):
        if self.semen_dose:
            semen_product = self.specie.semen_product
            semen_input_lines = [i for i in self.inputs
                if i.product == semen_product]
            if not semen_input_lines:
                self.raise_user_error('missing_semen_input', (self.rec_name,))

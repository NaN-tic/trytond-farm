#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pyson import Bool, Eval, Id, If, Not, Or
from trytond.pool import PoolMeta
from trytond.exceptions import UserError
from trytond.i18n import gettext


class BOM(metaclass=PoolMeta):
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
        cls.outputs.domain.append(If(Bool(Eval('semen_dose', 0)),
                ('uom', '=', Id('product', 'uom_unit')), ()))

    @classmethod
    def validate(cls, boms):
        super(BOM, cls).validate(boms)
        for bom in boms:
            bom.check_specie_semen_in_inputs()

    def check_specie_semen_in_inputs(self):
        if not self.semen_dose:
            return
        if not self.check_specie_semen_in_inputs_recursive():
            raise UserError(gettext('farm.missing_semen_input',
                    bom=self.rec_name))

    def check_specie_semen_in_inputs_recursive(self):
        if self.semen_dose:
            semen_product = self.specie.semen_product
            for i in self.inputs:
                if i.product.boms:
                    for l in i.product.boms:
                        if l.bom.check_specie_semen_in_inputs_recursive():
                            return True
                elif i.product == semen_product:
                    return True
        return False

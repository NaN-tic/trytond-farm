#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['Template']


class Template(metaclass=PoolMeta):
    __name__ = 'product.template'

    farrowing_price = fields.Numeric('Farrowing Price', digits=(16, 4),
        help=('Unitary cost for farrowing events. It\'s only used when the '
            'product is a group product of a farm specie.'))
    weaning_price = fields.Numeric('Weaning Price', digits=(16, 4),
        help=('Unitary cost for weaning events. It\'s only used when the '
            'product is a group product of a farm specie.'))

#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelSQL
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Id, Not


class User(metaclass=PoolMeta):
    __name__ = 'res.user'

    farms = fields.Many2Many('res.user-stock.location', 'user', 'location',
        'Farms', domain=[
            ('type', '=', 'warehouse'),
            ],
        states={
            'readonly': Not(Eval('context', {}).get('groups', []).contains(
                Id('farm', 'group_farm_admin'))),
            },
        help="Farms to which this user is assigned. Determine animals that "
        "he/she can manage.")

    @classmethod
    def __setup__(cls):
        super(User, cls).__setup__()
        cls._preferences_fields.extend([
                'farms'])
        cls._context_fields.insert(0, 'farms')


class UserLocation(ModelSQL):
    'User - Location'
    __name__ = 'res.user-stock.location'
    user = fields.Many2One('res.user', 'User', ondelete='CASCADE',
        required=True)
    location = fields.Many2One('stock.location', 'Location',
        ondelete='CASCADE', required=True)

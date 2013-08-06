#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from .feed_abstract_event import FeedAbstractEvent

__all__ = ['MedicationEvent']


class MedicationEvent(FeedAbstractEvent):
    'Medication Event'
    __name__ = 'farm.medication.event'
    _table = 'farm_medication_event'

    @classmethod
    def __setup__(cls):
        super(MedicationEvent, cls).__setup__()
        cls._error_messages.update({
                'animal_not_in_location': ('The medication event of animal '
                    '"%(animal)s" is trying to move it from location '
                    '"%(location)s" but it isn\'t there at '
                    '"%(timestamp)s".'),
                'group_not_in_location': ('The medication event of group '
                    '"%(group)s" is trying to move animals from location '
                    '"%(location)s" but there isn\'t any there at '
                    '"%(timestamp)s".'),
                'not_enought_feed_lot': ('The medication event "%(event)s" is '
                    'trying to move %(quantity)s of lot "%(lot)s" from silo '
                    '"%(location)s" but there isn\'t enought quantity there '
                    'at "%(timestamp)s".'),
                'not_enought_feed_product': ('The medication event '
                    '"%(event)s" is trying to move %(quantity)s of product '
                    '"%(product)s" from silo "%(location)s" but there isn\'t '
                    'enought quantity there at "%(timestamp)s".'),
                })
        cls._sql_constraints += [
            ('quantity_positive', 'check ( quantity != 0.0 )',
                'In Medication Events, the quantity must be positive (greater '
                'or equal to 1)'),
            ]

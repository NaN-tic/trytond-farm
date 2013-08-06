#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, ModelSQL, Workflow
from trytond.pyson import Equal, Eval, If

from .abstract_event import AbstractEvent, _STATES_VALIDATED, \
    _DEPENDS_VALIDATED

__all__ = ['AbortEvent', 'AbortEventFemaleCycle']


class AbortEvent(AbstractEvent):
    '''Farm Abort Event'''
    __name__ = 'farm.abort.event'
    _table = 'farm_abort_event'

    female_cycle = fields.One2One('farm.abort.event-farm.animal.female_cycle',
        'event', 'cycle', string='Female Cycle', readonly=True, domain=[
            ('animal', '=', Eval('animal')),
            ], states=_STATES_VALIDATED,
        depends=_DEPENDS_VALIDATED + ['animal'])

    @classmethod
    def __setup__(cls):
        super(AbortEvent, cls).__setup__()
        cls.animal.domain += [
            ('type', '=', 'female'),
            ('current_cycle', '!=', False),
            If(Equal(Eval('state'), 'draft'),
                ('current_cycle.state', '=', 'pregnant'),
                ()),
            ]

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
        return super(AbortEvent, self).get_rec_name(name)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Updates the state of female
        """
        for diagnosis_event in events:
            diagnosis_event.female_cycle = diagnosis_event.animal.current_cycle
            diagnosis_event.save()
            diagnosis_event.female_cycle.update_state(diagnosis_event)

    @classmethod
    def copy(cls, records, default=None):
        if default is None:
            default = {}
        else:
            default = default.copy()
        default.update({
                'female_cycle': None,
                })
        return super(AbortEvent, cls).copy(records, default=default)


class AbortEventFemaleCycle(ModelSQL):
    "Abort Event - Female Cycle"
    __name__ = 'farm.abort.event-farm.animal.female_cycle'

    event = fields.Many2One('farm.abort.event', 'Abort Event', required=True,
        ondelete='RESTRICT')
    cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        required=True, ondelete='RESTRICT')

    @classmethod
    def __setup__(cls):
        super(AbortEventFemaleCycle, cls).__setup__()
        cls._sql_constraints += [
            ('event_unique', 'UNIQUE(event)',
                'The Abort Event must be unique.'),
            ('cycle_unique', 'UNIQUE(cycle)',
                'The Female Cycle must be unique.'),
            ]

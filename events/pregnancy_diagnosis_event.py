#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.model import fields, ModelView, Workflow
from trytond.pyson import Equal, Eval, If

from .abstract_event import AbstractEvent, _STATES_WRITE_DRAFT, \
    _DEPENDS_WRITE_DRAFT, _STATES_VALIDATED, _DEPENDS_VALIDATED

__all__ = ['PregnancyDiagnosisEvent']


class PregnancyDiagnosisEvent(AbstractEvent):
    '''Farm Pregnancy Diagnosis Event'''
    __name__ = 'farm.pregnancy_diagnosis.event'
    _table = 'farm__ency_diagnosis_event'

    result = fields.Selection([
            ('negative', 'Negative'),
            ('positive', 'Positive'),
            ('nonconclusive', 'Non conclusive'),
            ('not-pregnant', 'Observed not Pregnant'),
            ], 'Result', required=True,
        states=_STATES_WRITE_DRAFT, depends=_DEPENDS_WRITE_DRAFT)
    female_cycle = fields.Many2One('farm.animal.female_cycle', 'Female Cycle',
        readonly=True, domain=[('animal', '=', Eval('animal'))],
        states=_STATES_VALIDATED, depends=_DEPENDS_VALIDATED + ['animal'])

    @classmethod
    def __setup__(cls):
        super(PregnancyDiagnosisEvent, cls).__setup__()
        cls.animal.domain += [
            ('type', '=', 'female'),
            ('current_cycle', '!=', None),
            If(Equal(Eval('state'), 'draft'),
                ('current_cycle.state', 'in', ('mated', 'pregnant')),
                ()),
            ]

    @staticmethod
    def default_animal_type():
        return 'female'

    @staticmethod
    def default_result():
        return 'positive'

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
        return super(PregnancyDiagnosisEvent, self).get_rec_name(name)

    @classmethod
    @ModelView.button
    @Workflow.transition('validated')
    def validate_event(cls, events):
        """
        Set the 'female_cycle' of events and update the 'state' FemaleCycle and
        Female.
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
        return super(PregnancyDiagnosisEvent, cls).copy(records,
            default=default)

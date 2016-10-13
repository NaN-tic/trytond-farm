#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool

import animal
import animal_group
import events
import product
import production
import quality
import specie
import stock
import user


def register():
    Pool.register(
        specie.Specie,
        specie.SpecieModel,
        specie.SpecieFarmLine,
        specie.Breed,
        specie.UIMenu,
        specie.ActionActWindow,
        specie.ActionWizard,
        animal.Tag,
        events.removal_event.RemovalType,
        events.removal_event.RemovalReason,
        events.farrowing_event.FarrowingProblem,
        animal.Animal,
        animal.AnimalTag,
        animal.AnimalWeight,
        animal.Male,
        animal.FemaleCycle,
        animal.Female,
        animal.CreateFemaleStart,
        animal.CreateFemaleLine,
        animal_group.AnimalGroup,
        animal_group.AnimalGroupTag,
        animal_group.AnimalGroupWeight,
        stock.Location,
        stock.LocationSiloLocation,
        stock.LotAnimal,
        stock.LotAnimalGroup,
        stock.Lot,
        stock.LotCostLine,
        user.User,
        user.UserLocation,
        product.Template,
        events.event_order.EventOrder,
        events.abstract_event.AbstractEvent,
        events.move_event.MoveEvent,
        events.feed_inventory.FeedInventory,
        events.feed_inventory.FeedProvisionalInventory,
        events.feed_inventory.FeedInventoryLocation,
        events.feed_inventory.FeedAnimalLocationDate,
        events.feed_event.FeedEvent,
        events.medication_event.MedicationEvent,
        events.transformation_event.TransformationEvent,
        events.removal_event.RemovalEvent,
        events.semen_extraction_event.SemenExtractionEvent,
        events.semen_extraction_event.SemenExtractionEventQualityTest,
        events.semen_extraction_event.SemenExtractionDose,
        events.insemination_event.InseminationEvent,
        events.pregnancy_diagnosis_event.PregnancyDiagnosisEvent,
        events.abort_event.AbortEvent,
        events.abort_event.AbortEventFemaleCycle,
        events.farrowing_event.FarrowingEvent,
        events.farrowing_event.FarrowingEventFemaleCycle,
        events.farrowing_event.FarrowingEventAnimalGroup,
        events.foster_event.FosterEvent,
        events.weaning_event.WeaningEvent,
        events.weaning_event.WeaningEventFemaleCycle,
        stock.Move,
        production.BOM,
        quality.QualityTest,
        module='farm', type_='model')
    Pool.register(
        animal.CreateFemale,
        module='farm', type_='wizard')

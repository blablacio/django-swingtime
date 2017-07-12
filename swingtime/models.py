import warnings
import importlib
from datetime import datetime, date, timedelta
from dateutil import rrule

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation

from . import base_models
from .conf import swingtime_settings

__all__ = (
    'EventType',
    'Event',
    'Occurrence',
    'create_event'
)

if swingtime_settings.USE_CONCRETE_MODELS:

    class Note(models.Model):
        '''
        A generic model for adding simple, arbitrary notes to other models such as
        ``Event`` or ``Occurrence``.
        '''
        note = models.TextField(_('note'))
        created = models.DateTimeField(_('created'), auto_now_add=True)
        content_type = models.ForeignKey(
            ContentType,
            verbose_name=_('content type'),
            on_delete=models.CASCADE
        )
        object_id = models.PositiveIntegerField(_('object id'))
        content_object = GenericForeignKey('content_type', 'object_id')
        
        class Meta:
            verbose_name = _('note')
            verbose_name_plural = _('notes')

        def __str__(self):
            return self.note

    class EventType(base_models.EventTypeBase):
        class Meta:
            app_label = 'swingtime'


    class Event(base_models.EventBase):
        notes = GenericRelation(Note, verbose_name=_('notes'))

        class Meta:
            app_label = 'swingtime'


    class Occurrence(base_models.OccurrenceBase):
        class Meta:
            app_label = 'swingtime'
else:
    if swingtime_settings.EVENT_MODEL:
        package, model = swingtime_settings.EVENT_MODEL.rsplit('.', 1)
        Event = getattr(importlib.import_module(package), model)
    if swingtime_settings.EVENT_TYPE_MODEL:
        package, model = swingtime_settings.EVENT_TYPE_MODEL.rsplit('.', 1)
        EventType = getattr(importlib.import_module(package), model)

    if swingtime_settings.OCCURRENCE_MODEL:
        package, model = swingtime_settings.OCCURRENCE_MODEL.rsplit('.', 1)
        Occurrence = getattr(importlib.import_module(package), model)

create_event = base_models.event_creation_factory(Event, EventType)

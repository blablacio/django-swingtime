from __future__ import unicode_literals
from django.db import models

from swingtime import base_models as swingtime

class RRuleEventType(swingtime.EventTypeBase):
	pass

class RRuleEvent(swingtime.EventBase):
    event_type = models.ForeignKey(RRuleEventType, verbose_name='event type')


create_rrule_event = swingtime.event_creation_factory(RRuleEvent, RRuleEventType)

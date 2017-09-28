from datetime import datetime, date, timedelta
from dateutil import rrule

from django.db import models
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _

from .conf import swingtime_settings

__all__ = (
    'EventTypeBase',
    'EventBase',
    'OccurrenceBase',
    'event_creation_factory'
)


class EventTypeBase(models.Model):
    '''
    Simple ``Event`` classifcation.
    '''
    abbr = models.CharField(_('abbreviation'), max_length=10, unique=True)
    label = models.CharField(_('label'), max_length=50)

    class Meta:
        abstract = True
        verbose_name = _('event type')
        verbose_name_plural = _('event types')

    def __str__(self):
        return self.label


class EventBase(models.Model):
    '''
    Container model for general metadata and associated ``Occurrence`` entries.
    '''
    title = models.CharField(_('title'), max_length=100)
    description = models.CharField(_('description'), max_length=255)
    event_type = models.ForeignKey(swingtime_settings.EVENT_TYPE_MODEL)

    class Meta:
        abstract = True
        verbose_name = _('event')
        verbose_name_plural = _('events')
        ordering = ('title', )

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('swingtime-event', args=[str(self.id)])

    def add_occurrences(self, start_time, end_time, **rrule_params):
        '''
        Add one or more occurences to the event using a comparable API to 
        ``dateutil.rrule``. 
        
        If ``rrule_params`` does not contain a ``freq``, one will be defaulted
        to ``rrule.DAILY``.
        
        Because ``rrule.rrule`` returns an iterator that can essentially be
        unbounded, we need to slightly alter the expected behavior here in order
        to enforce a finite number of occurrence creation.
        
        If both ``count`` and ``until`` entries are missing from ``rrule_params``,
        only a single ``Occurrence`` instance will be created using the exact
        ``start_time`` and ``end_time`` values.
        '''
        count = rrule_params.get('count')
        until = rrule_params.get('until')
        if not (count or until):
            self.occurrence_set.create(start_time=start_time, end_time=end_time)
        else:
            rrule_params.setdefault('freq', rrule.DAILY)
            delta = end_time - start_time
            occurrences = []
            model_cls = self.occurrence_set.model
            for ev in rrule.rrule(dtstart=start_time, **rrule_params):
                occurrences.append(model_cls(
                    start_time=ev,
                    end_time=ev + delta,
                    event=self
                ))
            self.occurrence_set.bulk_create(occurrences)
        
    def upcoming_occurrences(self):
        '''
        Return all occurrences that are set to start on or after the current
        time.
        '''
        return self.occurrence_set.filter(start_time__gte=datetime.now())

    def next_occurrence(self):
        '''
        Return the single occurrence set to start on or after the current time
        if available, otherwise ``None``.
        '''
        upcoming = self.upcoming_occurrences()
        return upcoming[0] if upcoming else None

    def daily_occurrences(self, dt=None):
        '''
        Convenience method wrapping ``Occurrence.objects.daily_occurrences``.
        '''
        return _daily_occurrences(self.occurrence_set, dt)


def _daily_occurrences(obj, dt=None):
    dt = dt or datetime.now()
    start = datetime(dt.year, dt.month, dt.day)
    end = start.replace(hour=23, minute=59, second=59)
    return obj.filter(
        models.Q(start_time__gte=start, start_time__lte=end) |
        models.Q(end_time__gte=start, end_time__lte=end)     |
        models.Q(start_time__lt=start, end_time__gt=end)
    )


class OccurrenceManager(models.Manager):
    
    use_for_related_fields = True
    
    def daily_occurrences(self, dt=None, event=None):
        '''
        Returns a queryset of for instances that have any overlap with a 
        particular day.
        
        * ``dt`` may be either a datetime.datetime, datetime.date object, or
          ``None``. If ``None``, default to the current day.
        
        * ``event`` can be an ``Event`` instance for further filtering.
        '''
        qs = _daily_occurrences(self, dt)
        return qs.filter(event=event) if event else qs


class OccurrenceBase(models.Model):
    '''
    Represents the start end time for a specific occurrence of a master ``Event``
    object.
    '''
    event = models.ForeignKey(swingtime_settings.EVENT_MODEL, verbose_name=_('event'), editable=False)
    start_time = models.DateTimeField(_('start time'))
    end_time = models.DateTimeField(_('end time'))
    
    objects = OccurrenceManager()

    class Meta:
        abstract = True
        verbose_name = _('occurrence')
        verbose_name_plural = _('occurrences')
        ordering = ('start_time', 'end_time')

    def __str__(self):
        return u'{}: {}'.format(self.title, self.start_time.isoformat())

    def get_absolute_url(self):
        return reverse('swingtime-occurrence', args=[str(self.event.id), str(self.id)])

    def __lt__(self, other):
        return self.start_time < other.start_time

    @property
    def title(self):
        return self.event.title
        
    @property
    def event_type(self):
        return self.event.event_type


def event_creation_factory(event_cls, event_type_cls):
    
    def inner_create_event(
        title, 
        event_type,
        description='',
        start_time=None,
        end_time=None,
        **rrule_params
    ):
        '''
        Convenience function to create an ``Event``, optionally create an 
        ``EventType``, and associated ``Occurrence``s. ``Occurrence`` creation
        rules match those for ``Event.add_occurrences``.
         
        Returns the newly created ``Event`` instance.
        
        Parameters
        
        ``event_type``
            can be either an ``EventType`` object or 2-tuple of ``(abbreviation,label)``, 
            from which an ``EventType`` is either created or retrieved.
        
        ``start_time`` 
            will default to the current hour if ``None``
        
        ``end_time`` 
            will default to ``start_time`` plus swingtime_settings.DEFAULT_OCCURRENCE_DURATION
            hour if ``None``
        
        ``freq``, ``count``, ``rrule_params``
            follow the ``dateutils`` API (see http://labix.org/python-dateutil)
        
        '''
        
        if isinstance(event_type, tuple):
            event_type, created = event_type_cls.objects.get_or_create(
                abbr=event_type[0],
                label=event_type[1]
            )
        
        event = event_cls.objects.create(
            title=title, 
            description=description,
            event_type=event_type
        )

        start_time = start_time or datetime.now().replace(
            minute=0,
            second=0, 
            microsecond=0
        )
        
        end_time = end_time or (start_time + swingtime_settings.DEFAULT_OCCURRENCE_DURATION)
        event.add_occurrences(start_time, end_time, **rrule_params)
        return event

    return inner_create_event

import datetime
from geopy import distance as geopy_distance
from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _

from geo import fields as custom_fields
from geo import geocoding, misc
from geo.dateutil.relativedelta import relativedelta

class LocationManager(models.Manager):
	def by_proximity_to_location(self, origin_location, radius_miles=None):
		"""Returns a list of all self.model objects (excluding the origin_location)
			within radius_miles miles of the passed location if specified (otherwise
			returns all other objects), ordered by ascending proximity to it."""
		
		if radius_miles is not None:
			# It is assumed that 1 degree of latitude and longitude is equal to
			# 75 miles (this is actually overestimated)
			coord_set = {
				'latitude': {
					'minimum': origin_location.latitude - (radius_miles / 75),
					'maximum': origin_location.latitude + (radius_miles / 75),
				},
				'longitude': {
					'minimum': origin_location.longitude - (radius_miles / 75),
					'maximum': origin_location.longitude + (radius_miles / 75),
				},
			}
		
			results = self.model.objects.filter(latitude__range=(coord_set['latitude']['minimum'], coord_set['latitude']['maximum'])).filter(longitude__range=(coord_set['longitude']['minimum'], coord_set['longitude']['maximum']))
		else:
			results = self.model.objects.all()
		
		# Exclude any locations with exactly the same co-ordinates (GeoPy doesn't play nice with these)
		results = list(results.exclude(latitude__exact=origin_location.latitude).exclude(longitude__exact=origin_location.longitude))
		# And any that don't actually fall within the radius (accurately calculated)
		if radius_miles is not None:
			for result in results:
				if geopy_distance.distance((result.latitude, result.longitude), (origin_location.latitude, origin_location.longitude)).miles > radius_miles:
					results.remove(result)
		
		def proximity_cmp(current, previous, location=origin_location):
			return misc.base_cmp_by_proximity(current, previous, location.coords_tuple)
		
		results.sort(proximity_cmp)
		return results
	
	# Backwards-compatibility
	by_prox = by_proximity_to_location
	
	@property
	def public(self):
		"""Returns all self.model objects which have is_public set as True (convenience function)."""
		return self.model.objects.filter(is_public=True)
	
	@property
	def expired(self):
		"""Returns all self.model objects which have expired (convenience function)."""
		return self.model.objects.filter(refreshed__lte=(datetime.datetime.now() - relativedelta.relativedelta(**settings.MAX_LOCATION_CACHE_AGE)))
	
	def within_bounds(self, north_west, south_east):
		"""Returns a QuerySet of self.models within the supplied lat/long two-tuples (the northwest
		   and southwest-most corners bounding the segment of the earth in which to search)."""
		return self.model.objects.filter(latitude__range=(north_west[0], south_east[0])).filter(longitude__range=(north_west[1], south_east[1]))

class Location(models.Model):
	"""A Location on the earth."""
	query = models.CharField(_('Location'), max_length=250, blank=False, null=False, unique=True)
	friendly_name = models.CharField(max_length=250, blank=True, null=True, help_text=_('Use this to assign a friendly display-name to this location like \'Home\'.'))
	geocoded = models.BooleanField(default=True)
	result = custom_fields.PickledObjectField(blank=True, null=True, editable=False)
	latitude = models.FloatField(blank=True, null=False)
	longitude = models.FloatField(blank=True, null=False)
	refreshed = models.DateTimeField(editable=False, blank=True, null=False, default=datetime.datetime.now())
	extra = custom_fields.DictionaryField(_('A dictionary of additional information'), blank=True, null=True, editable=False)
	created = models.DateTimeField(editable=False, blank=True, null=True, default=datetime.datetime.now())
	is_public = models.BooleanField(default=True)
	# Manager
	objects = LocationManager()
	
	class Admin:
		list_display = ('__str__', 'latitude', 'longitude', 'created', 'refreshed')
		list_filter = ('created', 'refreshed')
	
	def save(self, *args, **kwargs):
		self.refresh()
		return super(Location, self).save(*args, **kwargs)
	
	# General
	def __unicode__(self):
		return unicode(self.name)
	
	def __getitem__(self, index):
		"""Gets either a latitude or longitude by indexing the coords_tuple."""
		return self.coords_tuple[index]
	
	def get_geocoder(self):
		"""Returns an instantiated geocoder for this object. Make sure you have settings.DEFAULT_GEOCODER set correctly."""
		return geocoding.SHORT_NAME_MAPPINGS[settings.DEFAULT_GEOCODER]
	
	@property
	def coords(self):
		if hasattr(self.result, 'coords'):
			return self.result.coords
		else:
			return geocoding.Coordinates(float(self.latitude or 0), float(self.longitude or 0))
	
	@property
	def coords_tuple(self):
		if not hasattr(self.result, 'coords'):
			return (self.latitude, self.longitude)
		else:
			return tuple(self.result.coords)
	
	@property
	def coords_dict(self):
		if not hasattr(self.result, 'coords'):
			return {u'latitude': self.latitude, u'longitude': self.longitude}
		else:
			return {u'longitude': self.result.coords.latitude, u'longitude': self.result.coords.longitude}
	
	@property
	def name(self):
		return self.friendly_name or self.query
	
	# Caching
	@property
	def expires(self):
		"""Returns the datetime when this object will be deemed to have expired."""
		return self.refreshed + relativedelta(**settings.MAX_LOCATION_CACHE_AGE)
	
	@property
	def expired(self):
		"""Returns boolean as to whether this object has 'expired'. Always returns False if not geocoded."""
		if not self.geocoded:
			# This location hasn't been geocoded
			return False
		elif datetime.datetime.now() >= self.expires:
			# The location has expired
			return True
		elif not (self.result and hasattr(self.result, 'coords')):
			# The location hasn't yet been geocoded, but it should have been
			return True
		else:
			# The location hasn't expired
			return False
	
	def force_refresh(self):
		"""Forces a refresh of the geo-mapping by re-geocoding (if the location is geocoded)."""
		if self.geocoded:
			self.result = self.get_geocoder()(self).geocode()
			self.latitude, self.longitude = tuple(self.result.coords)[:2]
			self.refreshed = datetime.datetime.now()
		return self
	
	def refresh(self):
		"""Refreshes the geo-mapping it has already expired."""
		if self.expired:
			self.force_refresh()
		return self
	
	# Conveniences
	def distance_between(self, other_location, units='miles'):
		"""Calculates the distance between this Location object and another Location object.
		   units should be a string containing the unit of measurement (default: miles) you would like
		   the result returned in (kilometers, miles, feet or nautical)."""
		if self.coords_tuple == other_location.coords_tuple:
			return 0
		dist_obj = geopy_distance.distance(self.coords_tuple, other_location.coords_tuple)
		return getattr(dist_obj, str(units))
	
	def within_bounds(self, north_west, south_east):
		"""Given 2x two-tuples containing lat/long pairs (the northwest and southeast corners
		   bounding a segment of the earth), returns Boolean as to whether this Location falls
		   inside the area."""
		if (north_west[0] > self.latitude > south_east[0]) and (north_west[1] < self.longitude < south_east[1]):
			return True
		else:
			return False

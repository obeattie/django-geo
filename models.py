from django.db import models
import datetime
try:
	import cPickle as pickle
except ImportError:
	import pickle
# Imports for Django stuff
from django.db import models
from django.utils.encoding import smart_unicode
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings
# Imports for geo stuff
from wt.generic.geo import misc as geo_misc
from wt.generic.geo import fields as custom_fields
from wt.generic.geo.dateutil import relativedelta
from geopy import geocoders as geopy_geocoders, distance as geopy_distance

class LocationManager(models.Manager):
	def by_proximity_to_location(self, origin_location, radius_miles=None):
		"""Returns a list of all Location objects (excluding the origin_location)
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
		
			results = Location.objects.filter(latitude__range=(coord_set['latitude']['minimum'], coord_set['latitude']['maximum'])).filter(longitude__range=(coord_set['longitude']['minimum'], coord_set['longitude']['maximum']))
		else:
			results = Location.objects.all()
		
		# Exclude any locations with exactly the same co-ordinates (GeoPy doesn't play nice with these)
		results = list(results.exclude(latitude__exact=origin_location.latitude).exclude(longitude__exact=origin_location.longitude))
		# And any that don't actually fall within the radius (accurately calculated)
		if radius_miles is not None:
			for result in results:
				if geopy_distance.distance((result.latitude, result.longitude), (origin_location.latitude, origin_location.longitude)).miles > radius_miles:
					results.remove(result)
		
		def proximity_cmp(current, previous, location=origin_location):
			return geo_misc.base_cmp_by_proximity(current, previous, location.coords_tuple)
		
		results.sort(proximity_cmp)
		return results
	
	# Backwards-compatibility
	by_prox = by_proximity_to_location
	
	@property
	def public(self):
		"""Returns all Location objects which have is_public set as True (convenience function)."""
		return Location.objects.filter(is_public=True)
	
	@property
	def expired(self):
		"""Returns all Location objects which have expired (convenience function)."""
		return Location.objects.filter(refreshed__lte=(datetime.datetime.now() - relativedelta.relativedelta(**settings.MAX_LOCATION_CACHE_AGE)))
	
	def within_bounds(self, north_west, south_east):
		"""Returns a QuerySet of Locations within the supplied lat/long two-tuples (the northwest
		   and southwest-most corners bounding the segment of the earth in which to search)."""
		return Location.objects.filter(latitude__range=(north_west[0], south_east[0])).filter(longitude__range=(north_west[1], south_east[1]))

class Location(models.Model):
	"""Defines a location somewhere on the globe (presumably! [somewhere with two-
	   dimensional space defined by latitude/longitude anyway!]). All that needs 
	   to be entered is a query, which is what will be geocoded (for example 
	   'Penzance, UK'), and everything else will be taken care of automagically. 
	   Note that if the object is to be used before it is saved, then
	   refresh_if_needed needs to be called."""
	
	query = models.TextField('Location', blank=False, null=False) # TextField in case it's over 250 characters
	friendly_name = models.CharField(max_length=250, blank=True, null=True, help_text='Use this to assign a friendly display-name to this location like \'Home\'.')
	geocoder = custom_fields.PickledObjectField(blank=True, null=False)
	latitude = models.FloatField(blank=True, null=False)
	longitude = models.FloatField(blank=True, null=False)
	refreshed = models.DateTimeField(editable=False, blank=True, null=False)
	created = models.DateTimeField(editable=False, blank=True, null=True)
	is_public = models.BooleanField(default=True)
	# Manager
	objects = LocationManager()
	
	class Admin:
		list_display = ('__str__', 'latitude', 'longitude', 'created', 'refreshed')
		list_filter = ('created', 'refreshed')
	
	@property
	def coords(self):
		"""A dictionary of latitude and longitude."""
		return {
				'latitude': self.latitude,
				'longitude': self.longitude,
			}
	
	@property
	def name(self):
		"""If it exists, returns the friendly_name, otherwise returns the query."""
		return self.friendly_name or self.query
	
	@property
	def coords_tuple(self):
		"""A two-tuple of latitude and longitude."""
		return (self.latitude, self.longitude)
	
	def __str__(self):
		return self.name
	
	def save(self):
		if not self.created:
			self.created = datetime.datetime.now()
		if not self.geocoder:
			self.geocoder = getattr(geopy_geocoders, settings.DEFAULT_GEOCODER)
		self.refresh_if_needed(save=False)
		super(Location, self).save()
	
	def refresh(self, save=True):
		"""Refreshes the geo-mapping."""
		try:
			geo_keys = settings.GEOCODING_KEYS
		except AttributeError:
			geo_keys = {}
		if self.geocoder.__name__ in geo_keys.keys():
			geocoder = self.geocoder(geo_keys[self.geocoder.__name__])
		else:
			geocoder = self.geocoder()
		try:
			place, (self.latitude, self.longitude) = geocoder.geocode(self.query)
			self.refreshed = datetime.datetime.now()
			if save:
				self.save()
		except:
			raise geo_misc.GeocodingError, 'The location \'%s\' could not be geocoded.' % self.query
		return True
	
	def refresh_if_needed(self, *args, **kwargs):
		"""Refreshes the geo-mapping if it has already expired, or we don't have any data
		   already"""
		if self.expired or not (self.latitude or self.longitude):
			return self.refresh(*args, **kwargs)
		else:
			return False
	
	@property
	def expired(self):
		if datetime.datetime.now() > (self.created + relativedelta.relativedelta(**settings.MAX_LOCATION_CACHE_AGE)):
			return True
		return False
	
	def distance_between(self, other_location, units='miles'):
		"""Calculates the distance between this Location object and another Location object.
		   units should be a string containing the unit of measurement (default: miles) you
		   would like the result returned in (kilometers, miles, feet or nautical)."""
		
		if self.coords_tuple == other_location.coords_tuple:
			return 0
		dist_obj = geopy_distance.distance(self.coords_tuple, other_location.coords_tuple)
		return getattr(dist_obj, str(units))
	
	def within_bounds(self, north_west, south_east):
		"""Given 2x two-tuples containing lat/long pairs (the northwest and southeast corners
		   bounding a segment of the earth), returns Boolean as to whether this Location falls
		   inside the area."""
		if (north_west[0] < self.latitude < south_east[0]) and (north_west[1] < self.longitude < south_east[1]):
			return True
		else:
			return False

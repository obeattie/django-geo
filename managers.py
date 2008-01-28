import datetime
from geopy import distance as geopy_distance
from django.db import models
from django.conf import settings

from geo import misc
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
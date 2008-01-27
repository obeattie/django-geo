import re, urllib, urllib2
from elementtree import ElementTree

from django.conf import settings

from geo.misc import yahoo_precision_to_google_zoom_mappings, GeocodingError

NAMESPACE_RE = re.compile(r'^\{.+\}') # To remove xml namespace declarations from tag names, as they are unhelpful here.

class XMLElement(object):
	"""Object for storing basic XML data (represents an element in an XML document). Content and attributes can
	   be stored."""
	def __init__(self, tag='', text='', attrs={}, *args, **kwargs):
		self.text = text
		self.attrs = attrs
		return super(XMLElement, self).__init__(*args, **kwargs)
	
	def __unicode__(self):
		return unicode(self.text)
	
	def __str__(self):
		return str(self.text)
	
	def __repr__(self):
		return '<XMLElement: %s: %s>' % (self.tag, self.text)
	
	def __int__(self):
		return int(self.text)
	
	def __float__(self):
		return float(self.text)

class Coordinates(object):
	"""Basic object for storing co-ordinate data."""
	def __init__(self, latitude=0.0, longitude=0.0, elevation=0.0, granularity=0, *args, **kwargs):
		self.latitude, self.longitude, self.elevation, self.granularity = float(latitude), float(longitude), float(elevation), int(granularity)
		return super(Coordinates, self).__init__(*args, **kwargs)
	
	def __unicode__(self):
		return 'Coordinate (%s, %s, %s)' % (self.latitude, self.longitude, self.elevation)
	
	def __repr__(self):
		return '<Coordinates object for (%s, %s, %s)>' % (self.latitude, self.longitude, self.elevation)
	
	def __iter__(self):
		return iter((self.latitude, self.longitude, self.elevation))
	
	def __getitem__(self, index):
		return tuple(self)[index]

class XMLResponse(object):
	"""Object for storing a simple representation of an XML response (not as complex as an ElementTree,
	   has no concept of nesting)."""
	def __init__(self, *args, **kwargs):
		self.raw = ''
		self.coords = Coordinates()
		self.data = {}
		return super(XMLResponse, self).__init__(*args, **kwargs)
	
	def __setattr__(self, name, value):
		if not hasattr(self, name):
			try:
				self.data[name] = value
				return
			except:
				return super(XMLResponse, self).__setattr__(name, value)
		else:
			return super(XMLResponse, self).__setattr__(name, value)

class GeocodingResult(object):
	"""Class to store geocoding response objects."""
	def __init__(self, *args, **kwargs):
		self.response = XMLResponse()
		self.query = ''
		self.coords = Coordinates()
		return super(GeocodingResult, self).__init__(*args, **kwargs)
	
	def __repr__(self):
		return '<GeocodingResult instance for \'%s\'>' % self.query

class XMLGeocoder(object):
	short_name = ''
	key_key = ''
	geocoder_url = ''
	query_key = ''
	default_args = {}
	default_inst_args = {
		'result': GeocodingResult(),
		'geocoder_params': {},
	}
	
	def __init__(self, location, *args, **kwargs):
		if self.__class__.__name__ is 'XMLGeocoder':
			raise NotImplementedError('You cannot instantiate XMLGeocoder directly; use on of its subclasses instead.')
		# Set some instance attributes
		self.result = GeocodingResult()
		self.geocoder_params = {unicode(self.query_key): location.name}
		self.result.query = self.geocoder_params[self.query_key]
		# Return
		return super(XMLGeocoder, self).__init__(self, *args, **kwargs)
	
	@property
	def parameters(self):
		params = self.geocoder_params
		if not self.key_key in params:
			params.update(self.key)
		for arg in self.default_args:
			if not arg in params:
				params.update({arg: self.default_args[arg]})
		return params
	
	@property
	def url(self):
		"""Returns the URL to preform geocoding."""
		return u'%s?%s' % (unicode(self.geocoder_url), urllib.urlencode(self.parameters))
	
	@property
	def key(self):
		"""The API key to use with this geocoder. Returns a dictionary that can be added to the geocoder
		   parameter."""
		try:
			return {self.key_key: unicode(settings.GEOCODING_KEYS[self.short_name])}
		except (AttributeError, KeyError):
			# If the GEOCODING_KEYS setting isn't defined or the key isn't in there, return an
			# empty dict.
			return {}
	
	def geocode(self):
		"""Let's get geocoding!"""
		self.result.response.raw = urllib2.urlopen(self.url).read()
		et = ElementTree.fromstring(self.result.response.raw)
		for el in et.getiterator():
			xml_element = XMLElement()
			# Add the element content to the xml_element
			xml_element.tag = NAMESPACE_RE.sub('', unicode(el.tag).lower().strip())
			xml_element.text = unicode(el.text).strip()
			xml_element.attrs = el.attrib
			self.result.response.data[xml_element.tag] = xml_element
		try:
			self.result = self.additional_processing(self.result)
		except:
			raise GeocodingError('The location could not be geocoded.')
		return self.result
	
	def additional_processing(self, result):
		"""Performs any additional processing that needs to be done on the GeocodingResult object passed
		   -- returns the modified object. Also should raise a GeocodingError if something isn't right."""
		return result
	
class YahooGeocoder(XMLGeocoder):
	"""Yahoo! Maps' geocoder. Requires a 'yahoo' key in settings.GEOCODING_KEYS to work correctly."""
	geocoder_url = u'http://local.yahooapis.com/MapsService/V1/geocode'
	short_name = u'yahoo'
	key_key = u'appid'
	query_key = u'location'
	
	def additional_processing(self, result):
		result.coords = Coordinates(result.response.data['latitude'].text, result.response.data['longitude'].text, 0, yahoo_precision_to_google_zoom_mappings[result.response.data['result'].attrs['precision']])
		return result

class GoogleGeocoder(XMLGeocoder):
	"""Google Maps' geocoder. Requires a 'google' key in settings.GEOCODING_KEYS to work correctly."""
	geocoder_url = u'http://maps.google.com/maps/geo'
	short_name = u'google',
	key_key = u'key'
	query_key = u'q'
	default_args = {u'output': u'xml'}
	
	def additional_processing(self, result):
		result.coords = Coordinates(*result.response.data['coordinates'].text.split(','))
		return result

class GeoNamesGeocoder(XMLGeocoder):
	"""GeoNames' geocoder. Doesn't require an API key."""
	geocoder_url = u'http://ws.geonames.org/search'
	short_name = u'geonames'
	query_key = u'q'
	default_args = {u'maxRows': 1}
	
	def additional_processing(self, result):
		result.coords = Coordinates(result.response.data['lat'], result.response.data['lng'])
		return result

SHORT_NAME_MAPPINGS = {
	'yahoo': YahooGeocoder,
	'google': GoogleGeocoder,
	'geonames': GeoNamesGeocoder,
}

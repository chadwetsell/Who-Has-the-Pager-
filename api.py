import webapp2
import os
import jinja2
import sys
import urllib2
from xml.dom import minidom
from string import letters
from google.appengine.ext import db
import json
import csv

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_environment = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

fb_key = db.Key.from_path('FBAPI', 'fbs')


GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x400&sensor=false&"
def gmaps_img(points):
    markers = "&".join('markers=%s,%s' % (p.lat, p.lon) for p in points)
    return GMAPS_URL + markers

CSV = csv.reader(open('pager.csv'))

fb_url = "https://graph.facebook.com/"
def get_api(id):
	url = "https://graph.facebook.com/" + id
	return json.loads(urllib2.urlopen(url).read())
	
class FB(db.Model):
	fb_id = db.StringProperty(required = True)
	name = db.StringProperty()
	first_name = db.StringProperty()
	last_name = db.StringProperty()
	username = db.StringProperty()
	gender = db.StringProperty()
	locale = db.StringProperty()
	created = db.DateTimeProperty(auto_now_add = True)
	

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_environment.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))
        
class FbHandler(Handler):
	def render_front(self, error = '', fb_id = ''):
		fbs = db.GqlQuery("SELECT * "
						   "From FB "
						   "WHERE ANCESTOR is :1 "
						   "ORDER BY created DESC ",
						   fb_key)
		fbs = list(fbs)	
		img_url = None
		
		self.render('api.html', fb_id = fb_id,  
		 						  error = error,
		 						  fbs = fbs)
		for e in CSV:
                    print e[0]


	def get(self):
		return self.render_front()
		
	def post(self):
		fb_id = self.request.get('fb_id')
		
		if fb_id:
			fb = get_api(fb_id)
			p = FB(parent = fb_key, fb_id = fb_id)
			p.name = fb['name']
			p.first_name = fb['first_name']
			p.last_name = fb['last_name']
			p.username = fb['username']
			p.put()
			
			self.redirect('/api/api')
		else:
			error = "Need a FB User ID!"
			self.render_front(error = error, fb_id = fb_id)


app = webapp2.WSGIApplication([('/test/api', FbHandler)],
                              debug=True)

# user log-in/provide ID
# load fb json into dict
# store fb vals in db
# post vals on page
#
#
#
#
#
#

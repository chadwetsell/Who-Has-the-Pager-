import os
import re
import random
import hashlib
import hmac
from string import letters
from datetime import datetime, timedelta
import csv
import datetime

import webapp2
import jinja2

from google.appengine.api import memcache
from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'pager')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                               autoescape = True)

secret = 'chadillac'

def render_str(template, **params):
    t = jinja_env.get_template(template)
    return t.render(params)

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

class BlogHandler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        params['user'] = self.user
        return render_str(template, **params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))


#
# User Functions
#

def make_salt(length = 5):
    return ''.join(random.choice(letters) for x in xrange(length))

def make_pw_hash(name, pw, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pw + salt).hexdigest()
    return '%s,%s' % (salt, h)

def valid_pw(name, password, h):
    salt = h.split(',')[0]
    return h == make_pw_hash(name, password, salt)

def users_key(group = 'default'):
    return db.Key.from_path('users', group)

class User(db.Model):
    name = db.StringProperty(required = True)
    pw_hash = db.StringProperty(required = True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return User.get_by_id(uid, parent = users_key())

    @classmethod
    def by_name(cls, name):
        u = User.all().filter('name =', name).get()
        return u

    @classmethod
    def register(cls, name, pw, email = None):
        pw_hash = make_pw_hash(name, pw)
        return User(parent = users_key(),
                    name = name,
                    pw_hash = pw_hash,
                    email = email)

    @classmethod
    def login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pw(name, pw, u.pw_hash):
            return u

EMAIL_RE  = re.compile(r'^[\S]+@[\S]+\.[\S]+$')
def valid_email(email):
    return not email or EMAIL_RE.match(email)

class Login(BlogHandler):
    def get(self):
        self.render('login-form.html')

    def post(self):
        self.username = self.request.get('username')
        username = self.username
        
        domain = username[-15:]
        if domain == '@datasphere.com':
            self.user = username[:-16]
            us = User.register(self.username, self.user)
            us.put()

            self.login(us)
            self.redirect('/')
        else:
            msg = 'Invalid login'
            self.render('login-form.html', error = msg)

class Logout(BlogHandler):
    def get(self):
        self.logout()
        self.redirect('/')


#
# Pager App Functions
#

#Setup for the Database
class Pager(db.Model):
    p1 = db.TextProperty()
    p2 = db.TextProperty()
    week = db.IntegerProperty(required = True)
    monday = db.DateProperty(required = True)
    last_modified = db.DateTimeProperty(auto_now = True)
    
    @classmethod
    def by_id(cls, uid):
        return Pager.get_by_id(uid, parent = users_key())

    @classmethod
    def by_week(cls, week):
        u = Pager.all().filter('week =', week).get()
        return u



#Imports the Pager signup CSV
CSV = csv.reader(open('pager.csv'))

#temp Dictionary for putting the CSV into the DB
CACHE = {}

#Temp f(x) to find the first Monday of a year.
def findMonday():
    for x in range(1,7):
        d = datetime.date(2012, 1, x)
        tup = datetime.date.timetuple(d)
        if tup.tm_wday == 0:
            return d

#Builds a Dictionary of the P1/P2 signups by Mondays
def csv2date():
    for e in CSV:
        if not e[0] == 'Title':
            monday = e[1]
            slash = monday.find('/')
            slash2 = monday.find('/', slash + 1)
            month = int(monday[:slash])
            day = int(monday[slash + 1:slash2])
            year = int(monday[-4:])
            Date = datetime.date(year, month, day)
            for k in CACHE:
            	#CACHE[k]['p1'] = CACHE[k]['p2'] = None
            	if CACHE[k]['monday'] == Date:
            		week = k
            if '1' in e[0]:
                CACHE[week]['p1'] = e[0]
            if '2' in e[0]:
                CACHE[week]['p2'] = e[0]


#Sets up the Database of Weeks/Mondays/P1/P2 (using the Dictionary)
def initDB():
    week = 0
    monday = datetime.date(2011, 12, 19)
    while week < 60:
        CACHE[week] = {'monday': monday, 'p1': None, 'p2': None}
        week += 1
        monday += datetime.timedelta(7)
    csv2date()
    for k in CACHE:
    	week = k
    	monday = CACHE[k]['monday']
    	p1 = CACHE[k]['p1']
    	p2 = CACHE[k]['p2']
    	p = Pager(week = week, monday = monday, p1 = p1, p2 = p2)
    	p.put()

#Returns the Monday for any given date.
def findMonday(date):
    of = date.weekday()
    monday = date - datetime.timedelta(of)
    return monday

#Returns the Week #1 for a given Monday.
def findWeek(date):
	for k in CACHE:
		print 'cache', CACHE[k]
		if CACHE[k]['monday'] == date:
			return k

#Returns the P1 and P2 person for a given Monday.
def findPeeps(date):
	entries = Pager.gql("where monday = :1", date)
	for entry in entries:
		return entry.p1, entry.p2	

#Point bad links back to the main page
class ErrorPage(BlogHandler):
	def get(self):	
		self.redirect('/')  

#Loads the front page ("this week")
class MainPage(BlogHandler):
	def get(self):
		if not self.user:
			self.redirect("/login")
		else:
			Today = datetime.date.today()
			Monday = findMonday(Today)
			posts = Pager.all().order('-last_modified').fetch(limit = 1)
			if not posts:
				initDB()

			P1, P2 = findPeeps(Monday)
			
			self.render("main.html", Monday = Monday, P1 = P1, P2 = P2)
			return

#Loads the "Next Week" page
class Next(BlogHandler):
	def get(self):
		if not self.user:
			self.redirect("/login")
		else:
			Today = datetime.date.today()
			Monday = findMonday(Today + datetime.timedelta(7))
			P1, P2 = findPeeps(Monday)
			self.render("next.html", Monday = Monday, P1 = P1, P2 = P2)
			return

#Loads the "Previous Week" page
class Previous(BlogHandler):
	def get(self):
		if not self.user:
			self.redirect("/login")
		else:
			Today = datetime.date.today()
			Monday = findMonday(Today - datetime.timedelta(7))
			P1, P2 = findPeeps(Monday)
			self.render("previous.html", Monday = Monday, P1 = P1, P2 = P2)
			return



PAGE_RE = r'(/(?:[a-zA-Z0-9_-]+/?)*)'
app = webapp2.WSGIApplication([('/', MainPage),
							   ('/login', Login),
                               ('/logout', Logout),
                               ('/lastweek', Previous),
			       			   ('/nextweek', Next)
			       			   #('/' + PAGE_RE, ErrorPage)
			       			   ],
                              debug=True)

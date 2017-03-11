import cgi, os, urllib, time, datetime
import wsgiref.handlers
from google.appengine.ext import webapp

from deewhy import *

def main():
	application = webapp.WSGIApplication([
		('(/' + PageTypes.manage + '/' + PageTypes.player  + ')/(.*)', PlayerManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.protected  + ')/(.*)', ProtectedManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.ground  + ')/(.*)', GroundManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.draw    + ')/(.*)', DrawManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.results + ')/(.*)', ResultsManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.beer    + ')/(.*)', BeerManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.shirts  + ')/(.*)', ShirtsManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.mailer  + ')/(.*)', MailerManagePage),
		('(/' + PageTypes.manage + '/' + PageTypes.export  + ')/(.*)', ExportManagePage),
		('(/' + PageTypes.manage + ')/(.*)', PlayerManagePage),
		('(/' + PageTypes.manage + ')(.*)', PlayerManagePage),
	])
	wsgiref.handlers.CGIHandler().run(application)

if __name__ == "__main__":
	main()

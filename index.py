import cgi, os, urllib, time, datetime
import wsgiref.handlers
from google.appengine.ext import webapp
import logging

from deewhy import *

from google.appengine.dist import use_library
use_library('django', '0.96')

def real_main():
	application = webapp.WSGIApplication([
		('/(' + PageTypes.player + ')/(.*)', PlayerPage),
		('/(' + PageTypes.results + ')/(.*)', ResultsPage),
		('/(' + PageTypes.scorers + ')/(.*)', ScorersPage),
		('/(' + PageTypes.beer + ')/(.*)', BeerPage),
		('/(' + PageTypes.shirts + ')/(.*)', ShirtsPage),
		('/(' + PageTypes.table + ')/(.*)', TablePage),
		('/(' + PageTypes.protected + ')/(.*)', ProtectedPage),
		('/(.*)', PlayerPage),
		('(.*)', PlayerPage),
	])
	wsgiref.handlers.CGIHandler().run(application)

def profile_main():
 # This is the main function for profiling 
 # We've renamed our original main() above to real_main()
 import cProfile, pstats, StringIO
 prof = cProfile.Profile()
 prof = prof.runctx("real_main()", globals(), locals())
 stream = StringIO.StringIO()
 stats = pstats.Stats(prof, stream=stream)
 stats.sort_stats("time")  # Or cumulative
 stats.print_stats(80)  # 80 = how many to print
 # The rest is optional.
 # stats.print_callees()
 # stats.print_callers()
 logging.info("Profile data:\n%s", stream.getvalue())

if __name__ == "__main__":
	real_main()
	#profile_main()

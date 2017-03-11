import urllib
import datetime
from google.appengine.ext.db import *

# Most important commonality is that every model has a static "get_key" method to generate its datastore key.

class Player(Model):
	"""All the player information, obviously!"""
	@staticmethod
	def get_key(first, last):
		try:
			key = first + last
			key = key.replace('\'', '')
			key = key.replace('\"', '')
			return key
		except:
			pass

	def get_short_name(self):
		name = self.nick_name
		if name is None or len(name) == 0:
			name = self.first_name
		return name

	db_key = StringProperty(required=True)
	first_name = StringProperty(required=True)
	last_name = StringProperty(required=True)
	nick_name = StringProperty(required=False)
	email = StringProperty(required=True)
	phone = StringProperty(required=False)
	registration = StringProperty(required=False)
	shirt = StringProperty(required=False)

class TeamList(Model):
	"""All the players for a given year"""

	@staticmethod
	def get_key(player, year):
		try:
			return 'tl_%s-%d' % (player, int(year))
		except:
			return ''

	player = ReferenceProperty(Player, required=True, collection_name='year_list')
	year = IntegerProperty(required=True)
	
class Ground(Model):
	"""A playing ground"""
	
	@staticmethod
	def get_key():
		try:
			return 'g_' + `Query(Ground).count() + 1`
		except:
			return ''

	db_key = StringProperty(required=True)
	name = StringProperty(required=True)
	address = StringProperty(required=True)
	map = LinkProperty(required=True)
	
class Round(Model):
	"""Who, what, when, where for a round"""
	
	@staticmethod
	def get_key(round, year):
		try:
			return 'r_' + `int(year)` + '-' + `int(round)`
		except:
			return ''

	def get_player_count(self):
		full_count = TeamList.gql('WHERE year = :1', self.year).count()
		for a in self.availability_set:
			if not a.playing:
				full_count -= 1
		return full_count
		
	def get_away_set(self):
		away_set = []
		for a in self.availability_set:
			if not a.playing:
				away_set.append(a.player.get_short_name())
		return away_set

	def get_away_str(self):
		away_set = self.get_away_set()
		if len(away_set) == 0:
			return 'Nobody'
		else:
			return ', '.join(away_set)
			
	def is_current(self):
		round_time = datetime.datetime(self.date.year, self.date.month, self.date.day, self.time.hour, self.time.minute)
		# Ugly hack to get in AEST, but site is only active in winter and only needs to be an approximation.
		curr_time = datetime.datetime.utcnow() + datetime.timedelta(hours=10)
		delta = curr_time - round_time
		return delta < datetime.timedelta(hours=12) 

	year = IntegerProperty(required=True)
	num = IntegerProperty(required=True)
	caption = StringProperty(required=False)
	date = DateProperty(required=True)
	time = TimeProperty(required=False)
	opponent = StringProperty(required=False)
	homeaway = StringProperty(required=False)
	location = ReferenceProperty(Ground, required=False, collection_name='round_list')
	
class Beer(Model):
	"""Link between a player and a round for supplying beer"""

	UNKNOWN = "unknown"
	NOBODY = "nobody"
	OTHERS = [UNKNOWN, NOBODY]
	OTHERS_FRIENDLY = {UNKNOWN:'Don\'t know', NOBODY:'Nobody'}

	@staticmethod
	def get_key(round, year):
		try:
			return 'b_' + `int(year)` + '-' + `int(round)`
		except:
			return ''

	year = IntegerProperty(required=True)
	round = ReferenceProperty(Round, required=True, collection_name='beer_set')
	buyer = StringProperty(required=True)
	player_ref = ReferenceProperty(Player, required=False, collection_name='beer_set')
	
class Shirts(Model):
	"""Link between a player and a round for washing shirts"""

	UNKNOWN = "unknown"
	NOBODY = "nobody"
	OTHERS = [UNKNOWN, NOBODY]
	OTHERS_FRIENDLY = {UNKNOWN:'Don\'t know', NOBODY:'Nobody'}

	@staticmethod
	def get_key(round, year):
		try:
			return 's_' + `int(year)` + '-' + `int(round)`
		except:
			return ''

	year = IntegerProperty(required=True)
	round = ReferenceProperty(Round, required=True, collection_name='shirt_set')
	washer = StringProperty(required=True)
	player_ref = ReferenceProperty(Player, required=False, collection_name='shirt_set')

class Result(Model):
	"""Goals for and against, and hence the result, for a given round"""

	def get_result_str(self):
		"""Turn the two sides' goals into a single word summary"""
		if self.deewhy_forfeit:
			return 'Loss'
		elif self.opponent_forfeit:
			return 'Win'
		try:
			goal_diff = self.deewhy_goals - self.opponent_goals
			if goal_diff < 0:
				return 'Loss'
			elif goal_diff > 0:
				return 'Win'
			else:
				return 'Draw'
		except:
			return ''

	def get_scorer_str(self):
		"""Build a short summary string for who scored in the game"""
		result = []
		for s in self.scorer_set:
			p_str = s.player.get_short_name()
			if s.count > 1:
				p_str += '&nbsp;(%d)' % (s.count)
			result.append(p_str)
		if self.other_goals > 0:
			p_str = 'Other'
			if self.other_goals > 1:
				p_str += '&nbsp;(%d)' % (self.other_goals)
			result.append(p_str)
		if self.own_goals > 0:
			p_str = 'Own goal'
			if self.own_goals > 1:
				p_str += '&nbsp;(%d)' % (self.own_goals)
			result.append(p_str)

		if len(result) == 0:
			return 'Nobody'
		else:
			return ', '.join(result)
		
	@staticmethod
	def get_key(round, year):
		try:
			return 'res_' + `int(year)` + '-' + `int(round)`
		except:
			return ''

	year = IntegerProperty(required=True)
	round = ReferenceProperty(Round, required=True, collection_name='result')
	deewhy_forfeit = BooleanProperty(required=False)
	opponent_forfeit = BooleanProperty(required=False)
	deewhy_goals = IntegerProperty(required=False)
	opponent_goals = IntegerProperty(required=False)
	other_goals = IntegerProperty(required=False)
	own_goals = IntegerProperty(required=False)
	
class GoalsScored(Model):
	"""Link between a player and the rounds where they scored"""

	@staticmethod
	def get_key(player, round, year):
		try:
			return 'gs_' + player + '-' + `int(year)` + '-' + `int(round)`
		except:
			return ''
	
	year = IntegerProperty(required=True)
	result = ReferenceProperty(Result, required=True, collection_name='scorer_set')
	player = ReferenceProperty(Player, required=True, collection_name='goal_set')
	count = IntegerProperty(required=True)	
	
class Availability(Model):
	"""Link between a player and their availability for each round"""
	@staticmethod
	def get_key(player, round, year):
		try:
			return 'av_' + player + '-' + `int(year)` + '-' + `int(round)`
		except:
			return ''
	
	playing = BooleanProperty(required=True)	
	year = IntegerProperty(required=True)
	given_date = DateProperty(required=True)	# Would prefer to look up based on this solely (not round), but django makes it difficult
	round = ReferenceProperty(Round, required=True, collection_name='availability_set')
	player = ReferenceProperty(Player, required=True, collection_name='availability_set')
	
	
	
	
	
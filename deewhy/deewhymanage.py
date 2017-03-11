import os, urllib
import logging
import base64
from datetime import datetime, timedelta
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import memcache, users, mail
# from google.appengine.ext.webapp.util import login_required
from models import Player, Round, Beer, Shirts, TeamList, Ground, Result, GoalsScored, Availability
from deewhy import *

class DeeWhyManagePage(DeeWhyPage):
	"""Base type for all management pages. Note that there is minimal caching for these pages, as
they need to be highly dynamic and only person is ever accessing them - plus I can't risk
accidentally caching incorrent content if I make a programming error!"""

	def __init__(self):
		self.is_manage = True

	def matching_page(self, base_url, type):
		"""Works out which page the URL refers to after you remove the management prefix"""
		if base_url.startswith('/' + PageTypes.manage):
			base_url = base_url[len(PageTypes.manage)+1:]
			if base_url.startswith('/'):
				base_url = base_url[1:]

			if len(type) == 0:
				if len(base_url) == 0 or base_url == '/':
					return True
				else:
					return False
			return base_url.startswith(type)
		else:
			return False
			
	def get_tabs(self, args):
		"""Construct the management-specific row of tabs, where every tab other than the current is a link"""
		base_url = args['base_url']
		year = ''
		year_args = {}
		if args.has_key('year'):
			year = args['year']
			year_args['year'] = year
		# year is currently the only argument we want to carry between pages
		args_str = '/' + self.build_arg_str(year_args)
		
		tabs = [
			(PageTypes.manage + args_str, self.matching_page(base_url, '') or self.matching_page(base_url, PageTypes.player), 'Players'),
			(PageTypes.manage + '/' + PageTypes.protected + args_str, self.matching_page(base_url, PageTypes.protected), 'Summary'),
			(PageTypes.manage + '/' + PageTypes.ground + args_str, self.matching_page(base_url, PageTypes.ground), 'Grounds'),
			(PageTypes.manage + '/' + PageTypes.draw + args_str, self.matching_page(base_url, PageTypes.draw), 'Draw'),
			(PageTypes.manage + '/' + PageTypes.results + args_str, self.matching_page(base_url, PageTypes.results), 'Results'),
			(PageTypes.manage + '/' + PageTypes.beer + args_str, self.matching_page(base_url, PageTypes.beer), 'Beer'),
			(PageTypes.manage + '/' + PageTypes.shirts + args_str, self.matching_page(base_url, PageTypes.shirts), 'Shirts'),
		]

		# Add another tab for each year it has data for
		for y in xrange(datetime.now().year, FIRST_YEAR - 1, -1):
			if not y == self.get_year(args):
				tabs.append((PageTypes.manage + '/' + self.build_arg_str({'year': `y`}), False, `y`))
		tabs.append((PageTypes.manage + '/' + self.build_arg_str({'year': `ALL_YEARS`}), False, 'All years'))
		tabs.append(('', False, 'View mode'))	# Special tab to exit management mode
		return tabs
		
class DrawManagePage(DeeWhyManagePage):
	"""The page to manage the full season draw"""

	def do_body(self, args):
		"""Render the HTML for all the rounds, and provide enough information to edit an existing round or create a new one"""
		data = {
			'url_args': args,
			'new_round': True,
			'grounds': Ground.gql('ORDER BY name ASC')
		}
		year = self.get_year(args)
		if year == ALL_YEARS:
			data['rounds'] = Round.gql('ORDER BY date ASC')
		else:
			data['rounds'] = Round.gql('WHERE year = :1 ORDER BY date ASC', year)
			
		# Retrieve the full information for the given round so we can edit it
		if args.has_key('round'):
			round_key = Round.get_key(urllib.unquote(urllib.unquote(args['round'])), year)
			curr_round = Round.get_by_key_name(round_key)
			if curr_round:
				data['current'] = curr_round
				data['new_round'] = False
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'manage_draw.html')
		self.response.out.write(template.render(tpath, data))

	def delete_round(self, key):
		"""Scrap the entire round"""
		if key:
			r = Round.get_by_key_name(key)
			if r:
				r.delete()

	def post(self, base_url, extra):
		"""Save the details for the given round"""
		try:
			old_key = self.request.get('key_name')
			if self.request.POST.get('do_delete') == 'true':
			# Delete the selected round
				self.delete_round(old_key)
				year = old_key.split('-')[0]
			else:
			# Create/update the round
				num = int(self.request.get('num').strip())
				caption = self.request.get('caption').strip()
				#if caption == '':
				#	caption = 'Rd ' + `num`
				try:
					date = datetime.strptime(self.request.get('date').strip(), '%d/%m/%Y').date()
				except:
					date = datetime.strptime(self.request.get('date').strip(), '%d/%m/%y').date()
				time_value = self.request.get('time').strip()
				if time_value == '':
					time = None
				else:
					time = datetime.strptime(time_value, '%H:%M').time()
				opponent = self.request.get('opponent').strip()
				homeaway = self.request.get('homeaway').strip()
				location = Ground.get(self.request.get('location'))
				key = Round.get_key(num, date.year)
				if key != '' and num != '':
					new_round = Round(
						key_name = key,
						num = num,
						year = date.year,
						caption = caption,
						date = date,
						time = time,
						opponent = opponent,
						homeaway = homeaway,
						location = location,
					)
					new_round.put()
				if old_key != key:
					# If changing the info changes the key, be sure to scrap the old entry too
					self.delete_round(old_key)
				year = date.year
					
			# Pages that are affected by this post:
			# - Draw, via a new item
			memcache.delete(PlayerPage.get_draw_mem_key(year))
			memcache.delete(PlayerPage.get_draw_mem_key(ALL_YEARS))
			# - All the individual player pages, via the items they can update
			for p in TeamList.gql('WHERE year = :1', year):
				memcache.delete(PlayerPage.get_player_mem_key(p.player.db_key, year))
				memcache.delete(PlayerPage.get_player_mem_key(p.player.db_key, ALL_YEARS))
			# NOT - results, beer or shirts (until results posted)
			
			self.get(base_url, extra)
		except Exception, e:
			self.get(base_url, extra, error=e)	
	
class PlayerManagePage(DeeWhyManagePage):
	"""The page to manage information about players and the years they play"""

	@staticmethod
	def get_list_mem_key(year):
		try:
			return 'playerlist_manage_%d'  % (int(year))
		except:
			return ''

	def do_body(self, args):
		"""Render the HTML for all the players, and provide enough information to edit an existing player or create a new one"""
		self.do_player_list(args, True)
		data = {
			'year': self.get_year(args),
			'url_args': args,
			'new_player': True,
			'past_years': list(range(datetime.now().year, FIRST_YEAR - 1, -1))
		}
		if args.has_key('player'):
			player_key = urllib.unquote(urllib.unquote(args['player']))	# Dealing with spaces - why don't they disappear??
			curr_player = Player.get_by_key_name(player_key)

			if curr_player:
				data['current'] = curr_player
				data['new_player'] = False
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'manage_players.html')
		self.response.out.write(template.render(tpath, data))

	def delete_player(self, key):
		"""Scrap the entire player"""
		if key:
			p = Player.get_by_key_name(key)
			if p:
				p.delete()
		
	def delete_player_year(self, key):
		"""Remove the association between the player and the year"""
		if key:
			t = TeamList.get_by_key_name(key)
			if t:
				t.delete()
		
	def post(self, base_url, extra):
		"""Save the data posted about the player from the HTML form"""
		#try:
		affected_years = set()
		old_key = self.request.get('key_name')
		if self.request.POST.has_key('do_delete') and self.request.POST.get('do_delete') == 'true':
		# Delete the selected player
		# Also need to delete anything else they were involved with e.g. teamlists, goals scored, etc...
			key = old_key
			player = Player.get_by_key_name(key)
			for x in player.year_list:
				x.delete() 
			for x in player.beer_set:
				x.delete() 
			for x in player.shirt_set:
				x.delete() 
			for x in player.goal_set:
				x.delete() 
			for x in player.availability_set:
				x.delete() 
			self.delete_player(key)
		else:
		# Create/update the player
			first = self.request.get('first_name').strip()
			last = self.request.get('last_name').strip()
			key = Player.get_key(first, last)
			nick = self.request.get('nick_name').strip()
			email = self.request.get('email').strip()
			phone = self.request.get('phone').strip()
			registration = self.request.get('registration').strip()
			shirt = self.request.get('shirt').strip()
			if key != '':
				new_player = Player(
					key_name = key,
					db_key = key,
					first_name = first,
					last_name = last,
					nick_name = nick,
					email = email,
					phone = phone,
					registration = registration,
					shirt = shirt,
				)
				new_player.put()
				for y in xrange(datetime.now().year, FIRST_YEAR - 1, -1):
					year_key = TeamList.get_key(key, y)
					if self.request.POST.has_key('played_' + str(y)):
						TeamList(
							key_name = year_key,
							player = new_player,
							year = y,
						).put()
					else:
						self.delete_player_year(year_key)
			if old_key != key:
				# If changing the info changes the key, be sure to scrap the old entry too
				self.delete_player(old_key)

		# Quite a few pages are potentially affected when you change a player's details. But only do it if the
		# form says to do so, because it's so expensive to regenerate everything!
		nickname_update = (self.request.POST.has_key('do_flush') and self.request.get('do_flush') == 'on')

		# Update the side listings
		memcache.delete(PlayerPage.get_list_mem_key(ALL_YEARS))
		memcache.delete(PlayerManagePage.get_list_mem_key(ALL_YEARS))
		memcache.delete(PlayerPage.get_player_mem_key(key, ALL_YEARS))	# Their availability
		if nickname_update:
			memcache.delete(PlayerPage.get_draw_mem_key(ALL_YEARS))
			memcache.delete(ResultsPage.get_mem_key(ALL_YEARS))
			memcache.delete(ScorersPage.get_mem_key(ALL_YEARS))
			memcache.delete(BeerPage.get_mem_key('beer', ALL_YEARS))
			memcache.delete(ShirtsPage.get_mem_key('shirts', ALL_YEARS))
			memcache.delete(ProtectedPage.get_mem_key())

		for y in xrange(datetime.now().year, FIRST_YEAR - 1, -1):
			memcache.delete(PlayerPage.get_list_mem_key(y))
			memcache.delete(PlayerManagePage.get_list_mem_key(y))
			memcache.delete(PlayerPage.get_player_mem_key(key, y))	# Their availability

			if nickname_update:
				memcache.delete(PlayerPage.get_draw_mem_key(y))
				memcache.delete(ResultsPage.get_mem_key(y))
				memcache.delete(ScorersPage.get_mem_key(y))
				memcache.delete(BeerPage.get_mem_key('beer', y))
				memcache.delete(ShirtsPage.get_mem_key('shirts', y))

		self.get(base_url, extra)
		#except Exception, e:
		#	self.get(base_url, extra, error=e)			
			
class GroundManagePage(DeeWhyManagePage):
	"""The page to specify information about the grounds we play on"""

	@staticmethod
	def get_list_mem_key(year):
		# Year is not strictly necessary, but preserve it to include in links
		try:
			return 'groundlist_manage_%d'  % (int(year))
		except:
			return ''

	def do_body(self, args):
		"""Render the HTML for all the grounds, and provide enough information to edit an existing ground or create a new one"""
		year = self.get_year(args)
		ground_list = memcache.get(GroundManagePage.get_list_mem_key(year))
		if ground_list is None:
			data = {
				'url_args': args,
				'grounds': Ground.gql('ORDER BY name ASC')
			}
				
			tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'grounds.html')
			ground_list = template.render(tpath, data)
		self.response.out.write(ground_list)

		data = {
			'url_args': args,
			'new_ground': True,
		}
		# Get all the information for the ground they have selected to edit
		if args.has_key('ground'):
			curr_ground = Ground.get(args['ground'])
			if curr_ground:
				data['current'] = curr_ground
				data['new_ground'] = False
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'manage_grounds.html')
		self.response.out.write(template.render(tpath, data))

	def delete_ground(self, key):
		"""Scrap the whole ground"""
		if key:
			g = Ground.get_by_key_name(key)
			if g:
				g.delete()
		
	def post(self, base_url, extra):
		"""Save the data posted about the ground from the HTML form"""
		try:
			db_key = self.request.get('db_key')
			if self.request.POST.has_key('do_delete') and self.request.POST.get('do_delete') == 'true':
			# Delete the selected ground
				self.delete_ground(db_key)
			else:
			# Create/update the ground
				name = self.request.get('name').strip()
				address = self.request.get('address').strip()
				map = self.request.get('map').strip()
				if db_key == '':
					# new entry, needs random key
					db_key = Ground.get_key()
				args = {
					'key_name': db_key,
					'db_key': db_key,
					'name': name,
					'address': address,
					'map': map,
				}
	
				new_ground = Ground(**args)
				new_ground.put()
			
			# Pages that are affected by this post:
			for y in xrange(datetime.now().year, FIRST_YEAR - 1, -1):
				# - Draw, via the location and link
				memcache.delete(PlayerPage.get_draw_mem_key(y))
				# - Management ground listing
				memcache.delete(GroundManagePage.get_list_mem_key(y))
			memcache.delete(PlayerPage.get_draw_mem_key(ALL_YEARS))
			memcache.delete(GroundManagePage.get_list_mem_key(ALL_YEARS))
					
			self.get(base_url, extra)
		except Exception, e:
			self.get(base_url, extra, error=e)			
			
class ResultsManagePage(DeeWhyManagePage):
	"""The page to summarise the results of the match. Should really try to fold the item entry (beer, shirts)
into this page to centralise post-match data entry"""

	def do_body(self, args):
		"""Render the HTML for all the results, and provide enough information to edit an game"""
		data = {
			'url_args': args,
		}
		year = self.get_year(args)
		if year == ALL_YEARS:
			data['rounds'] = Round.gql('ORDER BY date ASC')
		else:
			data['rounds'] = Round.gql('WHERE year = :1 ORDER BY date ASC', year)
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'rounds.html')
		self.response.out.write(template.render(tpath, data))

		data = {
			'url_args': args,
		}
		
		# Get the full data for the given round so they can edit it
		if args.has_key('round'):
			round_num = args['round']
			round_key = Round.get_key(round_num, year)
			result_key = Result.get_key(round_num, year)
			if round_key != '':
				curr_round = Round.get_by_key_name(round_key)
				if curr_round:
					data['players'] = [p.player for p in TeamList.gql('WHERE year = :1', curr_round.date.year)]
					data['players'].sort(self.sort_players)
					data['round'] = curr_round
				curr_result = Result.get_by_key_name(result_key)
				if curr_result:
					data['result'] = curr_result
					if curr_result.other_goals == 0:
						curr_result.other_goals = None
					if curr_result.own_goals == 0:
						curr_result.own_goals = None

					#if curr_result.deewhy_forfeit:
					#	curr_result.deewhy_goals = 0
					#	curr_result.opponent_goals = 5
					#elif curr_result.opponent_forfeit:
					#	curr_result.deewhy_goals = 5
					#	curr_result.opponent_goals = 0

		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'manage_results.html')
		self.response.out.write(template.render(tpath, data))

	def get_goals(self, field):
		"""Parse the given goal count out of a string field in the request object"""
		try:
			return(int(self.request.get(field)))
		except:
			return 0	
		
	def post(self, base_url, extra):
		"""Save the data posted about the result from the HTML form"""
		try:
			curr_round = None
			round_num = int(self.request.get('round_num'))
			year = int(self.request.get('year'))
			round_key = Round.get_key(round_num, year)
			if round_key:
				curr_round = Round.get_by_key_name(round_key)

			if curr_round:
				# Quite a few cached pages depend upon this output, need to delete them all
				# - Removing this page from the summary
				memcache.delete(PlayerPage.get_draw_mem_key(year))
				memcache.delete(PlayerPage.get_draw_mem_key(ALL_YEARS))
				# - Disabling the options for this page for each player
				for t in TeamList.gql('WHERE year = :1', year):
					memcache.delete(PlayerPage.get_player_mem_key(t.player.db_key, year))
				# - Changing the result and who scored
				memcache.delete(ResultsPage.get_mem_key(year))
				memcache.delete(ResultsPage.get_mem_key(ALL_YEARS))
				# - Changing the number of goals
				memcache.delete(ScorersPage.get_mem_key(year))
				memcache.delete(ScorersPage.get_mem_key(ALL_YEARS))
				# - Triggering previously suppressed rounds for the beer and shirts
				memcache.delete(BeerPage.get_mem_key('beer', year))
				memcache.delete(BeerPage.get_mem_key('beer', ALL_YEARS))
				memcache.delete(ShirtsPage.get_mem_key('shirts', year))
				memcache.delete(ShirtsPage.get_mem_key('shirts', ALL_YEARS))

			
				args = {
					'year': year,
					'key_name': Result.get_key(round_num, year),
					'round': curr_round,
				}
				
				deewhy_forfeit = self.request.get('deewhy_forfeit')
				opponent_forfeit = self.request.get('opponent_forfeit')
				if not (deewhy_forfeit or opponent_forfeit):
					# Regular operation - read the goal counts
					args['deewhy_goals'] = self.get_goals('deewhy_goals')
					args['opponent_goals'] = self.get_goals('opponent_goals')
					args['other_goals'] = self.get_goals('other_goals')
					args['own_goals'] = self.get_goals('own_goals')
				elif deewhy_forfeit is not None and self.request.get('deewhy_forfeit') == 'on':
					# No goals in a forfeit
					args['deewhy_forfeit'] = True
				elif opponent_forfeit is not None and self.request.get('opponent_forfeit') == 'on':
					# No goals in a forfeit
					args['opponent_forfeit'] = True
				curr_result = Result(**args)
				curr_result.put()

				# Need to delete any existing scorers for this round - otherwise orphaned goals will stuff up the tallies
				for scorer in curr_result.scorer_set:
					scorer.delete()

				if not (deewhy_forfeit or opponent_forfeit):
					for post_key in self.request.POST.keys():
						# Each goal scorer in the game needs a separate record
						if post_key.startswith('goals_'):
							player = Player.get_by_key_name(post_key[len('goals_'):])
							goals = self.get_goals(post_key)
							if player is not None and goals > 0:
								GoalsScored(
									key_name = GoalsScored.get_key(player.db_key, round_num, year),
									year = int(year),
									player = player,
									result = curr_result,
									count = goals,
								).put()
			self.get(base_url, extra)
		except Exception, e:
			self.get(base_url, extra, error=e)			

class CommonSelectManagePage(DeeWhyManagePage):
	def do_body(self, args):
		"""Render the HTML for all the items, and provide enough information to edit one of them."""
		updated_args = dict(args)
		year = self.get_year(args)
		updated_args['year'] = year
		data = {
			'url_args': updated_args,
		}
		if year == ALL_YEARS:
			data['rounds'] = Round.gql('ORDER BY date ASC')
			data['players'] = Player.gql('ORDER BY last_name ASC, first_name ASC')
		else:
			data['rounds'] = Round.gql('WHERE year = :1 ORDER BY date ASC', int(year))
			data['players'] = [p.player for p in TeamList.gql('WHERE year = :1', int(year))]
			data['players'].sort(self.sort_players)
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, self.template_file)
		self.response.out.write(template.render(tpath, data))

	def post(self, base_url, extra):
		"""Save the data posted about the all the items from the HTML form"""
		try:
			delete_years = set()	# Only refresh the cache for affected years
			# All the rounds are saved at once
			for year_round_key in self.request.POST.keys():
				try:
					split_key = year_round_key.split('-')
					year = split_key[0]
					delete_years.add(year)
					round = split_key[1]
					if len(round) == 0:
						# Might have been a negative round, so an extra split!
						round = '-' + split_key[2]
					round_key = Round.get_key(round, year)
					round = Round.get_by_key_name(round_key)
					if round:
						args = {
							'year': round.year,
							'key_name': self.data_class.get_key(round.num, round.year),
							'round': round
						}
						player_key = self.request.POST.get(year_round_key)
						args[self.name_property] = player_key
						if not player_key in self.data_class.OTHERS:
							args['player_ref'] = Player.get_by_key_name(player_key)
						
						new_entry = self.data_class(**args)
						new_entry.put()
				except IndexError:
					pass
					
		# Flush the cache for the affected years
			for y in delete_years:
				memcache.delete(CommonItemPage.get_mem_key(self.type,  y))
			memcache.delete(CommonItemPage.get_mem_key(self.type,  ALL_YEARS))
			self.get(base_url, extra)
		except Exception, e:
			self.get(base_url, extra, error=e)	
	
class BeerManagePage(CommonSelectManagePage):
	def __init__(self):
		self.template_file = 'manage_beer.html'
		self.data_class = Beer
		self.name_property = 'buyer'
		self.type = 'beer'
		
class ShirtsManagePage(CommonSelectManagePage):
	def __init__(self):
		self.template_file = 'manage_shirts.html'
		self.data_class = Shirts
		self.name_property = 'washer'
		self.type = 'shirts'

class ProtectedManagePage(DeeWhyManagePage):
	"""Shows pretty much the same information as the standard personal information page, but with a little more housekeeping"""
	def do_body(self, args):
		year = self.get_year(args)
		if year == ALL_YEARS:
			players = Player.all()
		else:
			players = [t.player for t in TeamList.gql('WHERE year = :1', year)]
		players.sort(self.sort_players)
		data = {
			'players': players,
		}
	
		tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'manage_protected.html')
		protected_page = template.render(tpath, data)
		self.response.out.write(protected_page)


class MailerManagePage(DeeWhyManagePage):
	"""The page that is called via a cron job to mail out the upcoming matches to all players in the team"""

  	def do_body(self, args):
		"""Generate the HTML email if there is an upcoming game"""
  		day_skip = 2
  		if args.has_key('days'):
  			try:
	  			day_skip = int(args['days'])
	  		except:
	  			pass
  		admin_address = 'abhudson@mailinator.com'
		curr_date = datetime.now()
		start_date = curr_date.replace(hour=0, minute=0, second=0) + timedelta(days=day_skip)
		end_date = curr_date.replace(hour=0, minute=0, second=0) + timedelta(days=day_skip + 1)

		# Find all the games that are within the given date range - really only expect one, behaviour
		# could end up a little strange if there's multiple...
		query = Round.gql('WHERE date >= :1 AND date <= :2', start_date, end_date)
		curr_round = query.get()
		logging.debug('WHERE date >= %s AND date <= %s' % (start_date, end_date))
		logging.debug(curr_round)
		
		if curr_round:
			data = {
				'current': curr_round,
			}
			
			tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'mailer.html')		
			email_content = template.render(tpath, data)
			self.response.out.write(email_content)	# Print the content as an added debug
	
			players = [p.player for p in TeamList.gql('WHERE year = :1', curr_round.date.year)]
			non_admins = []
			admin = ''
			for p in players:
				details = '%s %s<%s>' % (p.first_name, p.last_name,  p.email)
				if p.email == admin_address:
					admin = details
				else:
					non_admins.append(details)
			recipients = ','.join(non_admins)
			cc_recipients = admin	# working around a server bug where cron emails fail when sent to me!
			#recipients = 'Test Guy<testguy@mailinator.com>' % (curr_date.strftime('%A %d %B %I:%M'))	# To make sure tests don't go out!
			logging.debug('Sending to ' + recipients)

			"""
			recipients = ','.join([
				'Adam1<abhudson.test1@mailinator.com>',
				'Adam2<abhudson.test2@mailinator.com>',
				])
			logging.debug('Really sending to ' + recipients)
			"""
					
			caption = curr_round.caption
			if not caption:
				caption = 'Round ' + `int(curr_round.num)`
			kickoffStr = `int(curr_round.time.strftime('%I'))`
			if curr_round.time.minute > 0:
				kickoffStr += ':' + curr_round.time.strftime('%M')
			kickoffStr += curr_round.time.strftime('%p')
			subject = caption + ' - ' + curr_round.date.strftime('%A %d %B') + ' at ' + kickoffStr
	
			message = mail.EmailMessage()
			message.subject = subject
			message.sender = 'Dee Why AL5 Team Page<abhudson@mailinator.com>'
			message.to = recipients
			message.cc = cc_recipients
			# Too lazy to add BCC recipients as a UI option so just add them here
			message.bcc = 'others@mailinator.com'
			message.html = email_content
			message.check_initialized()
			message.send()

class ExportManagePage(DeeWhyManagePage):
	"""Stupid testing page"""
	def do_body(self, arg):
		self.response.out.write('export')

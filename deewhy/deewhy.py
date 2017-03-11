import os, urllib
import base64
from datetime import datetime, timedelta
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import memcache, users, mail
from google.appengine.ext.webapp.util import login_required
from models import Player, Round, Beer, Shirts, TeamList, Ground, Result, GoalsScored, Availability

FIRST_YEAR = 2007
ALL_YEARS = 0


class PageTypes:
    """Enumerate the page types and map them to URLs"""

    draw = 'draw'
    player = 'player'
    ground = 'ground'
    results = 'results'
    scorers = 'scorers'
    beer = 'beer'
    shirts = 'shirts'
    table = 'table'
    mailer = 'mailer'
    export = 'export'
    manage = 'manage'
    protected = 'protected'


def basicauth(func):
    """Decorator to make appengine customise the authentication of a page"""

    def callf(webappRequest, *args, **kwargs):
        # Parse the header to extract a user/password combo.
        # We're expecting something like "Basic XZxgZRTpbjpvcGVuIHYlc4FkZQ=="
        auth_header = webappRequest.request.headers.get('Authorization')

        if auth_header == None:
            webappRequest.response.set_status(401, message="Authorization Required")
            webappRequest.response.headers['WWW-Authenticate'] = 'Basic realm="Dee Why AL5"'
        else:
            # Isolate the encoded user/passwd and decode it
            auth_parts = auth_header.split(' ')
            user_pass_parts = base64.b64decode(auth_parts[1]).split(':')
            user_arg = user_pass_parts[0]
            pass_arg = user_pass_parts[1]

            if pass_arg != "NotTheRealPassword":  # Don't care about user name and not important enough to obfuscate password
                webappRequest.response.set_status(401, message="Authorization Required")
                webappRequest.response.headers['WWW-Authenticate'] = 'Basic realm="Dee Why AL5"'
                webappRequest.response.out.write(
                    template.render(os.path.join(DeeWhyPage.TEMPLATE_DIR, 'access_denied.html'), {}))
            else:
                return func(webappRequest, *args, **kwargs)

    return callf


class DeeWhyPage(webapp.RequestHandler):
    """Base type for all general user pages"""

    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '../templates')

    def __init__(self):
        self.is_manage = False

    def get_year(self, args):
        try:
            return int(args['year'])
        except KeyError, ValueError:
            return datetime.now().year

    def build_arg_str(self, args, excludes=['base_url']):
        """Build a URL request string that will carry the given arguments between pages"""
        removed = {}
        result = ''
        for e in excludes:
            if args.has_key(e):
                removed[e] = args.pop(e)
        if len(args) > 0:
            try:
                result = '?' + '&'.join(['='.join(i) for i in args.items()])
            except TypeError:
                try:
                    for k in args.keys():
                        args[k] = `args[k]`
                    result = '?' + '&'.join(['='.join(i) for i in args.items()])
                except:
                    result = ''
        for e in excludes:
            if removed.has_key(e):
                args[e] = removed[e]
        return result

    def matching_page(self, base_url, type):
        """Used to work out whether the URL is currently on the given page"""
        if base_url.startswith('/'):
            base_url = base_url[1:]
        return base_url.startswith(type)

    @basicauth
    def protected_get(self, url, extra=None, error=None):
        self._get_internal(url, extra=None, error=None)

    def get(self, url, extra=None, error=None):
        self._get_internal(url, extra=None, error=None)

    def _get_internal(self, url, extra=None, error=None):
        """Construct a standard page, with the common HTTP and HTML headers/footers."""
        self.response.headers['Content-Type'] = 'text/html'
        args = self.request.GET
        args['base_url'] = url
        self.do_header(args)
        if error is None:
            self.do_body(args)
        else:
            self.response.out.write('''
            <br/>
            <p class="playersummary">
                Error: ''' + error.message + '''
            </p>
            <p class="playersummary">
                <input type="button" value="Back" onclick="javascript:history.back()"/>
            </p>
            <br/>
            ''')
        self.do_footer()

    def get_tabs(self, args):
        """Construct the common row of tabs, where every tab other than the current is a link"""
        base_url = args['base_url']
        year = ''
        year_args = {}
        if args.has_key('year'):
            year = args['year']
            year_args['year'] = year
        # year is currently the only argument we want to carry between pages
        args_str = '/' + self.build_arg_str(year_args)

        # Show the availability entry option for the current year only - no point for historical browsing
        is_current_year = year == '' or year == str(datetime.now().year)
        if is_current_year:
            tabs = [
                (args_str[1:], base_url == '' or base_url == '/' or self.matching_page(base_url, PageTypes.player),
                 'Draw & Availability'),
            ]
        else:
            tabs = []

        tabs += [
            (PageTypes.results + args_str, self.matching_page(base_url, PageTypes.results), 'Results'),
            (PageTypes.scorers + args_str, self.matching_page(base_url, PageTypes.scorers), 'Goal Scorers'),
        ]


        # These things are also only relevant for the current year
        if is_current_year:
            tabs += [
                (PageTypes.beer + args_str, self.matching_page(base_url, PageTypes.beer), 'Beer'),
                (PageTypes.shirts + args_str, self.matching_page(base_url, PageTypes.shirts), 'Shirts'),
                (PageTypes.table + args_str, self.matching_page(base_url, PageTypes.table), 'Table'),
            ]

        # Add a tab for each year that we have historical results
        for y in xrange(datetime.now().year, FIRST_YEAR - 1, -1):
            prefix = ''
            if y != datetime.now().year:
                prefix = PageTypes.results + '/'
            if not y == self.get_year(args):
                tabs.append((prefix + self.build_arg_str({'year': `y`}), False, `y`))
        if not self.get_year(args) == 0:
            tabs.append(
                (prefix + self.build_arg_str({'year': '0'}), False, '%d-%d' % (FIRST_YEAR, datetime.now().year)))
        return tabs

    def sort_players(self, x, y):
        xs = x.last_name
        ys = y.last_name
        if xs > ys:
            return 1
        elif xs < ys:
            return -1
        elif x.first_name > y.first_name:
            return 1
        elif x.first_name < y.first_name:
            return -1
        else:
            return 0;

    def do_player_list(self, args, manage_mode=False):
        """Render the HTML for a list of players"""
        year = self.get_year(args)
        if manage_mode:
            mem_key = PlayerPage.get_manage_list_mem_key(year)
        else:
            mem_key = PlayerPage.get_list_mem_key(year)
        player_div = memcache.get(mem_key)
        if player_div is None:
            data = {
            'url_args': args,
            }
            if year == ALL_YEARS:
                data['players'] = Player.gql('ORDER BY last_name ASC, first_name ASC')
            else:
                data['players'] = [p.player for p in TeamList.gql('WHERE year = :1', year)]
                data['players'].sort(self.sort_players)

            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'players.html')
            player_div = template.render(tpath, data)
            memcache.set(mem_key, player_div)
        self.response.out.write(player_div)

    def do_header(self, args):
        """Generate the HTML for the common header, which includes the tabs"""
        mem_key = 'header_%s_%d' % (args['base_url'], self.get_year(args))
        header = memcache.get(mem_key)
        #header = None	# Uncomment when flushing the cached header in production
        if header is None:
            data = {
            'url_args': args,
            'tabs': self.get_tabs(args),
            }
            try:
                year = args['year']
                if year == '0':
                    data['year'] = 'All years'
                elif year != str(datetime.now().year):
                    data['year'] = year
            except:
                pass
            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'header.html')
            header = template.render(tpath, data)
            memcache.set(mem_key, header, 60 * 60 * 24)  # Won't change dynamically, so cache for a day
        self.response.out.write(header)

    def do_footer(self):
        """Generate the HTML for the common footer"""
        mem_key = 'footer'
        footer = memcache.get(mem_key)
        if footer is None:
            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'footer.html')
            footer = template.render(tpath, {})
            memcache.set(mem_key, footer, 60 * 60 * 24)  # Won't change dynamically, so cache for a day
        self.response.out.write(footer)


class PlayerPage(DeeWhyPage):
    """The main page for the site. Either generates HTML for the front summary page that
outlines the season draw, or presents a player with a way to set their own availability
throughout the year."""

    @staticmethod
    def get_player_mem_key(player, year):
        try:
            return 'player_%s_%d' % (player, int(year))
        except:
            return ''

    @staticmethod
    def get_list_mem_key(year):
        try:
            return 'playerlist_%d' % (int(year))
        except:
            return ''

    @staticmethod
    def get_manage_list_mem_key(year):
        """Quick and dirty way to avoid a circular dependency"""
        try:
            return 'playerlist_manage_%d' % (int(year))
        except:
            return ''

    @staticmethod
    def get_draw_mem_key(year):
        try:
            return 'draw_%d' % (int(year))
        except:
            return ''

    def do_body(self, args):
        """Render the HTML for the front page"""
        self.do_player_list(args)
        year = self.get_year(args)
        # Different key for the different modes
        if args.has_key('player'):
            mem_key = PlayerPage.get_player_mem_key(args['player'], year)
        else:
            mem_key = PlayerPage.get_draw_mem_key(year)

        player_page = memcache.get(mem_key)
        if player_page is None:
            data = {
            'url_args': args,
            }

            # Switches mode depending on the input:
            if args.has_key('player'):
                # Present the player with the dialogues to set the availability
                page = 'individual.html'
                data = {
                'rounds': Round.gql('WHERE year = :1 ORDER BY date ASC', year),
                'player': Player.get_by_key_name(args['player']),
                }
            else:
                # Present the full season summary of upcoming games
                page = 'summary.html'
                if year == ALL_YEARS:
                    data['rounds'] = Round.gql('ORDER BY date ASC')
                else:
                    data['rounds'] = Round.gql('WHERE year = :1 ORDER BY date ASC', year)
            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, page)
            player_page = template.render(tpath, data)
            memcache.set(mem_key, player_page)
        self.response.out.write(player_page)

    def post(self, base_url, extra):
        """The user is saving their availability for the year, so save it to the datastore and
        invalidate the affected pages' HTML"""
        try:
            delete_years = set()
            if self.request.POST.has_key('updated'):
                player = Player.get_by_key_name(self.request.get('updated'))
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
                        # Writes the current round's date each time, just in case it has changed. Would have preferred to have
                        # multiple records for the player, linked by date and not time, but django made it difficult (unless I
                        # wanted to have a Model that just contains a date, and everything links back to that...)
                        if round:
                            args = {
                            'key_name': Availability.get_key(player.db_key, round.num, round.year),
                            'year': round.year,
                            'round': round,
                            'player': player,
                            'playing': self.request.POST.get(year_round_key) == "0",
                            'given_date': round.date,
                            }
                            Availability(**args).put()
                    except IndexError:
                        pass

                # Pages that have been affected by this update:
                for y in delete_years:
                    # - Draw page, via the number available
                    memcache.delete(PlayerPage.get_draw_mem_key(y))
                    # - Player summary, because their checkboxes have changed
                    memcache.delete(PlayerPage.get_player_mem_key(player.db_key, y))
                memcache.delete(PlayerPage.get_draw_mem_key(ALL_YEARS))
                memcache.delete(PlayerPage.get_player_mem_key(player.db_key, ALL_YEARS))
            self.get(base_url, extra)
        except Exception, e:
            self.get(base_url, extra, error=e)


class ResultsPage(DeeWhyPage):
    """The page that summarises the results for games in one or more years"""

    @staticmethod
    def get_mem_key(year):
        try:
            return 'results_%d' % (int(year))
        except:
            return ''

    def sort_results(self, x, y):
        xround = x.round
        yround = y.round
        xd = xround.date
        yd = yround.date

        if xd > yd:
            return 1
        elif xd < yd:
            return -1
        elif xround.time > yround.time:
            return 1
        elif xround.time < yround.time:
            return -1
        else:
            return 0;

    def do_body(self, args):
        year = self.get_year(args)
        mem_key = ResultsPage.get_mem_key(year)
        results_page = memcache.get(mem_key)
        if results_page is None:
            if year == ALL_YEARS:
                results = Result.all()
            else:
                results = Result.gql('WHERE year = :1', year)

            data = {
            'url_args': args,
            'results': [r for r in results],
            }
            data['results'].sort(self.sort_results)

            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'results.html')
            results_page = template.render(tpath, data)
            memcache.set(mem_key, results_page)
        self.response.out.write(results_page)


class ScorersPage(DeeWhyPage):
    """The goal scorer tally across one or more years"""

    @staticmethod
    def get_mem_key(year):
        try:
            return 'scorers_%d' % (int(year))
        except:
            return ''

    def sort_scores(self, x, y):
        if x[1] < y[1]:
            return 1
        elif x[1] > y[1]:
            return -1
        elif x[0] > y[0]:
            return 1
        elif x[0] < y[0]:
            return -1
        else:
            return 0;

    def do_body(self, args):
        """Render the HTMl for the goal scorer tally"""
        year = self.get_year(args)
        mem_key = ScorersPage.get_mem_key(year)
        scorer_page = memcache.get(mem_key)
        if scorer_page is None:
            if year == ALL_YEARS:
                players = Player.all()
            else:
                players = [t.player for t in TeamList.gql('WHERE year = :1', year)]

            scorers = []
            for p in players:
                tally = 0
                for g in p.goal_set:
                    round = g.result.round
                    if (year == ALL_YEARS or year == round.date.year) and round.num > 0:
                        # Only count real goals - negative rounds are trials
                        tally += g.count
                if tally > 0:
                    scorers.append((p.get_short_name(), tally))
            scorers.sort(self.sort_scores)
            data = {
            'scorers': scorers,
            }

            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'scorers.html')
            scorer_page = template.render(tpath, data)
            memcache.set(mem_key, scorer_page)
        self.response.out.write(scorer_page)


class CommonItemPage(DeeWhyPage):
    """Beer buying and shirt washing are basically the same page, but with different underlying
data models. So do the same for both and set the specifics in the subclasses."""

    @staticmethod
    def get_mem_key(type, year):
        try:
            return '%s_%d' % (type, int(year))
        except:
            return ''

    def sort_tuple(self, x, y):
        if x.year > y.year:
            return 1
        elif x.year < y.year:
            return -1
        xdate = x.round.date
        ydate = y.round.date
        if xdate > ydate:
            return 1
        elif xdate < ydate:
            return -1
        else:
            return 0;

    def do_body(self, args):
        """Render a given year's item summary. Makes no sense for multi-year."""
        year = self.get_year(args)
        mem_key = CommonItemPage.get_mem_key(self.type, year)
        item_page = memcache.get(mem_key)
        if item_page is None:
            items = self.data_class.gql('WHERE year = :1', year)
            items = [i for i in items]
            items.sort(self.sort_tuple)
            remaining = [t.player.get_short_name() for t in TeamList.gql('WHERE year = :1', year)]

            rounds = []
            for i in items:
                round = i.round
                # Only display entries that already have a result
                if round.result.get() is not None:
                    caption = round.caption
                    if not caption:
                        caption = round.num

                    if self.get_person(i) in self.data_class.OTHERS:
                        person = self.data_class.OTHERS_FRIENDLY[self.get_person(i)]
                    else:
                        person = i.player_ref.get_short_name()
                        try:
                            remaining.remove(person)
                        except ValueError:
                            # It was already removed before
                            pass
                    rounds.append((caption, person))
            if len(remaining) > 0:
                remaining_str = ', '.join(remaining)
            else:
                remaining_str = 'Nobody'
            data = {
            'rounds': rounds,
            'remaining': remaining_str,
            'url_args': args,
            }

            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, self.template_file)
            item_page = template.render(tpath, data)
            memcache.set(mem_key, item_page)
        self.response.out.write(item_page)


class BeerPage(CommonItemPage):
    def __init__(self):
        CommonItemPage.__init__(self)
        self.template_file = 'beer.html'
        self.data_class = Beer
        self.type = 'beer'

    def get_person(self, db_item):
        return db_item.buyer


class ShirtsPage(CommonItemPage):
    def __init__(self):
        CommonItemPage.__init__(self)
        self.template_file = 'shirts.html'
        self.data_class = Shirts
        self.type = 'shirts'

    def get_person(self, db_item):
        return db_item.washer


class TablePage(DeeWhyPage):
    """Simply present an iframe containing the association's table. URL changes every year!"""

    def do_body(self, args):
        #2011:
        #self.response.out.write("<iframe src='http://www.compman.net.au/idata_mwfa/TablesNew.php?s_Comp=31&s_Club=&s_AG=333&s_Div=1272' frameborder='0' style='width:100%; height:500px;' height='451'></iframe>")
        self.response.out.write(
            "<iframe src='http://www.compman.net.au/idata_mwfa/TablesNew.php?s_Comp=36&s_Club=&s_AG=373&s_Div=1445' frameborder='0' style='width:100%; height:700px;' height='451'></iframe>")


class ProtectedPage(DeeWhyPage):
    """A page that contains private information for player eyes only - so it's password protected"""

    @staticmethod
    def get_mem_key():
        # Only ever one version of this page, so no need to parameterise the key
        return 'protected_current'

    def get(self, url, extra=None, error=None):
        self.protected_get(url, extra, error)

    def do_body(self, args):
        """Render the HTML for the page containing private details for everybody currently in the team."""
        mem_key = ProtectedPage.get_mem_key()
        protected_page = None  #memcache.get(mem_key)
        if protected_page is None:
            players = [t.player for t in TeamList.gql('WHERE year = :1', datetime.now().year)]  # Always this year
            players.sort(self.sort_players)
            data = {
            'players': players,
            }

            tpath = os.path.join(DeeWhyPage.TEMPLATE_DIR, 'protected.html')
            protected_page = template.render(tpath, data)
            memcache.set(mem_key, protected_page)
        self.response.out.write(protected_page)


class MailerPage(DeeWhyPage):
    """Experimental - probably not needed"""

    def do_body(self, args):
        self.response.out.write('mailer')

# Team management site for Dee Why FC AL5
This site made managing a soccer team easy, in a way that nothing at the time (2009) allowed. As manager, I would set up the playing roster and match schedule at the beginning of the year. Players would record when they were going to be away, and the site would automatically email everybody 2 days before kickoff. Then, after each match, I would update the results and who performed what team duties. It made it simple to make sure everybody knew the who/when/where each week, and to refer back to results and top goal scorers across 10 years of data. 

I originally wrote this version of the site as an exercise in learning how to use Google AppEngine. It needed to be patched up a few times over the years as Google changed their storage and library requirements, or as I learnt new CSS tricks, but the overall design remains basically the same as when I first wrote it. Some of the queries seem to run quite slowly and could definitely be optimised, but it was always fast enough to suit its purposes.

Unfortunately it will no longer work because it needs to be upgraded from Python 2.4 to 2.7, and this will break the templating and data storage library compatibility in AppEngine. So it lives on here as a memorial, and not much else.

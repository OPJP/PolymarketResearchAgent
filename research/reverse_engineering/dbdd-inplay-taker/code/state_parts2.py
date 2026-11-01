"""Iteration-2 state parts: dimension inventory (E1), indicator ledger rows, components, target metrics."""
import indicators as ind


def dim(family, status, source, resolution, latency, best, mds, verdict, note=''):
    return {'family': family, 'status': status, 'source': source, 'resolution': resolution, 'publication_latency': latency,
            'best_indicator': best, 'min_detectable_share': mds, 'verdict': verdict, 'note': note}


def dimensions():
    return {
        'pm_tape_prints': dim('Polymarket internal', 'have', 'data-api /trades takerOnly (tapes2 sample; iteration-1 full tapes)', 'print, 1 s',
                              'block time (a print stamped T may match up to 2 s earlier)', 'prints so far, price level, 60-s USD, quiet',
                              None, 'drives', 'these are the co-occurrence baseline features (selection AUC 0.65 alone); not a decoded input'),
        'pm_books_top10': dim('Polymarket internal', 'have', 'live lab clob_wallets (dev blocks since 2026-10-31 12:18 UTC)', '200 ms, top 10',
                              'websocket receive time', 'best ask 1 s before signing; token mid move 60-300 s before', None, 'untested',
                              'live-only: 141 decisions with a recorded book so far; split: post-T0 days 0-1 BUILD, 2-3 VALIDATE'),
        'pm_maker_quote_ages': dim('Polymarket internal', 'have', 'B1 calldata maker orders (signing ms)', 'ms', 'on-chain',
                                   'age of the quotes it hits vs other takers in the same markets', None, 'inferred',
                                   'wallet hits older, non-fresh quotes: median 17.8 s vs 10.4 s, 65% of 636 paired markets, p 7e-16'),
        'pm_other_wallets': dim('Polymarket internal', 'have', 'tape proxyWallet', 'print', 'block time', 'same-token buys by others 0-30 s before',
                                None, 'untested', 'X1: no strong-form leader; staggered independent bots (different client fingerprints)'),
        'pm_listing_metadata': dim('Polymarket internal', 'have', 'Gamma markets (listing projection)', 'per market', 'at listing',
                                   'sportsMarketType, family, outcome label, fee rate', None, 'drives', 'part of the +0.02 gain over the baseline'),
        'pm_comments': dim('Polymarket internal', 'missing', 'Gamma /comments (parent_entity_type/id)', 'post', 'post time', None, None, 'untested', 'not fetched'),
        'pm_fees_rebates': dim('Polymarket internal', 'have', 'activity TAKER_REBATE rows, Gamma feeSchedule', 'daily', 'daily', None, None, 'untested',
                               'Gold taker tier; rebate share of PnL not computed (B6 open)'),
        'pm_operational_events': dim('Polymarket internal', 'missing', 'status page, engine restarts', 'event', 'minutes', None, None, 'untested', 'A8 open'),
        'pm_sibling_markets_same_event': dim('Related markets', 'proxy', 'tapes and live books of the same event', 'print / 200 ms', 'block / receive',
                                             'max sibling mid move 10-60 s before', None, 'untested',
                                             'iteration 1: low gain; live: siblings recorded only when a studied wallet traded them'),
        'sportsbook_inplay_odds': dim('Related markets', 'blocked', 'Pinnacle / Betfair / bet365 in-play APIs (keys)', 'sub-second', 'n/a', None, None,
                                      'untested', 'H3; proxy candidates: free odds aggregators, the odds recorded live by other agents are not used'),
        'kalshi_sports': dim('Related markets', 'missing', 'Kalshi public market data', 'trade', 'seconds', None, None, 'untested', 'A4b open'),
        'espn_soccer_keyevents': dim('Event state', 'have', 'ESPN site.api summary keyEvents (533 games)', 'wall clock, 1 s', 'wall clock; used +5 s',
                                     'goal_any / goal_lead in the 0-80 s after', None, 'drives',
                                     'E3: BUILD q<0.002 at both lag ranges; VALIDATE confirmed at core 600 s (Holm 0.01): peak 15-25 s, lift 2.5-3.5'),
        'pm_sports_websocket': dim('Event state', 'have', 'live lab sports feed (dev blocks)', 'message', 'receive time', 'score change 0-30 s before',
                                   None, 'untested', '241 decisions in covered games: 6.2% vs 3.7% of controls within 30 s; too few for a screen yet'),
        'official_data_feeds': dim('Event state', 'blocked', 'Sportradar / Genius / Opta live feeds (commercial)', 'sub-second', 'n/a', None, None, 'untested',
                                   'H2 upstream; the goal lag profile says the wallet is not faster than ESPN for goals'),
        'tennis_point_feed': dim('Event state', 'proxy', 'sports websocket tennis scores (live)', 'game/point', 'seconds', None, None, 'untested',
                                 'tennis is 30% of its orders; not screened yet'),
        'esports_round_feed': dim('Event state', 'proxy', 'sports websocket CS2/Valorant maps and scores', 'round', 'seconds', None, None, 'untested', ''),
        'video_stream': dim('Event state', 'missing', 'broadcast streams', 'frame', '10-40 s behind live', None, None, 'inferred',
                            'goal reaction peak 15-25 s after the ESPN wall clock fits a stream-paced trigger'),
        'news_social_tipsters': dim('Information', 'missing', 'Telegram previews, Reddit RSS, Bluesky (work); X blocked', 'post', 'post time', None, None,
                                    'untested', 'H7: a signal channel would show as bursts before the co-trader cluster'),
        'own_inventory': dim('Own state', 'have', 'activity (own fills)', 'fill', 'n/a', None, None, 'untested',
                             'conditioning only; both tokens bought in 23.6% of markets'),
        'own_pnl_drawdown': dim('Own state', 'proxy', 'activity + resolutions', 'day', 'n/a', None, None, 'untested', ''),
        'operator_time_of_day': dim('Operator', 'have', 'B1 signing times', 'ms', 'n/a', 'hour-of-day profile', None, 'inferred',
                                    'hours follow the sports calendar'),
        'operator_loop_cadence': dim('Operator', 'have', 'B1 signing ms', 'ms', 'n/a', 'signing ms mod 1000, s mod 10', None, 'untested',
                                     'uniform (KS p 0.20); no min_detectable_share yet, so not no_effect'),
        'infra_latency': dim('Infrastructure', 'have', 'B1 signing vs block; live own-trade receive time', 'ms', 'n/a',
                             'block - signing 3.05 s median; own trade reaches the recorder 0.05 s before its stamp (clock ahead ~0.3 s)',
                             None, 'inferred', 'not a latency racer'),
        'infra_api_outages': dim('Infrastructure', 'missing', 'Polymarket status history', 'event', 'minutes', None, None, 'untested', ''),
    }


def e3_rows(e3):
    out = []
    for period in ('BUILD', 'VALIDATE'):
        for lagset, rows in ((e3.get(period) or {}).get('screens') or {}).items():
            for r in rows:
                if period == 'BUILD':
                    ver = 'survivor (q<=0.10)' if r.get('q_bh', 1) <= 0.10 else 'not a survivor'
                else:
                    ver = ('confirmed (one-sided, Holm over 6 survivors, alpha 0.01)' if r['name'] in ('goal_any', 'goal_lead') and lagset == 'core600_10s'
                           else 'not confirmed / not a survivor')
                out.append(ind.ledger_row(f"espn_{r['name']}_{lagset}", 'espn_soccer_keyevents', f"ESPN keyEvents '{r['name']}' wall clocks",
                                          f'event at wall clock; {lagset}; units = games on disjoint timelines', dict(r), period, ver))
    return out

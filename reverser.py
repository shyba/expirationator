# coding: utf-8
from binascii import hexlify
from collections import Counter

import plyvel
import struct
import asyncio
import aiohttp
import ujson
import re

from lbryschema.decode import smart_decode
from lbryschema.uri import parse_lbry_uri
from lbryschema.error import DecodeError, URIParseError

from rpc import rpc


def update_db(app_db, names_db, height_db, expiring_height):
    values_db = plyvel.DB('db/claim_values/')
    outpoint_db = plyvel.DB('db/claim_outpoint/')
    def get_txid_for_claim_id(claim_id):
        txid_nout = outpoint_db.get(claim_id)
        txid = txid_nout[0:64]
        return txid
    expired_names, known_types, txids, expired_channels = {}, set(), {}, {}
    [app_db.delete(x[0]) for x in app_db]
    with app_db.write_batch() as writer:
        for (claim_id, height) in height_db:
            key = struct.pack('>I40s', int(height), claim_id)
            try:
                name = names_db.get(claim_id)
                parsed = parse_lbry_uri(name.decode('utf8'))
                decoded = smart_decode(values_db.get(claim_id))
                known_types.add(decoded.get('claimType', 'unknown'))
                if decoded.get('claimType') == 'certificateType' or parsed.is_channel:
                    expired_channels[name] = height
                if int(height) < expiring_height:
                    expired_names[name] = int(height)
                    txids[name] = get_txid_for_claim_id(claim_id)
                    writer.put(key, name)
            except (DecodeError, UnicodeDecodeError, URIParseError):
                continue
    return expired_names, known_types, txids, expired_channels


async def get_names(app_db, names_db, height_db):
    current_height = await rpc("getblockcount")
    expiring_height = current_height - 262974
    expired_names, types, expired_txids_by_name, expired_chan = update_db(app_db, names_db, height_db, expiring_height)
    trie = await rpc("getclaimsintrie")
    expiring_names = {}
    valid_expiring_names = {}
    renewed_names = {}
    expiring_channels = {}
    signed_expiring_claims = {}
    print(len(expired_names.keys()))

    for name, claims in [(r['name'], r['claims']) for r in trie]:
        max_height = max(int(c['height']) for c in claims)
        current_value = [c['value'] for c in claims if int(c['height']) == max_height][0]
        if max_height < (expiring_height + 576*90):  # ~90 days ahead
            expiring_names[name] = max_height
            try:
                parsed = parse_lbry_uri(name)
                decoded = smart_decode(current_value.encode('ISO-8859-1'))
                claim_type = decoded.get('claimType', 'unknown')
                if claim_type == 'certificateType' or parsed.is_channel:
                    expiring_channels[name] = max_height
                if decoded.signature:
                    signed_expiring_claims[name] = max_height
                types.add(claim_type)
                valid_expiring_names[name] = expiring_names[name]
            except DecodeError:
                print("Could not decode %s - %s" % (name, current_value.encode('ISO-8859-1')))
                pass
            except (UnicodeDecodeError, URIParseError, AssertionError) as e:
                print("Could not decode %s - %s" % (name, e))
                pass
        if name in expired_names:
            renewed_names[name] = expired_names.pop(name)
            print("removing %s as it is also claimed at %s" % (name, max_height))

    # verify for spent txs in expired set
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        for name in list(expired_names.keys()):
            txid = expired_txids_by_name[name]
            claims = await rpc("getclaimsfortx", [txid], session)
            if not claims:
                del expired_names[name]
                print("Spent expired: %s - %s" % (name, txid))

    [expired_chan.pop(name) for name in list(expired_chan.keys()) if name not in expired_names]
    for (key, name) in list(app_db.iterator()):
        if name not in expired_names:
            app_db.delete(key)

    print(len(expired_names.keys()))
    print(types)
    print("Renewed names: %s" %  len(renewed_names))
    print("Expired names: %s" %  len(expired_names))
    print("Expired channels: %s" %  len(expired_chan))
    print("Expiring names: %s" % len(expiring_names))
    print("Expiring channels: %s" % len(expiring_channels))
    print("Signed expiring names: %s" % len(signed_expiring_claims))
    print("Valid expiring names: %s" % len(valid_expiring_names))
    expired_stats = extract_stats(expired_names, 'expired')
    expired_chan_stats = extract_stats(expired_chan, 'expired channels')
    expiring_stats = extract_stats(expiring_names, 'expiring')
    expiring_channels_stats = extract_stats(expiring_channels, 'expiring channels')
    signed_expiring_stats = extract_stats(signed_expiring_claims, 'signed expiring channels')
    valid_expiring_stats = extract_stats(valid_expiring_names, 'valid and expiring')
    app_db.put(b'stats', ujson.dumps([expired_stats, expired_chan_stats, expiring_stats, valid_expiring_stats,
                                      expiring_channels_stats, signed_expiring_stats]).encode('utf8'))
    working_data = {'expired': sorted_values(expired_names), 'expiring': sorted_values(expiring_names),
                    'valid_expiring': sorted_values(valid_expiring_names),
                    'expired_channels': sorted_values(expired_chan),
                    'expiring_channels': sorted_values(expiring_channels),
                    'known_types': list(types), 'last_run_height': current_height}
    app_db.put(b'working_data', ujson.dumps(working_data).encode('utf8'))

def sorted_values(dictionary):
    return sorted((v, k) for (k, v) in dictionary.items())

def extract_stats(height_by_name_dict, stat_name):
    heights, stats = [], {'x': [], 'y': []}
    accumulated = 0
    for (height, sum) in sorted(Counter([height for (name, height) in height_by_name_dict.items()]).items()):
        accumulated += sum
        stats['x'].append(height)
        stats['y'].append(accumulated)
    stats['name'] = stat_name
    return stats

async def run_updater(app_db=None):
    height_db = plyvel.DB('db/claim_height/')
    names_db = plyvel.DB('db/claim_names/')
    app_db = app_db or plyvel.DB('db/height_claim/', create_if_missing=True)
    await get_names(app_db, names_db, height_db)
    height_db.close()
    names_db.close()


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run_updater())

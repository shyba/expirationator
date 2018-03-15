# coding: utf-8
import plyvel
import struct
import asyncio
import aiohttp
import ujson
import re
from rpc import rpc

height_db = plyvel.DB('db/claim_height/')
names_db = plyvel.DB('db/claim_names/')
app_db = plyvel.DB('db/height_claim/', create_if_missing=True)
expired_names = {}


def update_db(expiring_height):
    [app_db.delete(x[0]) for x in app_db]
    with app_db.write_batch() as writer:
        for (claim_id, height) in height_db:
            key = struct.pack('>I40s', int(height), claim_id)
            name = names_db.get(claim_id)
            writer.put(key, name)
            if int(height) < (expiring_height + 576*90):
                expired_names[name] = height


async def get_names():
    current_height = await rpc("getblockcount")
    expiring_height = current_height - 262974
    update_db(expiring_height)
    trie = await rpc("getclaimsintrie")
    expiring_names = {}
    renewed_names = {}
    print(len(expired_names.keys()))
    for name, claims in [(r['name'], r['claims']) for r in trie]:
        for claim in claims:
            height = claim['height']
            if height < (expiring_height + 576*90):  # ~90 days ahead
                expiring_names.setdefault(name, []).append(claim['height'])
            if name in expired_names:
                del expired_names[name]
                print("removing %s as it is also claimed at %s" % (name, height))
    print(len(expired_names.keys()))

    valid_name_char = "[a-zA-Z0-9\-]"  # these characters are the only valid name characters (from lbryschema:uri.py)
    valid_name_re = re.compile(valid_name_char)
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        for name in list(expired_names.keys()):
            try:
                if not valid_name_re.match(name.decode('utf8')): continue
            except UnicodeDecodeError:
                continue
            response = await rpc("getvalueforname", [name], session=session)
            height = response.get('height')
            if height and height > expiring_height:
                renewed_names[name] = height
                del expired_names[name]
    print("Renewed names: %s" %  len(renewed_names))
    print("Expired names: %s" %  len(expired_names))
    print("Expiring names: %s" % len(expiring_names))


loop = asyncio.get_event_loop()
loop.run_until_complete(get_names())
app_db.close()
height_db.close()
names_db.close()

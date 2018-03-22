import struct
import ujson
import asyncio

from rpc import rpc
from reverser import run_updater
from reverser import reclaim

from sanic import Sanic
from sanic import response
from sanic_jinja2 import SanicJinja2
import plyvel

db = plyvel.DB('db/height_claim')
app = Sanic(__name__)
jinja = SanicJinja2(app)
dbpacker = struct.Struct('>I40s')


def sorted_dump(start=None, stop=None):
    dump = []
    start, stop = ((struct.pack('>I', x) if x else None) for x in (start, stop))
    for (key, name) in db.iterator(start=start, stop=stop):
        if len(key) != dbpacker.size: continue
        height, claim_id = dbpacker.unpack(key)
        dump.append((height, claim_id, name))
    return dump


@app.route('/dump')
def dump_it(request):
    return response.json(sorted_dump())


@app.route('/dump/<start:int>/<stop:int>')
def dump_range(request, start, stop):
    return response.json(sorted_dump(start, stop))


@app.route('/stats')
def stats(request):
    return response.raw(db.get(b'stats'), content_type='application/json')


@app.route('/reclaim/<height:int>/<claim_id>')
async def reclaim_expired(request, height, claim_id):
    key = struct.pack('>I40s', height, claim_id.encode('utf8'))
    name = db.get(key)
    if not name:
        return response.json({'success': False, 'result': 'Unknown claim (database upgrade may be ongoing)'})
    return response.json(await reclaim(claim_id=claim_id.encode(), name=name))

@app.route('/reclaim_all')
async def reclaim_all(request):
    results = []
    for (height, claim_id, name) in sorted_dump():
        results.append(await reclaim(claim_id=claim_id, name=name))
    return response.json(results)


@app.route('/reclaim/<height:int>/<claim_id>/<name>')
async def reclaim_force(request, height, claim_id, name):
    return response.json(await reclaim(claim_id=claim_id.encode(), name=name.encode()))


@app.route('/')
@jinja.template('hello.html')
async def plot_it(request):
    current_height = rpc("getblockcount")
    working_data = ujson.loads(db.get(b'working_data'))
    current_height = await current_height
    wallet_address = await rpc("getaddressesbyaccount", [''])
    balance = await rpc("getbalance", ['', 0])
    return {'height': current_height, 'working_data': working_data, 'wallet_address': wallet_address, 'balance': balance}


async def schedule_db_update(last_height=None):
    last_height = last_height or int(ujson.loads(db.get(b'working_data', '{}')).get('last_run_height', 0))
    current_height = int(await rpc("getblockcount"))
    if (current_height % 10) == 0 and current_height != last_height:
        print("New block, running DB updater.")
        await run_updater(app_db=db)
    loop = app.loop
    loop.call_later(1, lambda: loop.create_task(schedule_db_update(current_height)))


if __name__ == '__main__':
    app.add_task(schedule_db_update)
    app.run(port=5000, debug=True)

import struct
import ujson

from rpc import rpc
from sanic import Sanic
from sanic import response
from sanic_jinja2 import SanicJinja2
from collections import OrderedDict
import plyvel

db = plyvel.DB('db/height_claim')
app = Sanic(__name__)
jinja = SanicJinja2(app)
dbpacker = struct.Struct('>I40s')


def sorted_dump(start=None, stop=None):
    dump = OrderedDict()
    start, stop = ((struct.pack('>I', x) if x else None) for x in (start, stop))
    for (key, name) in db.iterator(start=start, stop=stop):
        height, claim_id = dbpacker.unpack(key)
        dump.setdefault(height, {})[claim_id] = name
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


@app.route('/')
@jinja.template('hello.html')
async def plot_it(request):
    current_height = await rpc("getblockcount")
    return {'height': current_height}


if __name__ == '__main__':
    app.run(port=5000, debug=True)

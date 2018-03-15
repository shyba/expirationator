import struct

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


@app.route('/accumulated/<stop:int>')
def accumulate(request, stop):
    accumulated = 0
    result = {"x": [], "y": []}
    for k, v in sorted_dump(stop=stop).items():
        accumulated += len(v)
        result["x"].append(k)
        result["y"].append(accumulated)
    return response.json(result)


@app.route('/')
@jinja.template('hello.html')
async def plot_it(request):
    current_height = await rpc("getblockcount")
    return {'height': current_height}


if __name__ == '__main__':
    app.run(port=5000, debug=True)

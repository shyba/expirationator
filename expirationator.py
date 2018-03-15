import requests
from sanic import Sanic
from sanic import response
from sanic_jinja2 import SanicJinja2
from collections import OrderedDict
import plyvel
import msgpack

db = plyvel.DB('db/height_claim')
app = Sanic(__name__)
jinja = SanicJinja2(app)


def sorted_dump(start=None, stop=None):
    dump = OrderedDict()
    start, stop = ((x.encode() if x else None) for x in (start, stop))
    for (k, v) in db.iterator(start=start, stop=stop):
        dump[int(k)] = msgpack.loads(v)
    return dump


@app.route('/dump')
def dump_it(request):
    return response.json(sorted_dump())


@app.route('/dump/<start:int>/<stop:int>')
def dump_range(request, start, stop):
    start, stop = ('%06d' % (x) for x in (start, stop))
    return response.json(sorted_dump(start, stop))


@app.route('/accumulated/<stop:int>')
def accumulate(request, stop):
    stop = '%06d'%(stop)
    accumulated = 0
    result = {"x": [], "y": []}
    for k, v in sorted_dump(stop=stop).items():
        accumulated += len(v)
        result["x"].append(k)
        result["y"].append(accumulated)
    return response.json(result)


@app.route('/')
@jinja.template('hello.html')
def plot_it(request):
    height = max([block['Height'] for block in requests.get('https://explorer.lbry.io/api/v1/recentblocks').json()['blocks']])
    return {'height': height}


if __name__ == '__main__':
    app.run(port=5000, debug=True)

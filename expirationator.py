import requests
from flask import Flask
from flask import render_template
from collections import OrderedDict
import plyvel
import json

db = plyvel.DB('db/height_claim')
app = Flask(__name__)


def sorted_dump(start=None, stop=None):
    dump = OrderedDict()
    for (k, v) in db.iterator(start=start, stop=stop):
        dump[int(k)] = json.loads(v)
    return dump


@app.route('/dump')
def dump_it():
    return json.dumps(sorted_dump())


@app.route('/dump/<int:start>/<int:stop>')
def dump_range(start, stop):
    start, stop = ('%06d' % (x) for x in (start, stop))
    return json.dumps(sorted_dump(start, stop))


@app.route('/accumulated/<int:stop>')
def accumulate(stop):
    stop = '%06d'%(stop)
    accumulated = 0
    result = {"x":[], "y":[]}
    for k, v in sorted_dump(stop=stop).iteritems():
        accumulated += len(v)
        result["x"].append(k)
        result["y"].append(accumulated)
    return json.dumps(result)


@app.route('/')
def plot_it():
    height = max([block['Height'] for block in requests.get('https://explorer.lbry.io/api/v1/recentblocks').json()['blocks']])
    return render_template('hello.html', height=height)


if __name__ == '__main__':
    app.run()

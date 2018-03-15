# coding: utf-8
import plyvel
import json

db = plyvel.DB('db/claim_height/')
by_height = {}
for (k,v) in db:
    by_height.setdefault('%06d'%int(v), []).append(k)
    
db2 = plyvel.DB('db/height_claim/', create_if_missing=True)
[db2.delete(x[0]) for x in db2]
for (k,v) in by_height.iteritems():
    with db2.write_batch() as writer:
        writer.put(k, json.dumps(v))
        
db2.close()
db.close()

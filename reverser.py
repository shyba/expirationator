# coding: utf-8
import plyvel
import msgpack

height_db = plyvel.DB('db/claim_height/')
names_db = plyvel.DB('db/claim_names/')
by_height = {}
for (claim_id, height) in height_db:
    value = (claim_id, names_db.get(claim_id))
    by_height.setdefault(b'%06d' % int(height), []).append(value)
    
app_db = plyvel.DB('db/height_claim/', create_if_missing=True)
[app_db.delete(x[0]) for x in app_db]
for (k, v) in by_height.items():
    with app_db.write_batch() as writer:
        writer.put(k, msgpack.dumps(v))
        
app_db.close()
height_db.close()
names_db.close()

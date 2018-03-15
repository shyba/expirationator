# coding: utf-8
import plyvel
import struct

height_db = plyvel.DB('db/claim_height/')
names_db = plyvel.DB('db/claim_names/')
app_db = plyvel.DB('db/height_claim/', create_if_missing=True)

[app_db.delete(x[0]) for x in app_db]
with app_db.write_batch() as writer:
    for (claim_id, height) in height_db:
        key = struct.pack('>I40s', int(height), claim_id)
        writer.put(key, names_db.get(claim_id))

app_db.close()
height_db.close()
names_db.close()

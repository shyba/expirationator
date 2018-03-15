import aiohttp
import ujson


async def rpc(method, params=None, session=None):
    data = {"jsonrpc":"1.0","id":"0","method": method,"params":list(params or [])}
    if session:
        async with session.post('http://lbry:lbry@localhost:9245/', json=data) as resp:
            result = (await resp.json())
            return result['error'] or result['result']
    async with aiohttp.ClientSession(json_serialize=ujson.dumps) as session:
        async with session.post('http://lbry:lbry@localhost:9245/', json=data) as resp:
            result = (await resp.json())
            return result['error'] or result['result']

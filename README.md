# buildRedis
basic implementation of redis
Run the server and in a new tab open a python interpreter

run    
>from server import Client
>client = Client()

You can then run set like:
>client.set('foo', 'bar')
-Supports strings, arrays, dicts and integers

You can multi set like:
>client.mset('foo', 'bar', 'fizz', ['buzz1', 'buzz2'])

Get from index:
>client.get('foo')

Delete from index:
>client.delete('foo')


TODO: Fix issue with _write needing to be cast as byte
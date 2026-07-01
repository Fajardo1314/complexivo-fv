import urllib.request, json

# Clean nodes we accidentally created in companion's DB (aula-4587b)
db_url = 'https://aula-4587b-default-rtdb.firebaseio.com'
nodes_to_delete = ['inventario', 'usuarios_sistema', 'configuracion', 'sistema', 'auditoria', 'retiros', 'estado_foco', 'aforo', 'movimiento_pir', 'monitoreo', 'monitoreo_tiempo_real', 'equipos', 'docentes', 'usuarios_plataforma']

for node in nodes_to_delete:
    try:
        req = urllib.request.Request(db_url + '/' + node + '.json', method='DELETE')
        resp = urllib.request.urlopen(req)
        print('DELETED: ' + node + ' -> ' + resp.read().decode())
    except Exception as e:
        print('SKIP ' + node + ': ' + str(e))

# Check what remains
req = urllib.request.Request(db_url + '/.json')
resp = urllib.request.urlopen(req)
data = json.loads(resp.read().decode())
keys = list(data.keys()) if data else []
print('\nRemaining nodes in aula-4587b: ' + str(keys))
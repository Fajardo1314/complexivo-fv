import os

fpath = os.path.join('Proyecto_grado', 'web_dashboard', 'app.js')
with open(fpath, 'r', encoding='utf-8') as f:
    c = f.read()

replacements = [
    ("ref(db, 'monitoreo/pir')", "ref(db, 'movimiento_pir')"),
    ("ref(db, 'monitoreo/estado_pir')", "ref(db, 'movimiento_pir')"),
    ("ref(db, 'monitoreo/puerta')", "ref(db, 'puerta_fisica/estado')"),
    ("ref(db, 'monitoreo/estado_puerta')", "ref(db, 'puerta_fisica/estado')"),
    ("ref(db, 'monitoreo/infrarrojo')", "ref(db, 'aforo')"),
    ("ref(db, 'monitoreo/aforo_actual')", "ref(db, 'aforo')"),
    ("ref(db, 'monitoreo/estado_foco')", "ref(db, 'movimiento_pir')"),
    ("ref(db, 'monitoreo/ultimo_uid_no_registrado')", "ref(db, 'ultimo_uid_no_registrado')"),
    ("ref(db, 'monitoreo/ultimo_intento_invalido')", "ref(db, 'ultimo_intento_invalido')"),
    ('/monitoreo/pir', '/movimiento_pir'),
    ('/monitoreo/infrarrojo', '/aforo'),
    ('/monitoreo/puerta', '/puerta_fisica/estado'),
]

count = 0
for old, new in replacements:
    n = c.count(old)
    if n > 0:
        c = c.replace(old, new)
        count += n
        print(f'  {old} -> {new} ({n}x)')

with open(fpath, 'w', encoding='utf-8') as f:
    f.write(c)
print(f'\nTotal: {count} replacements done')
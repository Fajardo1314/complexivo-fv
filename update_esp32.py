import os

fpath = os.path.join('Proyecto_grado', 'esp32_firmware', 'esp32_firmware.ino')
with open(fpath, 'r', encoding='utf-8') as f:
    c = f.read()

replacements = [
    ('"complexivo-fv-default-rtdb.firebaseio.com"', '"aula-4587b-default-rtdb.firebaseio.com"'),
    ('const char *TOPIC_PIR = "monitoreo/pir"', 'const char *TOPIC_PIR = "movimiento_pir"'),
    ('const char *TOPIC_AFORO = "monitoreo/infrarrojo"', 'const char *TOPIC_AFORO = "aforo"'),
    ('const char *TOPIC_PUERTA = "monitoreo/puerta"', 'const char *TOPIC_PUERTA = "puerta_fisica/estado"'),
    ('const char *TOPIC_RFID = "monitoreo/rfid"', 'const char *TOPIC_RFID = "accesos"'),
    ('"/monitoreo/pir"', '"/movimiento_pir"'),
    ('"/monitoreo/infrarrojo"', '"/aforo"'),
    ('"/monitoreo/puerta"', '"/puerta_fisica/estado"'),
    ('"/monitoreo/rfid"', '"/accesos"'),
    ('# Condensar URI limpia: /monitoreo/pir.json', '# Construir URI limpia'),
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
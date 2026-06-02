import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from ssh_raspberry import RaspberrySSH
from credentials import SSH_HOST_LOCAL

with RaspberrySSH(host=SSH_HOST_LOCAL) as rpi:
    # Descomentar dtparam=spi=on
    print("Descomentando dtparam=spi=on en /boot/config.txt...")
    out = rpi.ejecutar_sudo("sed -i 's/^# dtparam=spi=on/dtparam=spi=on/' /boot/config.txt")
    print("Hecho:", out.encode('ascii','replace').decode('ascii') or "(sin salida)")

    # Verificar que se aplico
    check = rpi.ejecutar("grep 'dtparam=spi=on' /boot/config.txt")
    print("Verificacion:", check.encode('ascii','replace').decode('ascii'))

    # Ademas habilitar modulo en /etc/modules-load.d
    rpi.ejecutar_sudo("echo 'spi_bcm2835' > /etc/modules-load.d/spi.conf")
    print("Modulo spi_bcm2835 registrado en /etc/modules-load.d/spi.conf")

    print("\nReiniciando la Raspberry Pi...")
    rpi.ejecutar_sudo("reboot")
    print("Raspberry Pi se esta reiniciando. Disponible en ~30 segundos.")

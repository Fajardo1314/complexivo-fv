import paramiko, sys, time
sys.path.insert(0, 'Proyecto_grado')
from credentials import SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, timeout=15)

def run(cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(f"echo '{SSH_PASSWORD}' | sudo -S {cmd}", timeout=timeout)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'[CMD] {cmd}')
    if out: print(f'  OUT: {out}')
    if err and 'password' not in err.lower(): print(f'  ERR: {err}')
    return out, err

print("=" * 50)
print("  CONFIGURACION DE RED - RASPBERRY PI")
print("=" * 50)

# --- 1. NAT / IP FORWARDING ---
print("\n[1] Configurando NAT e IP Forwarding...")

# Detect interfaces
run('ip link show | grep -E "eth0|wlan0"')

# Enable IP forwarding
run('sysctl -w net.ipv4.ip_forward=1')
run('grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf')

# Flush and apply iptables NAT rules
run('iptables -t nat -F POSTROUTING')
run('iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE')
run('iptables -F FORWARD')
run('iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT')
run('iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT')

# Persist iptables
run('sh -c "iptables-save > /etc/iptables.ipv4.nat"')
run("sh -c \"sed -i '/iptables-restore/d' /etc/rc.local\"")
run("sh -c \"sed -i '/^exit 0/i iptables-restore < /etc/iptables.ipv4.nat' /etc/rc.local\"")

print("  [OK] NAT configurado.")

# --- 2. MOSQUITTO CONFIG ---
print("\n[2] Verificando configuracion de Mosquitto...")

# Check current mosquitto.conf
run('cat /home/user/proyecto_grado/mosquitto/config/mosquitto.conf')

# Ensure bind_address is 0.0.0.0 and allow_anonymous true
run("sh -c \"grep -q '^bind_address' /home/user/proyecto_grado/mosquitto/config/mosquitto.conf || echo 'bind_address 0.0.0.0' >> /home/user/proyecto_grado/mosquitto/config/mosquitto.conf\"")
run("sh -c \"grep -q '^allow_anonymous' /home/user/proyecto_grado/mosquitto/config/mosquitto.conf || echo 'allow_anonymous true' >> /home/user/proyecto_grado/mosquitto/config/mosquitto.conf\"")
run("sh -c \"sed -i 's/^bind_address .*/bind_address 0.0.0.0/' /home/user/proyecto_grado/mosquitto/config/mosquitto.conf\"")
run("sh -c \"sed -i 's/^allow_anonymous .*/allow_anonymous true/' /home/user/proyecto_grado/mosquitto/config/mosquitto.conf\"")

print("\n  Configuracion final de mosquitto.conf:")
run('cat /home/user/proyecto_grado/mosquitto/config/mosquitto.conf')

# --- 3. RESTART DOCKER CONTAINERS ---
print("\n[3] Reiniciando contenedores Docker...")
run('cd /home/user/proyecto_grado && docker-compose restart mosquitto', timeout=60)
time.sleep(5)

# --- 4. VERIFY ---
print("\n[4] Verificaciones finales...")

# Check Mosquitto is listening on 0.0.0.0:1883
run('ss -tlnp | grep 1883')

# Check NAT rules
run('iptables -t nat -L POSTROUTING -v -n')

# Check IP forwarding
run('sysctl net.ipv4.ip_forward')

# Check containers
run('docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"')

# Test internet from RPi
run('ping -c 1 -W 2 8.8.8.8')

client.close()
print("\n[OK] Configuracion completada. El ESP32 deberia tener internet y MQTT accesible.")
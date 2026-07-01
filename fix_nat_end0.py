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

WAN = "end0"
LAN = "wlan0"

print(f"=== CORRIGIENDO NAT: {WAN} -> {LAN} ===\n")

# Flush old rules
run('iptables -t nat -F POSTROUTING')
run('iptables -F FORWARD')

# Apply correct NAT rules with end0
run(f'iptables -t nat -A POSTROUTING -o {WAN} -j MASQUERADE')
run(f'iptables -A FORWARD -i {WAN} -o {LAN} -m state --state RELATED,ESTABLISHED -j ACCEPT')
run(f'iptables -A FORWARD -i {LAN} -o {WAN} -j ACCEPT')

# Persist
run('sh -c "iptables-save > /etc/iptables.ipv4.nat"')

# Verify
print('\n=== VERIFICACION ===')
run('iptables -t nat -L POSTROUTING -v -n')
run('iptables -L FORWARD -v -n')
run('ping -c 2 -W 2 8.8.8.8')

client.close()
print('\n[OK] NAT corregido con end0 como interfaz WAN.')
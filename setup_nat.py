import paramiko, sys
sys.path.insert(0, 'Proyecto_grado')
from credentials import SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo '{SSH_PASSWORD}' | sudo -S {cmd}", timeout=30)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f'[CMD] {cmd}')
    if out: print(f'  OUT: {out}')
    if err and 'password' not in err.lower(): print(f'  ERR: {err}')
    return out, err

# 1. Enable IP forwarding
run('sysctl -w net.ipv4.ip_forward=1')

# 2. Enable persistent IP forwarding
run('grep -q "net.ipv4.ip_forward=1" /etc/sysctl.conf || echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf')

# 3. Flush old iptables NAT rules
run('iptables -t nat -F')

# 4. Add NAT masquerade rule: forward from eth0 to wlan0
run('iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE')
run('iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT')
run('iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT')

# 5. Persist iptables rules
run('iptables-save > /etc/iptables.ipv4.nat')

# 6. Persist restore in rc.local
run("sed -i '/iptables-restore/d' /etc/rc.local")
run("sed -i '/^exit 0/i iptables-restore < /etc/iptables.ipv4.nat' /etc/rc.local")

# 7. Verify
print()
print('=== VERIFICACION ===')
run('sysctl net.ipv4.ip_forward')
run('iptables -t nat -L POSTROUTING -v -n')

client.close()
print('[OK] NAT/IP Forwarding configurado y persistido.')
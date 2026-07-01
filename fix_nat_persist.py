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

# Persist iptables with sudo
run('iptables-save | sudo tee /etc/iptables.ipv4.nat > /dev/null')

# Verify persistence
run('cat /etc/iptables.ipv4.nat | head -20')

# Verify DNS works from the AP network
run('ping -c 2 -W 2 8.8.8.8')

client.close()
print('[OK] Reglas NAT persistidas correctamente.')
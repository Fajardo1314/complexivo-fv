import paramiko, sys
sys.path.insert(0, 'Proyecto_grado')
from credentials import SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, timeout=15)

def run(cmd):
    stdin, stdout, stderr = client.exec_command(f"echo '{SSH_PASSWORD}' | sudo -S {cmd}", timeout=15)
    return stdout.read().decode().strip()

print('=== INTERFACES ===')
print(run('ip -br addr show'))
print()
print('=== DEFAULT ROUTE ===')
print(run('ip route show default'))
print()
print('=== ALL INTERFACES ===')
print(run('ip link show | grep -E "^[0-9]"'))

client.close()
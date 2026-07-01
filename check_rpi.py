import paramiko, sys
sys.path.insert(0, 'Proyecto_grado')
from credentials import SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(SSH_HOST, SSH_PORT, SSH_USER, SSH_PASSWORD, timeout=10)
stdin, stdout, stderr = c.exec_command('hostname && uptime && docker ps --format "table {{.Names}}\t{{.Status}}"')
print(stdout.read().decode())
c.close()
print('[OK] Raspberry Pi conectada y funcionando')
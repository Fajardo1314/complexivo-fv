"""
ssh_raspberry.py
================
Cliente SSH para la Raspberry Pi del Proyecto de Grado.

Funcionalidades:
    - Conectar a la Raspberry por SSH (vía Netbird VPN o red local)
    - Ejecutar comandos individuales y obtener su salida
    - Sesión interactiva (shell en tiempo real)
    - Enviar y recibir datos a través de un canal persistente
    - Transferir archivos (upload / download) con SFTP

Dependencias:
    pip install paramiko

Uso rápido:
    python ssh_raspberry.py                   # Sesión interactiva
    python ssh_raspberry.py "ls -la /home"    # Ejecutar un comando y salir
"""

import sys
import time
import threading
import paramiko

# ── Importar credenciales centralizadas ───────────────────────────────────────
try:
    from credentials import SSH_HOST, SSH_USER, SSH_PASSWORD, SSH_PORT
except ImportError:
    # Fallback si se ejecuta sin credentials.py
    SSH_HOST     = "raspberryfv.netbird.cloud"
    SSH_USER     = "user"
    SSH_PASSWORD = "taipt"
    SSH_PORT     = 22


# ══════════════════════════════════════════════════════════════════════════════
#  CLASE PRINCIPAL: RaspberrySSH
# ══════════════════════════════════════════════════════════════════════════════

class RaspberrySSH:
    """
    Cliente SSH de alto nivel para la Raspberry Pi.

    Ejemplo de uso:
        with RaspberrySSH() as rpi:
            salida = rpi.ejecutar("uname -a")
            print(salida)
    """

    def __init__(
        self,
        host: str      = SSH_HOST,
        user: str      = SSH_USER,
        password: str  = SSH_PASSWORD,
        port: int      = SSH_PORT,
        timeout: float = 10.0,
    ):
        self.host     = host
        self.user     = user
        self.password = password
        self.port     = port
        self.timeout  = timeout

        self._client:  paramiko.SSHClient  | None = None
        self._shell:   paramiko.Channel    | None = None   # canal interactivo

    # ── Conexión / desconexión ─────────────────────────────────────────────

    def conectar(self) -> "RaspberrySSH":
        """Establece la conexión SSH con la Raspberry Pi."""
        print(f"[SSH] Conectando a {self.user}@{self.host}:{self.port} ...")
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self._client.connect(
            hostname=self.host,
            port=self.port,
            username=self.user,
            password=self.password,
            timeout=self.timeout,
            allow_agent=False,
            look_for_keys=False,
        )
        print("[SSH] [OK] Conexion establecida.")
        return self

    def desconectar(self):
        """Cierra el canal interactivo y la conexion SSH."""
        if self._shell:
            self._shell.close()
            self._shell = None
        if self._client:
            self._client.close()
            self._client = None
        print("[SSH] Conexion cerrada.")

    # ── Context manager ────────────────────────────────────────────────────

    def __enter__(self) -> "RaspberrySSH":
        return self.conectar()

    def __exit__(self, *_):
        self.desconectar()

    # ── Ejecutar un comando y retornar salida ──────────────────────────────

    def ejecutar(self, comando: str, timeout: float = 30.0) -> str:
        """
        Ejecuta un comando en la Raspberry y devuelve su salida (stdout + stderr).

        Args:
            comando: Comando a ejecutar en bash.
            timeout: Tiempo máximo de espera en segundos.

        Returns:
            str con la salida combinada del comando.

        Ejemplo:
            rpi.ejecutar("systemctl status netbird")
        """
        if not self._client:
            raise RuntimeError("No hay conexión SSH activa. Llama a conectar() primero.")

        stdin, stdout, stderr = self._client.exec_command(comando, timeout=timeout)
        salida = stdout.read().decode("utf-8", errors="replace")
        error  = stderr.read().decode("utf-8", errors="replace")

        if error.strip():
            salida += f"\n[STDERR]\n{error}"
        return salida.strip()

    def ejecutar_sudo(self, comando: str, timeout: float = 30.0) -> str:
        """
        Ejecuta un comando con sudo, inyectando la contraseña automáticamente.

        Ejemplo:
            rpi.ejecutar_sudo("systemctl restart netbird")
        """
        return self.ejecutar(
            f"echo '{self.password}' | sudo -S {comando}",
            timeout=timeout,
        )

    # ── Enviar / recibir datos por canal persistente ───────────────────────

    def abrir_shell(self, cols: int = 200, rows: int = 50):
        """
        Abre un shell interactivo persistente (canal PTY).
        Usa send() y recibir() para comunicarte con él.
        """
        if not self._client:
            raise RuntimeError("No hay conexión SSH activa.")
        self._shell = self._client.invoke_shell(term="xterm", width=cols, height=rows)
        self._shell.settimeout(5.0)
        time.sleep(0.5)                 # dejar que el prompt aparezca
        self._limpiar_buffer()
        print("[SSH] Shell interactiva abierta.")

    def enviar(self, texto: str, enter: bool = True):
        """
        Envía texto (comando o datos) al shell interactivo.

        Args:
            texto:  Texto a enviar.
            enter:  Si True, añade '\\n' al final (simula Enter).
        """
        if not self._shell:
            raise RuntimeError("Shell no abierta. Llama a abrir_shell() primero.")
        payload = texto + ("\n" if enter else "")
        self._shell.send(payload)

    def recibir(self, espera: float = 1.5, chunk: int = 4096) -> str:
        """
        Recibe la salida disponible en el shell interactivo.

        Args:
            espera: Segundos a esperar por más datos antes de retornar.
            chunk:  Tamaño de cada lectura en bytes.

        Returns:
            str con todo lo recibido.
        """
        if not self._shell:
            raise RuntimeError("Shell no abierta. Llama a abrir_shell() primero.")

        time.sleep(espera)
        buffer = b""
        while self._shell.recv_ready():
            buffer += self._shell.recv(chunk)
        return buffer.decode("utf-8", errors="replace")

    def enviar_y_recibir(self, texto: str, espera: float = 1.5) -> str:
        """
        Envía un comando al shell interactivo y retorna la respuesta.

        Ejemplo:
            respuesta = rpi.enviar_y_recibir("netbird status")
            print(respuesta)
        """
        self.enviar(texto)
        return self.recibir(espera=espera)

    def _limpiar_buffer(self):
        """Vacía el buffer inicial del shell (mensajes de bienvenida, etc.)."""
        time.sleep(0.5)
        while self._shell.recv_ready():
            self._shell.recv(4096)

    # ── Transferencia de archivos (SFTP) ───────────────────────────────────

    def subir_archivo(self, ruta_local: str, ruta_remota: str):
        """
        Sube un archivo local a la Raspberry Pi.

        Args:
            ruta_local:  Ruta del archivo en tu máquina.
            ruta_remota: Ruta de destino en la Raspberry.

        Ejemplo:
            rpi.subir_archivo("config.py", "/home/user/config.py")
        """
        if not self._client:
            raise RuntimeError("No hay conexión SSH activa.")
        sftp = self._client.open_sftp()
        sftp.put(ruta_local, ruta_remota)
        sftp.close()
        print(f"[SFTP] [UP] '{ruta_local}' -> '{ruta_remota}'")

    def descargar_archivo(self, ruta_remota: str, ruta_local: str):
        """
        Descarga un archivo de la Raspberry Pi.

        Args:
            ruta_remota: Ruta del archivo en la Raspberry.
            ruta_local:  Ruta de destino en tu máquina.

        Ejemplo:
            rpi.descargar_archivo("/var/log/syslog", "syslog_local.txt")
        """
        if not self._client:
            raise RuntimeError("No hay conexión SSH activa.")
        sftp = self._client.open_sftp()
        sftp.get(ruta_remota, ruta_local)
        sftp.close()
        print(f"[SFTP] [DOWN] '{ruta_remota}' -> '{ruta_local}'")


# ══════════════════════════════════════════════════════════════════════════════
#  SESIÓN INTERACTIVA EN TERMINAL
# ══════════════════════════════════════════════════════════════════════════════

def _hilo_recibir(shell: paramiko.Channel, stop_event: threading.Event):
    """Hilo secundario que imprime en tiempo real todo lo que llega del servidor."""
    while not stop_event.is_set():
        if shell.recv_ready():
            datos = shell.recv(4096).decode("utf-8", errors="replace")
            print(datos, end="", flush=True)
        else:
            time.sleep(0.05)


def sesion_interactiva(rpi: RaspberrySSH):
    """
    Lanza una sesión de terminal interactiva en la consola local.
    Escribe comandos directamente; escribe 'exit' o Ctrl+C para salir.
    """
    rpi.abrir_shell()
    stop = threading.Event()
    hilo = threading.Thread(target=_hilo_recibir, args=(rpi._shell, stop), daemon=True)
    hilo.start()

    print("\n[SSH] Sesión interactiva — escribe 'exit' o presiona Ctrl+C para salir.\n")
    try:
        while True:
            cmd = input()          # leer del teclado
            rpi.enviar(cmd)
            if cmd.strip() in ("exit", "logout"):
                break
    except KeyboardInterrupt:
        print("\n[SSH] Interrupción por usuario.")
    finally:
        stop.set()
        hilo.join(timeout=1)


# ══════════════════════════════════════════════════════════════════════════════
#  EJEMPLOS DE USO — PUNTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def demo_comandos(rpi: RaspberrySSH):
    """Ejecuta una batería de comandos de demostración."""
    comandos = [
        ("Sistema",        "uname -a"),
        ("Uptime",         "uptime"),
        ("Estado Netbird", "netbird status"),
        ("Red (IP)",       "ip addr show wt0 2>/dev/null || echo 'Interfaz wt0 no encontrada'"),
        ("MQTT activo",    "ss -tulpn | grep 1883 || echo 'Sin broker MQTT activo'"),
        ("Disco",          "df -h /"),
        ("Memoria",        "free -h"),
    ]

    print("\n" + "═" * 60)
    print("  DIAGNÓSTICO RÁPIDO — Raspberry Pi")
    print("═" * 60)

    for nombre, cmd in comandos:
        print(f"\n {nombre}: {cmd}")
        print("─" * 40)
        salida = rpi.ejecutar(cmd)
        print(salida or "(sin salida)")

    print("\n" + "═" * 60)


if __name__ == "__main__":
    # ── Si se pasa un argumento, ejecutar ese comando y salir ─────────────
    if len(sys.argv) > 1:
        comando_cli = " ".join(sys.argv[1:])
        with RaspberrySSH() as rpi:
            print(rpi.ejecutar(comando_cli))
        sys.exit(0)

    # ── Sin argumentos: menú de opciones ─────────────────────────────────
    print("\n╔══════════════════════════════════════════╗")
    print("║   SSH Client — Raspberry Pi 4B           ║")
    print("║   Host: " + SSH_HOST.ljust(34) + "║")
    print("╚══════════════════════════════════════════╝")
    print("\n¿Qué deseas hacer?")
    print("  [1] Sesión interactiva (terminal)")
    print("  [2] Diagnóstico rápido (batería de comandos)")
    print("  [3] Ejecutar un comando personalizado")
    print("  [q] Salir")

    opcion = input("\nOpción: ").strip().lower()

    if opcion == "q":
        sys.exit(0)

    with RaspberrySSH() as rpi:
        if opcion == "1":
            sesion_interactiva(rpi)

        elif opcion == "2":
            demo_comandos(rpi)

        elif opcion == "3":
            cmd = input("Comando a ejecutar: ").strip()
            if cmd:
                print("\n" + rpi.ejecutar(cmd))
            else:
                print("Comando vacío.")

        else:
            print("Opción no reconocida.")

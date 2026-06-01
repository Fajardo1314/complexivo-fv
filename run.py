import subprocess
import sys
import time
import os

def main():
    print("[RUN] Iniciando el Sistema Maestro IoT...")
    
    # Obtener el directorio base de run.py
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    try:
        # Iniciar main_control.py (Servidor Flask, RFID, Relé)
        print("[RUN] Lanzando main_control.py...")
        control_path = os.path.join(base_dir, "main_control.py")
        control_process = subprocess.Popen([sys.executable, control_path], cwd=base_dir)
        
        # Iniciar automation.py (Control TP-Link, LDR, Horarios)
        print("[RUN] Lanzando automation.py...")
        automation_path = os.path.join(base_dir, "automation.py")
        automation_process = subprocess.Popen([sys.executable, automation_path], cwd=base_dir)
        
        print("[RUN] Sistema ejecutándose. Presione Ctrl+C para detener todo.")
        
        # Mantener el script principal corriendo
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n[RUN] Señal de apagado detectada (Ctrl+C).")
    finally:
        print("[RUN] Terminando subprocesos...")
        if 'control_process' in locals() and control_process.poll() is None:
            control_process.terminate()
        if 'automation_process' in locals() and automation_process.poll() is None:
            automation_process.terminate()
            
        print("[RUN] Esperando a que finalicen...")
        if 'control_process' in locals():
            control_process.wait()
        if 'automation_process' in locals():
            automation_process.wait()
            
        print("[RUN] Sistema detenido limpiamente.")

if __name__ == "__main__":
    main()

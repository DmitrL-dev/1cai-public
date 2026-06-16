import shutil
import os

def check_command(cmd):
    path = shutil.which(cmd)
    if path:
        print(f"✅ {cmd}: Found at {path}")
        return True
    else:
        print(f"❌ {cmd}: NOT FOUND")
        return False

def check_socket():
    if os.path.exists("/var/run/docker.sock"):
        print("✅ Docker Socket: Found")
        return True
    else:
        print("❌ Docker Socket: NOT FOUND (Cannot control Docker from here)")
        return False

print("🔍 Environment Verification for Battle Mode")
print("=========================================")

has_docker = check_command("docker")
has_compose = check_command("docker-compose") or (has_docker and os.system("docker compose version > /dev/null 2>&1") == 0)
has_python = check_command("python3")
has_socket = check_socket()

print("\n📋 Summary:")
if has_docker and has_socket:
    print("🚀 You are ready to launch Battle Mode!")
    print("   Run: ./scripts/start_battle_mode.sh")
else:
    print("⚠️  Environment incomplete.")
    print("   To run Battle Mode, please execute ./scripts/start_battle_mode.sh")
    print("   FROM YOUR HOST MACHINE (not inside this DevContainer).")


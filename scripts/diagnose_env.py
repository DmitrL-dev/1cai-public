import os
import sys
import platform
import socket

def check_environment():
    print(f"OS: {os.name}")
    print(f"Platform: {sys.platform}")
    print(f"System: {platform.system()}")
    print(f"Release: {platform.release()}")
    
    # Check for .dockerenv
    if os.path.exists('/.dockerenv'):
        print("✅ Found /.dockerenv (Likely inside Docker)")
    else:
        print("❌ /.dockerenv not found")

    # Check cgroups (Linux only)
    if os.path.exists('/proc/1/cgroup'):
        try:
            with open('/proc/1/cgroup', 'rt') as f:
                content = f.read()
                if 'docker' in content or 'kubepods' in content:
                    print("✅ 'docker' or 'kubepods' found in /proc/1/cgroup")
                else:
                    print("ℹ️ /proc/1/cgroup exists but no obvious docker indicators")
        except Exception as e:
            print(f"⚠️ Could not read /proc/1/cgroup: {e}")
    else:
        print("ℹ️ /proc/1/cgroup not found (Not Linux or not accessible)")

    # Check environment variables
    if os.environ.get('KUBERNETES_SERVICE_HOST'):
        print("✅ KUBERNETES_SERVICE_HOST is set")
    
    if os.environ.get('DOCKER_HOST'):
        print(f"ℹ️ DOCKER_HOST is set to: {os.environ.get('DOCKER_HOST')}")

    # Check network
    try:
        host_ip = socket.gethostbyname('host.docker.internal')
        print(f"✅ Resolved host.docker.internal to {host_ip}")
    except socket.gaierror:
        print("❌ Could not resolve host.docker.internal")

    try:
        localhost_ip = socket.gethostbyname('localhost')
        print(f"ℹ️ localhost resolves to {localhost_ip}")
    except:
        pass

if __name__ == "__main__":
    check_environment()

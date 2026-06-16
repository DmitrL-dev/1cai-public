import logging
import subprocess
import os
import json
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

class RasClient:
    """
    Wrapper for 1C 'rac' utility (Remote Administration Client).
    Allows managing 1C clusters via RAS protocol.
    """

    def __init__(self, rac_path: Optional[str] = None, ras_host: str = "localhost", ras_port: int = 1545):
        self.rac_path = rac_path or os.getenv("ONEC_RAC_PATH", "rac")
        self.ras_host = ras_host or os.getenv("ONEC_RAS_HOST", "localhost")
        self.ras_port = ras_port or int(os.getenv("ONEC_RAS_PORT", "1545"))
        self.auth_user = os.getenv("ONEC_CLUSTER_ADMIN", "")
        self.auth_pwd = os.getenv("ONEC_CLUSTER_PWD", "")

    def _run_command(self, args: List[str]) -> str:
        """Executes rac command and returns output."""
        cmd = [self.rac_path, *args, f"{self.ras_host}:{self.ras_port}"]
        
        # Add auth if provided (this depends on specific rac command syntax, 
        # usually auth is per-cluster or per-infobase, handled in specific methods)
        
        try:
            logger.debug(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', # Ensure correct encoding for 1C output
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"RAC command failed: {e.stderr}")
            raise RuntimeError(f"RAC error: {e.stderr}")
        except FileNotFoundError:
            logger.error(f"RAC utility not found at {self.rac_path}")
            raise RuntimeError(f"RAC utility not found at {self.rac_path}")

    def get_clusters(self) -> List[Dict[str, str]]:
        """Returns list of clusters."""
        # Output format of rac is usually text, parsing is required.
        # rac cluster list
        output = self._run_command(["cluster", "list"])
        return self._parse_rac_list(output)

    def get_sessions(self, cluster_id: str) -> List[Dict[str, str]]:
        """Returns list of sessions for a cluster."""
        # rac session list --cluster=<id>
        args = ["session", "list", f"--cluster={cluster_id}"]
        if self.auth_user:
             args.extend([f"--cluster-user={self.auth_user}", f"--cluster-pwd={self.auth_pwd}"])
             
        output = self._run_command(args)
        return self._parse_rac_list(output)

    def terminate_session(self, cluster_id: str, session_id: str, message: str = "Terminated by AI Admin"):
        """Terminates a specific session."""
        # rac session terminate --cluster=<id> --session=<id> --error-message=<msg>
        args = [
            "session", "terminate", 
            f"--cluster={cluster_id}", 
            f"--session={session_id}",
            f"--error-message={message}"
        ]
        if self.auth_user:
             args.extend([f"--cluster-user={self.auth_user}", f"--cluster-pwd={self.auth_pwd}"])

        self._run_command(args)

    def _parse_rac_list(self, output: str) -> List[Dict[str, str]]:
        """
        Parses standard rac output which looks like:
        cluster: <uuid>
        host: <host>
        port: <port>
        ...
        
        cluster: <uuid>
        ...
        """
        items = []
        current_item = {}
        
        for line in output.splitlines():
            line = line.strip()
            if not line:
                if current_item:
                    items.append(current_item)
                    current_item = {}
                continue
            
            if ":" in line:
                key, value = line.split(":", 1)
                current_item[key.strip()] = value.strip()
        
        if current_item:
            items.append(current_item)
            
        return items

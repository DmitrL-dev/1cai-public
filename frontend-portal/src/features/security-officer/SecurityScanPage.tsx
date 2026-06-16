import React, { useState } from "react";
import { securityOfficerService, Vulnerability } from "../../services/security-officer-service";

export const SecurityScanPage: React.FC = () => {
  const [targetPath, setTargetPath] = useState("");
  const [scanType, setScanType] = useState<"full" | "quick">("quick");
  const [vulnerabilities, setVulnerabilities] = useState<Vulnerability[]>([]);
  const [loading, setLoading] = useState(false);
  const [scannedCount, setScannedCount] = useState(0);

  const handleScan = async () => {
    setLoading(true);
    try {
      const result = await securityOfficerService.runScan({
        target_path: targetPath,
        scan_type: scanType,
      });
      setVulnerabilities(result.vulnerabilities);
      setScannedCount(result.scanned_files_count);
    } catch (error) {
      console.error("Failed to run scan:", error);
      alert("Error running security scan");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-6 text-red-700">Security Officer Agent</h1>

      <div className="bg-white p-6 rounded shadow mb-8">
        <div className="flex gap-4 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium text-gray-700">Target Path</label>
            <input
              type="text"
              value={targetPath}
              onChange={(e) => setTargetPath(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
              placeholder="/path/to/scan"
            />
          </div>
          <div className="w-48">
            <label className="block text-sm font-medium text-gray-700">Scan Type</label>
            <select
              value={scanType}
              onChange={(e) => setScanType(e.target.value as any)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-red-500 focus:ring-red-500"
            >
              <option value="quick">Quick Scan</option>
              <option value="full">Full Scan</option>
            </select>
          </div>
          <button
            onClick={handleScan}
            disabled={loading || !targetPath}
            className="bg-red-600 text-white px-6 py-2 rounded hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? "Scanning..." : "Run Security Scan"}
          </button>
        </div>
      </div>

      {scannedCount > 0 && (
        <div className="mb-4 text-gray-600">
          Scanned {scannedCount} files. Found {vulnerabilities.length} vulnerabilities.
        </div>
      )}

      <div className="space-y-4">
        {vulnerabilities.map((vuln) => (
          <div key={vuln.id} className="border-l-4 border-red-500 bg-white p-4 rounded shadow">
            <div className="flex justify-between">
              <h3 className="font-bold text-lg">{vuln.description}</h3>
              <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${
                vuln.severity === 'critical' ? 'bg-red-100 text-red-800' :
                vuln.severity === 'high' ? 'bg-orange-100 text-orange-800' :
                'bg-yellow-100 text-yellow-800'
              }`}>
                {vuln.severity}
              </span>
            </div>
            <p className="text-gray-600 mt-1 font-mono text-sm">
              {vuln.file_path}:{vuln.line_number}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
};

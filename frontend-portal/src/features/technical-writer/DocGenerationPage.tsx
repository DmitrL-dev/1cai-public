import React, { useState } from "react";
import { technicalWriterService } from "../../services/technical-writer-service";

export const DocGenerationPage: React.FC = () => {
  const [sourceCode, setSourceCode] = useState("");
  const [docType, setDocType] = useState<"api" | "user_guide">("api");
  const [language, setLanguage] = useState<"python" | "javascript" | "bsl">("python");
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const data = await technicalWriterService.generateDocs({
        source_code: sourceCode,
        doc_type: docType,
        language: language,
      });
      setResult(data.content);
    } catch (error) {
      console.error("Failed to generate docs:", error);
      alert("Error generating documentation");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">Technical Writer Agent</h1>
      
      <div className="grid grid-cols-2 gap-8">
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">Language</label>
            <select 
              value={language} 
              onChange={(e) => setLanguage(e.target.value as any)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="python">Python</option>
              <option value="javascript">JavaScript/TypeScript</option>
              <option value="bsl">1C (BSL)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Doc Type</label>
            <select 
              value={docType} 
              onChange={(e) => setDocType(e.target.value as any)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            >
              <option value="api">API Reference</option>
              <option value="user_guide">User Guide</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">Source Code</label>
            <textarea
              value={sourceCode}
              onChange={(e) => setSourceCode(e.target.value)}
              rows={10}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 font-mono text-sm"
              placeholder="Paste your code here..."
            />
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !sourceCode}
            className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? "Generating..." : "Generate Documentation"}
          </button>
        </div>

        <div className="bg-gray-50 p-4 rounded border overflow-auto max-h-[600px]">
          <h3 className="font-medium mb-2">Result:</h3>
          {result ? (
            <pre className="whitespace-pre-wrap text-sm">{result}</pre>
          ) : (
            <p className="text-gray-500 italic">Generated documentation will appear here...</p>
          )}
        </div>
      </div>
    </div>
  );
};

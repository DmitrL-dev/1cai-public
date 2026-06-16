/**
 * BPMN Editor
 * Visual process designer using bpmn.io
 */

import React, { useEffect, useRef, useState } from 'react';

interface BPMNEditorProps {
  diagramId?: string;
  initialXML?: string;
  onSave?: (xml: string) => void;
  readOnly?: boolean;
}

export const BPMNEditor: React.FC<BPMNEditorProps> = ({
  diagramId,
  initialXML,
  onSave,
  readOnly = false
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [modeler, setModeler] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return;

    // Load BPMN.io library
    const loadBPMN = async () => {
      try {
        // In production, import from npm: bpmn-js
        // For now, use CDN
        const BpmnModeler = (window as any).BpmnJS;
        
        if (!BpmnModeler) {
          console.error('BPMN.io not loaded. Include script: https://unpkg.com/bpmn-js/dist/bpmn-modeler.production.min.js');
          return;
        }

        const modelerInstance = new BpmnModeler({
          container: containerRef.current,
          keyboard: {
            bindTo: document
          }
        });

        setModeler(modelerInstance);

        // Load initial diagram
        const xml = initialXML || createEmptyBPMN();
        await modelerInstance.importXML(xml);

      } catch (error) {
        console.error('Error loading BPMN modeler:', error);
      }
    };

    loadBPMN();

    return () => {
      if (modeler) {
        modeler.destroy();
      }
    };
  }, []);

  const handleSave = async () => {
    if (!modeler || !onSave) return;

    setSaving(true);
    try {
      const { xml } = await modeler.saveXML({ format: true });
      onSave(xml);
      
      // Show success toast
      showToast('Diagram saved successfully!', 'success');
    } catch (error) {
      console.error('Error saving diagram:', error);
      showToast('Failed to save diagram', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleExportSVG = async () => {
    if (!modeler) return;

    try {
      const { svg } = await modeler.saveSVG();
      
      // Download SVG
      const blob = new Blob([svg], { type: 'image/svg+xml' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `process-diagram-${diagramId || 'new'}.svg`;
      link.click();
      URL.revokeObjectURL(url);
      
      showToast('Diagram exported as SVG!', 'success');
    } catch (error) {
      console.error('Error exporting SVG:', error);
      showToast('Failed to export diagram', 'error');
    }
  };

  return (
    <div className="flex flex-col h-screen">
      {/* Toolbar */}
      {!readOnly && (
        <div className="bg-white border-b border-gray-200 p-4 flex gap-4">
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-500 hover:bg-blue-600 text-white px-6 py-2 rounded-lg font-semibold disabled:opacity-50"
          >
            {saving ? 'Saving...' : '💾 Save'}
          </button>
          
          <button
            onClick={handleExportSVG}
            className="bg-green-500 hover:bg-green-600 text-white px-6 py-2 rounded-lg font-semibold"
          >
            📥 Export SVG
          </button>
          
          <div className="flex-1"></div>
          
          <button
            onClick={() => modeler?.get('zoomScroll').stepZoom(1)}
            className="bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded-lg"
          >
            🔍+
          </button>
          
          <button
            onClick={() => modeler?.get('zoomScroll').stepZoom(-1)}
            className="bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded-lg"
          >
            🔍-
          </button>
          
          <button
            onClick={() => modeler?.get('zoomScroll').reset()}
            className="bg-gray-200 hover:bg-gray-300 px-4 py-2 rounded-lg"
          >
            ⟲ Reset
          </button>
        </div>
      )}

      {/* Canvas */}
      <div ref={containerRef} className="flex-1 bg-gray-50"></div>

      {/* Helper */}
      {!readOnly && (
        <div className="bg-blue-50 border-t border-blue-200 p-4 text-sm">
          <p className="text-blue-900">
            <strong>💡 Tips:</strong> Drag elements from palette (left) onto canvas. 
            Double-click to edit labels. Connect elements by dragging.
          </p>
        </div>
      )}
    </div>
  );
};

function createEmptyBPMN(): string {
  return `<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                  xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                  xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                  id="Definitions_1">
  <bpmn:process id="Process_1" isExecutable="false">
    <bpmn:startEvent id="StartEvent_1" name="Start" />
  </bpmn:process>
  <bpmndi:BPMNDiagram id="BPMNDiagram_1">
    <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_1">
      <bpmndi:BPMNShape id="StartEvent_1_di" bpmnElement="StartEvent_1">
        <dc:Bounds x="173" y="102" width="36" height="36" />
      </bpmndi:BPMNShape>
    </bpmndi:BPMNPlane>
  </bpmndi:BPMNDiagram>
</bpmn:definitions>`;
}

function showToast(message: string, type: 'success' | 'error') {
  const toast = document.createElement('div');
  toast.className = `fixed bottom-4 right-4 px-6 py-4 rounded-lg text-white ${
    type === 'error' ? 'bg-red-500' : 'bg-green-500'
  } shadow-lg z-50`;
  toast.textContent = message;
  document.body.appendChild(toast);
  
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

export default BPMNEditor;



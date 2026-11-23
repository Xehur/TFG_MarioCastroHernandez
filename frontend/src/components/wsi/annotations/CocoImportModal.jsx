import { useState, useMemo } from 'react';
import {
  FileJson,
  Upload,
  AlertCircle,
  CheckCircle2,
  Loader2,
} from 'lucide-react';
import './CocoImportModal.css';

/**
 * Modal para importar anotaciones desde un archivo COCO JSON (issue 47).
 *
 * Props:
 * - onImport(coco, categoryMapping): importa; devuelve { imported, created_classes }
 * - onClose(): cierra el modal
 */
const CocoImportModal = ({ onImport, onClose }) => {
  const [fileName, setFileName] = useState('');
  const [coco, setCoco] = useState(null);
  const [error, setError] = useState(null);
  const [mapping, setMapping] = useState({});
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);

  const summary = useMemo(() => {
    if (!coco) return null;
    const byShape = {};
    const byCategory = {};
    const catName = {};
    (coco.categories || []).forEach(c => {
      catName[c.id] = c.name;
    });
    (coco.annotations || []).forEach(a => {
      const shape =
        (a.attributes && a.attributes.shape_type) ||
        (a.segmentation ? 'polygon' : 'rectangle');
      byShape[shape] = (byShape[shape] || 0) + 1;
      const name = catName[a.category_id] || 'unclassified';
      byCategory[name] = (byCategory[name] || 0) + 1;
    });
    return {
      total: (coco.annotations || []).length,
      byShape,
      categories: coco.categories || [],
      byCategory,
    };
  }, [coco]);

  const handleFile = e => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setError(null);
    setResult(null);
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(reader.result);
        if (
          !parsed ||
          !Array.isArray(parsed.images) ||
          !Array.isArray(parsed.annotations) ||
          !Array.isArray(parsed.categories)
        ) {
          throw new Error(
            'El archivo no tiene la estructura COCO (images, annotations, categories).'
          );
        }
        setCoco(parsed);
        setMapping({});
      } catch (err) {
        setCoco(null);
        setError(`Archivo inválido: ${err.message}`);
      }
    };
    reader.onerror = () => setError('No se pudo leer el archivo.');
    reader.readAsText(file);
  };

  const handleMappingChange = (name, value) => {
    setMapping(prev => ({ ...prev, [name]: value }));
  };

  const handleImport = async () => {
    if (!coco) return;
    setImporting(true);
    setError(null);
    try {
      const cleaned = {};
      Object.entries(mapping).forEach(([k, v]) => {
        if (v && v.trim() && v.trim() !== k) cleaned[k] = v.trim();
      });
      const res = await onImport(
        coco,
        Object.keys(cleaned).length ? cleaned : null
      );
      setResult(res);
    } catch (err) {
      setError(
        err.response?.data?.detail || err.message || 'Error al importar.'
      );
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="modal-card coco-modal"
        onClick={e => e.stopPropagation()}
      >
        <h2>
          <FileJson size={20} /> Importar anotaciones COCO
        </h2>

        {!result && (
          <>
            <label className="coco-filepick">
              <input type="file" accept=".json,application/json" onChange={handleFile} />
              <Upload size={18} />
              <span>{fileName || 'Seleccionar archivo COCO (.json)'}</span>
            </label>

            {error && (
              <p className="coco-error">
                <AlertCircle size={16} /> {error}
              </p>
            )}

            {summary && (
              <div className="coco-preview">
                <div className="coco-preview-head">
                  <CheckCircle2 size={16} />
                  <span>
                    {summary.total} anotaciones · {summary.categories.length}{' '}
                    categorías
                  </span>
                </div>

                <div className="coco-preview-shapes">
                  {Object.entries(summary.byShape).map(([shape, count]) => (
                    <span key={shape} className="coco-chip">
                      {shape}: {count}
                    </span>
                  ))}
                </div>

                {summary.categories.length > 0 && (
                  <div className="coco-mapping">
                    <p className="coco-mapping-title">
                      Mapeo de categorías (opcional)
                    </p>
                    {summary.categories.map(cat => (
                      <div key={cat.id} className="coco-mapping-row">
                        <span className="coco-mapping-from">
                          {cat.name}{' '}
                          <em>({summary.byCategory[cat.name] || 0})</em>
                        </span>
                        <span className="coco-mapping-arrow">→</span>
                        <input
                          type="text"
                          placeholder={cat.name}
                          value={mapping[cat.name] || ''}
                          onChange={e =>
                            handleMappingChange(cat.name, e.target.value)
                          }
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn modal-btn-cancel"
                onClick={onClose}
              >
                Cancelar
              </button>
              <button
                type="button"
                className="modal-btn modal-btn-save"
                onClick={handleImport}
                disabled={!coco || importing}
              >
                {importing ? (
                  <>
                    <Loader2 size={16} className="coco-spin" /> Importando…
                  </>
                ) : (
                  'Importar'
                )}
              </button>
            </div>
          </>
        )}

        {result && (
          <div className="coco-success">
            <CheckCircle2 size={40} />
            <p>
              Se importaron <strong>{result.imported}</strong> anotaciones.
            </p>
            {result.created_classes?.length > 0 && (
              <p className="coco-success-classes">
                Clases creadas: {result.created_classes.join(', ')}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="modal-btn modal-btn-save"
                onClick={onClose}
              >
                Cerrar
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CocoImportModal;

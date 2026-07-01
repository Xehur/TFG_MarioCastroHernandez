import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowLeft, Ruler, Layers, HardDrive } from 'lucide-react';
import { WSIViewer } from '../../components/wsi';
import {
  AnnotationLayer,
  AnnotationToolbar,
  AnnotationPanel,
  ClassificationModal,
  CocoImportModal,
  useAnnotations,
  centerOnAnnotation,
} from '../../components/wsi/annotations';
import { imageService } from '../../services/imageService';
import { annotationService } from '../../services/annotationService';
import config from '../../config/config';
import './ImageViewer.css';

const ImageViewer = () => {
  const { imageId } = useParams();
  const navigate = useNavigate();
  const numericId = parseInt(imageId, 10);

  const [imageInfo, setImageInfo] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Instancia de OpenSeadragon (cuando el visor está listo)
  const [viewer, setViewer] = useState(null);

  // Estado de anotación
  const [tool, setTool] = useState('select');
  const [color, setColor] = useState('#FF0000');
  const [grid, setGrid] = useState({ enabled: false, size: 256, opacity: 0.4 });
  const [selectedId, setSelectedId] = useState(null);
  const [pendingShape, setPendingShape] = useState(null);
  const [editingAnnotation, setEditingAnnotation] = useState(null);
  const [showCocoImport, setShowCocoImport] = useState(false);

  const {
    annotations,
    classes,
    loading: annotationsLoading,
    createAnnotation,
    updateAnnotation,
    deleteAnnotation,
    createClass,
    importCoco,
  } = useAnnotations(numericId);

  useEffect(() => {
    const fetchImageInfo = async () => {
      try {
        setLoading(true);
        const data = await imageService.getImageById(imageId);
        setImageInfo(data);
        setError(null);
      } catch (err) {
        console.error('Error fetching image info:', err);
        setError('No se pudo cargar la información de la imagen');
      } finally {
        setLoading(false);
      }
    };

    if (imageId) {
      fetchImageInfo();
    }
  }, [imageId]);

  const handleViewerError = useCallback(err => {
    console.error('WSI Viewer error:', err);
    setError(`Error al cargar la imagen: ${err.message}`);
  }, []);

  // Al terminar de dibujar una forma, abrir el modal de clasificación
  const handleCompleteShape = useCallback(shape => {
    setPendingShape(shape);
  }, []);

  const handleSubmitClassification = async ({ label, color: shapeColor, class_id }) => {
    await createAnnotation({
      ...pendingShape,
      label,
      color: shapeColor,
      class_id,
    });
    setPendingShape(null);
    setTool('select');
  };

  const handleCenter = useCallback(
    ann => {
      if (viewer) centerOnAnnotation(viewer, ann);
      setSelectedId(ann.id);
    },
    [viewer]
  );

  const handleEdit = useCallback(ann => {
    setEditingAnnotation(ann);
  }, []);

  const handleSubmitEdit = async ({ label, color: shapeColor, class_id }) => {
    await updateAnnotation(editingAnnotation.id, {
      label,
      color: shapeColor,
      class_id,
    });
    setEditingAnnotation(null);
  };

  const handleDelete = useCallback(
    async id => {
      await deleteAnnotation(id);
      setSelectedId(prev => (prev === id ? null : prev));
    },
    [deleteAnnotation]
  );

  const handleExportCoco = useCallback(async () => {
    try {
      const coco = await annotationService.exportCoco(numericId);
      const blob = new Blob([JSON.stringify(coco, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${imageInfo?.filename || `image_${numericId}`}_coco.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting COCO:', err);
    }
  }, [numericId, imageInfo]);

  if (loading) {
    return (
      <div className="image-viewer-page loading">
        <div className="spinner"></div>
        <p>Cargando información de la imagen...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="image-viewer-page error">
        <h2>
          <AlertCircle size={22} /> Error
        </h2>
        <p>{error}</p>
        <button onClick={() => navigate('/')}>Volver al inicio</button>
      </div>
    );
  }

  return (
    <div className="image-viewer-page">
      <header className="image-viewer-header">
        <button className="back-button" onClick={() => navigate('/')}>
          <ArrowLeft size={16} /> Volver
        </button>
        <div className="image-info">
          <h1>{imageInfo?.filename}</h1>
          <div className="image-metadata">
            <span>
              <Ruler size={15} /> {imageInfo?.width} x {imageInfo?.height} px
            </span>
            <span>
              <Layers size={15} /> {imageInfo?.level_count} niveles
            </span>
            <span>
              <HardDrive size={15} /> {imageInfo?.file_size_mb} MB
            </span>
          </div>
        </div>
      </header>

      <AnnotationToolbar
        tool={tool}
        onToolChange={setTool}
        color={color}
        onColorChange={setColor}
        grid={grid}
        onGridChange={setGrid}
      />

      <div className="viewer-body">
        <div className="image-viewer-content">
          <WSIViewer
            imageId={numericId}
            apiBaseUrl={config.apiBaseUrl}
            onError={handleViewerError}
            onViewerReady={setViewer}
          >
            <AnnotationLayer
              viewer={viewer}
              annotations={annotations}
              tool={tool}
              color={color}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onCompleteShape={handleCompleteShape}
              onCancel={() => setTool('select')}
              grid={grid}
            />
          </WSIViewer>
        </div>

        <AnnotationPanel
          annotations={annotations}
          classes={classes}
          selectedId={selectedId}
          onSelect={setSelectedId}
          onCenter={handleCenter}
          onEdit={handleEdit}
          onDelete={handleDelete}
          onExportCoco={handleExportCoco}
          onImportCoco={() => setShowCocoImport(true)}
          loading={annotationsLoading}
        />
      </div>

      {showCocoImport && (
        <CocoImportModal
          onImport={importCoco}
          onClose={() => setShowCocoImport(false)}
        />
      )}

      {pendingShape && (
        <ClassificationModal
          shape={pendingShape}
          classes={classes}
          defaultColor={color}
          onCreateClass={createClass}
          onSubmit={handleSubmitClassification}
          onCancel={() => setPendingShape(null)}
        />
      )}

      {editingAnnotation && (
        <ClassificationModal
          shape={editingAnnotation}
          classes={classes}
          defaultColor={color}
          initialLabel={editingAnnotation.label || ''}
          initialClassId={editingAnnotation.class_id}
          initialColor={editingAnnotation.color}
          title="Editar anotación"
          submitLabel="Guardar cambios"
          onCreateClass={createClass}
          onSubmit={handleSubmitEdit}
          onCancel={() => setEditingAnnotation(null)}
        />
      )}
    </div>
  );
};

export default ImageViewer;

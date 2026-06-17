import { useState, useCallback } from 'react';
import { imageService } from '../../services/imageService';
import { isValidWSIFile } from '../../utils/helpers';
import './ImageDropZone.css';

/**
 * Componente de zona drag & drop para subir imágenes WSI
 */
const ImageDropZone = ({ onUploadComplete, onUploadError }) => {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState([]);
  const [uploadProgress, setUploadProgress] = useState({});
  const [uploadStatus, setUploadStatus] = useState({}); // 'pending', 'uploading', 'success', 'error'
  const [errors, setErrors] = useState({});

  // Tipos de archivo WSI aceptados
  const ACCEPTED_TYPES = [
    '.svs',
    '.tif',
    '.tiff',
    '.ndpi',
    '.vms',
    '.vmu',
    '.scn',
    '.mrxs',
    '.bif',
  ];

  const validateFile = file => {
    // Validar tipo de archivo
    if (!isValidWSIFile(file.name)) {
      return {
        valid: false,
        error: `Tipo de archivo no válido. Formatos aceptados: ${ACCEPTED_TYPES.join(', ')}`,
      };
    }

    // Validar tamaño (máximo 2GB)
    const maxSize = 2 * 1024 * 1024 * 1024; // 2GB
    if (file.size > maxSize) {
      return {
        valid: false,
        error: 'El archivo es demasiado grande (máximo 2GB)',
      };
    }

    return { valid: true };
  };

  const addFiles = useCallback(newFiles => {
    const validatedFiles = newFiles.map(file => {
      const validation = validateFile(file);
      const fileId = `${file.name}-${Date.now()}-${Math.random()}`;

      if (!validation.valid) {
        setErrors(prev => ({ ...prev, [fileId]: validation.error }));
        setUploadStatus(prev => ({ ...prev, [fileId]: 'error' }));
      } else {
        setUploadStatus(prev => ({ ...prev, [fileId]: 'pending' }));
      }

      return {
        id: fileId,
        file,
        valid: validation.valid,
        error: validation.error,
      };
    });

    setFiles(prev => [...prev, ...validatedFiles]);
  }, []);

  const handleDragEnter = useCallback(e => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(e => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDragOver = useCallback(e => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback(
    e => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);

      const droppedFiles = Array.from(e.dataTransfer.files);
      addFiles(droppedFiles);
    },
    [addFiles]
  );

  const handleFileSelect = e => {
    const selectedFiles = Array.from(e.target.files);
    addFiles(selectedFiles);
  };

  const removeFile = fileId => {
    setFiles(prev => prev.filter(f => f.id !== fileId));
    setUploadProgress(prev => {
      const newProgress = { ...prev };
      delete newProgress[fileId];
      return newProgress;
    });
    setUploadStatus(prev => {
      const newStatus = { ...prev };
      delete newStatus[fileId];
      return newStatus;
    });
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[fileId];
      return newErrors;
    });
  };

  const uploadFile = async fileObj => {
    const { id, file } = fileObj;

    try {
      setUploadStatus(prev => ({ ...prev, [id]: 'uploading' }));
      setUploadProgress(prev => ({ ...prev, [id]: 0 }));

      // Simular progreso (el axios no soporta onUploadProgress en todos los casos)
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => {
          const current = prev[id] || 0;
          if (current < 90) {
            return { ...prev, [id]: current + 10 };
          }
          return prev;
        });
      }, 200);

      const response = await imageService.uploadImage(file);

      clearInterval(progressInterval);
      setUploadProgress(prev => ({ ...prev, [id]: 100 }));
      setUploadStatus(prev => ({ ...prev, [id]: 'success' }));

      if (onUploadComplete) {
        onUploadComplete(response);
      }

      return response;
    } catch (error) {
      setUploadStatus(prev => ({ ...prev, [id]: 'error' }));
      const errorMsg = error.response?.data?.detail || error.message || 'Error al subir el archivo';
      setErrors(prev => ({ ...prev, [id]: errorMsg }));

      if (onUploadError) {
        onUploadError(error);
      }

      throw error;
    }
  };

  const uploadAllFiles = async () => {
    const validFiles = files.filter(f => f.valid && uploadStatus[f.id] === 'pending');

    if (validFiles.length === 0) {
      return;
    }

    // Subir archivos uno por uno (para mejor control del progreso)
    for (const fileObj of validFiles) {
      try {
        await uploadFile(fileObj);
      } catch (error) {
        console.error(`Error uploading ${fileObj.file.name}:`, error);
      }
    }
  };

  const clearAll = () => {
    setFiles([]);
    setUploadProgress({});
    setUploadStatus({});
    setErrors({});
  };

  const getStatusIcon = status => {
    switch (status) {
      case 'pending':
        return '⏳';
      case 'uploading':
        return '📤';
      case 'success':
        return '✅';
      case 'error':
        return '❌';
      default:
        return '📄';
    }
  };

  const hasFilesToUpload = files.some(f => f.valid && uploadStatus[f.id] === 'pending');
  const hasSuccessfulUploads = Object.values(uploadStatus).some(s => s === 'success');

  return (
    <div className="image-drop-zone-container">
      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''} ${files.length > 0 ? 'has-files' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <div className="drop-zone-content">
          <div className="drop-icon">📁</div>
          <h3>Arrastra y suelta imágenes WSI aquí</h3>
          <p>o haz clic para seleccionar archivos</p>
          <p className="file-types">Formatos: {ACCEPTED_TYPES.join(', ')}</p>
          <input
            type="file"
            id="file-input"
            multiple
            accept={ACCEPTED_TYPES.join(',')}
            onChange={handleFileSelect}
            className="file-input"
          />
          <label htmlFor="file-input" className="file-input-label">
            Seleccionar archivos
          </label>
        </div>
      </div>

      {files.length > 0 && (
        <div className="files-list">
          <div className="files-header">
            <h3>Archivos ({files.length})</h3>
            <div className="files-actions">
              {hasFilesToUpload && (
                <button className="btn btn-primary" onClick={uploadAllFiles}>
                  📤 Subir todos
                </button>
              )}
              {hasSuccessfulUploads && (
                <button className="btn btn-secondary" onClick={clearAll}>
                  🗑️ Limpiar completados
                </button>
              )}
            </div>
          </div>

          <div className="files-items">
            {files.map(fileObj => (
              <div key={fileObj.id} className={`file-item status-${uploadStatus[fileObj.id]}`}>
                <div className="file-info">
                  <span className="file-status-icon">
                    {getStatusIcon(uploadStatus[fileObj.id])}
                  </span>
                  <div className="file-details">
                    <div className="file-name">{fileObj.file.name}</div>
                    <div className="file-size">
                      {(fileObj.file.size / (1024 * 1024)).toFixed(2)} MB
                    </div>
                  </div>
                </div>

                <div className="file-actions">
                  {uploadStatus[fileObj.id] === 'uploading' && (
                    <div className="progress-bar">
                      <div
                        className="progress-fill"
                        style={{ width: `${uploadProgress[fileObj.id] || 0}%` }}
                      />
                      <span className="progress-text">{uploadProgress[fileObj.id] || 0}%</span>
                    </div>
                  )}

                  {errors[fileObj.id] && <div className="file-error">{errors[fileObj.id]}</div>}

                  <button
                    className="btn-remove"
                    onClick={() => removeFile(fileObj.id)}
                    disabled={uploadStatus[fileObj.id] === 'uploading'}
                    title="Eliminar"
                  >
                    ✕
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ImageDropZone;

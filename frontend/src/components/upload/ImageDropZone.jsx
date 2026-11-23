import { useState, useCallback } from 'react';
import { Hourglass, UploadCloud, CheckCircle2, XCircle, FileText, FolderUp, Trash2, X } from 'lucide-react';
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

  // Tipos de archivo WSI aceptados (los mismos que valida el backend)
  const ACCEPTED_TYPES = ['.svs', '.tif', '.tiff', '.mrxs'];

  const validateFile = file => {
    // Validar tipo de archivo
    if (!isValidWSIFile(file.name)) {
      return {
        valid: false,
        error: `Tipo de archivo no válido. Formatos aceptados: ${ACCEPTED_TYPES.join(', ')}`,
      };
    }

    // Validar tamaño (máximo 10 GB, igual que MAX_FILE_SIZE del backend)
    const maxSize = 10 * 1024 * 1024 * 1024;
    if (file.size > maxSize) {
      return {
        valid: false,
        error: 'El archivo es demasiado grande (máximo 10 GB)',
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

      const response = await imageService.uploadImage(file, {
        onProgress: percent => {
          setUploadProgress(prev => ({ ...prev, [id]: percent }));
        },
      });

      setUploadProgress(prev => ({ ...prev, [id]: 100 }));
      setUploadStatus(prev => ({ ...prev, [id]: 'success' }));

      if (onUploadComplete) {
        onUploadComplete(response);
      }

      return response;
    } catch (error) {
      setUploadStatus(prev => ({ ...prev, [id]: 'error' }));
      const errorMsg = error.message || 'Error al subir el archivo';
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
        return <Hourglass size={18} />;
      case 'uploading':
        return <UploadCloud size={18} />;
      case 'success':
        return <CheckCircle2 size={18} />;
      case 'error':
        return <XCircle size={18} />;
      default:
        return <FileText size={18} />;
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
          <div className="drop-icon">
            <FolderUp size={48} />
          </div>
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
                  <UploadCloud size={16} /> Subir todos
                </button>
              )}
              {hasSuccessfulUploads && (
                <button className="btn btn-secondary" onClick={clearAll}>
                  <Trash2 size={16} /> Limpiar completados
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
                    <X size={16} />
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

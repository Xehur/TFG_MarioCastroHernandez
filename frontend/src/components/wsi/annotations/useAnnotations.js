/**
 * Hook que gestiona el estado de las anotaciones y clases de una imagen,
 * sincronizándolo con el backend.
 */
import { useState, useEffect, useCallback } from 'react';
import { annotationService } from '../../../services/annotationService';

export function useAnnotations(imageId) {
  const [annotations, setAnnotations] = useState([]);
  const [classes, setClasses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      if (!imageId) return;
      try {
        setLoading(true);
        const [list, cls] = await Promise.all([
          annotationService.list(imageId),
          annotationService.listClasses(),
        ]);
        if (mounted) {
          setAnnotations(list.items || []);
          setClasses(cls || []);
          setError(null);
        }
      } catch (err) {
        if (mounted) setError(err.message || 'Error al cargar anotaciones');
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    return () => {
      mounted = false;
    };
  }, [imageId]);

  const createAnnotation = useCallback(
    async payload => {
      const created = await annotationService.create(imageId, payload);
      setAnnotations(prev => [...prev, created]);
      return created;
    },
    [imageId]
  );

  const updateAnnotation = useCallback(async (id, payload) => {
    const updated = await annotationService.update(id, payload);
    setAnnotations(prev => prev.map(a => (a.id === id ? updated : a)));
    return updated;
  }, []);

  const deleteAnnotation = useCallback(async id => {
    await annotationService.remove(id);
    setAnnotations(prev => prev.filter(a => a.id !== id));
  }, []);

  const createClass = useCallback(async payload => {
    const created = await annotationService.createClass(payload);
    setClasses(prev => [...prev, created]);
    return created;
  }, []);

  return {
    annotations,
    classes,
    loading,
    error,
    createAnnotation,
    updateAnnotation,
    deleteAnnotation,
    createClass,
  };
}

export default useAnnotations;

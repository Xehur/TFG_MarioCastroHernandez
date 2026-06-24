import './AnnotationPanel.css';

const SHAPE_ICON = { rectangle: '▭', circle: '◯', polygon: '⬠' };

/**
 * Panel lateral con la lista de anotaciones guardadas.
 *
 * Props:
 * - annotations: array
 * - classes: array de clases (para mostrar el nombre)
 * - selectedId
 * - onSelect(id)
 * - onCenter(annotation): centra el visor en la anotación
 * - onEdit(annotation): abre el modal de edición (etiqueta, clase, color)
 * - onDelete(id)
 * - loading
 */
const AnnotationPanel = ({
  annotations = [],
  classes = [],
  selectedId,
  onSelect,
  onCenter,
  onEdit,
  onDelete,
  loading,
}) => {
  const classNameOf = id => classes.find(c => c.id === id)?.name;

  return (
    <aside className="annotation-panel">
      <div className="panel-header">
        <h3>Anotaciones</h3>
        <span className="panel-count">{annotations.length}</span>
      </div>

      {loading ? (
        <p className="panel-empty">Cargando…</p>
      ) : annotations.length === 0 ? (
        <p className="panel-empty">
          No hay anotaciones. Usa las herramientas para dibujar sobre la imagen.
        </p>
      ) : (
        <ul className="panel-list">
          {annotations.map(ann => (
            <li
              key={ann.id}
              className={`panel-item ${ann.id === selectedId ? 'selected' : ''}`}
              onClick={() => onSelect(ann.id)}
            >
              <span className="item-color" style={{ background: ann.color }} />
              <span className="item-shape">{SHAPE_ICON[ann.shape_type] || '?'}</span>
              <div className="item-body">
                <span className="item-label">{ann.label || '(sin etiqueta)'}</span>
                {classNameOf(ann.class_id) && (
                  <span className="item-class">{classNameOf(ann.class_id)}</span>
                )}
              </div>
              <div className="item-actions" onClick={e => e.stopPropagation()}>
                <button title="Centrar" onClick={() => onCenter(ann)}>
                  🎯
                </button>
                <button title="Editar" onClick={() => onEdit(ann)}>
                  ✏️
                </button>
                <button title="Eliminar" onClick={() => onDelete(ann.id)}>
                  🗑️
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </aside>
  );
};

export default AnnotationPanel;

import { useState } from 'react';
import './ClassificationModal.css';

/**
 * Modal para clasificar/etiquetar una anotación recién dibujada o existente.
 *
 * Props:
 * - shape: { shape_type } de la forma (pendiente o existente)
 * - classes: clases disponibles
 * - defaultColor: color por defecto si no hay valor inicial
 * - initialLabel / initialClassId / initialColor: valores iniciales (edición)
 * - title: título del modal
 * - submitLabel: texto del botón de confirmación
 * - onCreateClass(payload): crea una nueva clase, devuelve la clase creada
 * - onSubmit({ label, color, class_id }): confirma
 * - onCancel(): cancela
 */
const ClassificationModal = ({
  shape,
  classes = [],
  defaultColor = '#FF0000',
  initialLabel = '',
  initialClassId = null,
  initialColor = null,
  title = 'Clasificar anotación',
  submitLabel = 'Guardar',
  onCreateClass,
  onSubmit,
  onCancel,
}) => {
  const [label, setLabel] = useState(initialLabel || '');
  const [classId, setClassId] = useState(initialClassId ? String(initialClassId) : '');
  const [color, setColor] = useState(initialColor || defaultColor);
  const [creatingClass, setCreatingClass] = useState(false);
  const [newClassName, setNewClassName] = useState('');
  const [newClassColor, setNewClassColor] = useState('#FF0000');
  const [submitting, setSubmitting] = useState(false);

  const handleSelectClass = value => {
    setClassId(value);
    const cls = classes.find(c => String(c.id) === String(value));
    if (cls) setColor(cls.color);
  };

  const handleCreateClass = async () => {
    if (!newClassName.trim()) return;
    const created = await onCreateClass({ name: newClassName.trim(), color: newClassColor });
    setClassId(String(created.id));
    setColor(created.color);
    setCreatingClass(false);
    setNewClassName('');
  };

  const handleSubmit = async e => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await onSubmit({
        label: label.trim() || null,
        color,
        class_id: classId ? Number(classId) : null,
      });
    } finally {
      setSubmitting(false);
    }
  };

  const shapeName =
    { rectangle: 'Rectángulo', circle: 'Círculo', polygon: 'Polígono' }[shape?.shape_type] ||
    'Forma';

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" onClick={e => e.stopPropagation()}>
        <h2>{title}</h2>
        <p className="modal-shape">Forma: {shapeName}</p>

        <form onSubmit={handleSubmit} className="modal-form">
          <div className="modal-field">
            <label htmlFor="label">Etiqueta</label>
            <input
              id="label"
              type="text"
              value={label}
              onChange={e => setLabel(e.target.value)}
              placeholder="p.ej. Mitosis, Zona dudosa…"
              autoFocus
            />
          </div>

          <div className="modal-field">
            <label htmlFor="class">Clasificación</label>
            <select id="class" value={classId} onChange={e => handleSelectClass(e.target.value)}>
              <option value="">Sin clasificar</option>
              {classes.map(c => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          {!creatingClass ? (
            <button type="button" className="modal-link" onClick={() => setCreatingClass(true)}>
              + Nueva clase
            </button>
          ) : (
            <div className="modal-newclass">
              <input
                type="text"
                value={newClassName}
                onChange={e => setNewClassName(e.target.value)}
                placeholder="Nombre de la clase"
              />
              <input
                type="color"
                value={newClassColor}
                onChange={e => setNewClassColor(e.target.value)}
              />
              <button type="button" onClick={handleCreateClass} className="modal-btn-small">
                Crear
              </button>
            </div>
          )}

          <div className="modal-field">
            <label htmlFor="color">Color</label>
            <input id="color" type="color" value={color} onChange={e => setColor(e.target.value)} />
          </div>

          <div className="modal-actions">
            <button type="button" className="modal-btn modal-btn-cancel" onClick={onCancel}>
              Cancelar
            </button>
            <button type="submit" className="modal-btn modal-btn-save" disabled={submitting}>
              {submitting ? 'Guardando…' : submitLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default ClassificationModal;
